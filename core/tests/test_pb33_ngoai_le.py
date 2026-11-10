"""Kiểm thử Phần 5b – Admin xử lý ngoại lệ, sửa dữ liệu; NVTS đổi gia sư."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from core.integrations import zoom
from core.integrations.zoom import NguoiThamGia
from core.models import BuoiHoc, DoiGiaSu, KhoaHoc, LoiMoi, NhatKy, ThuLao, User, YeuCauHocTap
from core.services import buoi_hoc as dv_buoi
from core.services import ngoai_le as dv
from core.services import yeu_cau as dv_yc
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, MK, DuLieu, ngay_mai

TT = BuoiHoc.TrangThai
KH = KhoaHoc.TrangThai
YC = YeuCauHocTap.TrangThai


class NgoaiLe(DuLieu):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")

    def buoi_xac_nhan(self, gio=19, truoc=1):
        b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(gio)), ket_thuc_truoc_gio=truoc)
        dv_buoi.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        b.refresh_from_db()
        return b

    def buoi_khong_dat(self):
        b = self.buoi_xac_nhan()
        zoom._fake_singleton.kich_ban_tham_gia[b.zoom_meeting_id] = [
            NguoiThamGia("GS", "", b.bat_dau, b.bat_dau + timedelta(minutes=60), la_host=True)]
        dv_buoi.hau_kiem()
        b.refresh_from_db()
        from core.services import hau_kiem as dv_hk
        dv_hk.ket_luan(self.nvts, b.hau_kiem, "CO_VAN_DE", "THIEU_GIO", "Học viên không vào lớp")
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DANG_XEM_XET)
        return b

    def buoi_qua_han(self, truoc_gio=13):
        b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=truoc_gio)
        dv_buoi.quet_han()
        b.refresh_from_db()
        return b


class XemXetBuoiTest(NgoaiLe):
    def test_cong_nhan_hop_le_tra_thu_lao_ve_tam_tinh(self):
        b = self.buoi_khong_dat()
        dv.xac_nhan_hop_le(self.admin, b, "Phụ huynh xác nhận em có học")
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.kiem_tra), (TT.HOAN_TAT, BuoiHoc.KiemTra.DA_XU_LY))
        self.assertEqual(ThuLao.objects.get(buoi_hoc=b).trang_thai, ThuLao.TrangThai.TAM_TINH)

    def test_khong_cong_nhan_tra_lai_buoi_cho_khoa(self):
        b = self.buoi_khong_dat()
        dv.huy_sau_xem_xet(self.admin, b, "Học viên không vào lớp")
        b.refresh_from_db()
        self.khoa.refresh_from_db()
        self.assertEqual((b.trang_thai, b.ly_do_huy), (TT.DA_HUY, BuoiHoc.LyDoHuy.HAU_KIEM))
        self.assertEqual(self.khoa.so_buoi_da_dung, 0)
        self.assertEqual(ThuLao.objects.get(buoi_hoc=b).trang_thai, ThuLao.TrangThai.HUY)

    def test_thao_tac_admin_bat_buoc_ly_do(self):
        b = self.buoi_khong_dat()
        with self.assertRaisesMessage(ValidationError, "lý do"):
            dv.xac_nhan_hop_le(self.admin, b, "  ")

    def test_mo_lai_buoi_qua_han_cho_them_24h(self):
        b = self.buoi_qua_han()
        self.assertEqual(b.ly_do_huy, BuoiHoc.LyDoHuy.QUA_HAN)
        dv.mo_lai(self.admin, b, "Gia sư quên xác nhận")
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DA_LEN_LICH)
        self.assertGreater(b.han_xac_nhan, timezone.now() + timedelta(hours=23))
        dv_buoi.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)  # gia sư xác nhận được
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.so_buoi_da_dung, 1)

    def test_qua_7_ngay_khong_mo_lai_duoc(self):
        b = self.buoi_qua_han()
        BuoiHoc.objects.filter(pk=b.pk).update(han_xac_nhan=timezone.now() - timedelta(days=8))
        b.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "không mở lại được"):
            dv.mo_lai(self.admin, b, "Muộn")

    def test_chi_admin_vao_trang_xem_xet(self):
        self.dang_nhap(self.nvts)
        self.assertEqual(self.client.get(reverse("xem_xet")).status_code, 403)
        self.dang_nhap(self.admin)
        b = self.buoi_qua_han()  # QTV xử lý buổi tự hủy; buổi hậu kiểm có vấn đề do Tuyển sinh (Q1)
        r = self.client.get(reverse("xem_xet"))
        self.assertContains(r, b.ma)


class SuaDuLieuTest(NgoaiLe):
    def test_khong_giam_so_buoi_duoi_so_da_dung(self):
        self.buoi_xac_nhan()
        dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        with self.assertRaisesMessage(ValidationError, "ít nhất 2"):
            dv.sua_so_buoi(self.admin, self.khoa, 1, "Nhập nhầm")
        k = dv.sua_so_buoi(self.admin, self.khoa, 30, "Phụ huynh đăng ký 30 buổi")
        self.assertEqual(k.so_buoi_dang_ky, 30)
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Admin sửa số buổi đăng ký").exists())

    def test_nvts_khong_sua_so_buoi(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_sua_so_buoi", args=[self.khoa.pk]), {"so_buoi": 30, "ly_do": "x"})
        self.assertEqual(r.status_code, 403)

    def test_admin_sua_yeu_cau_da_khoa_phai_ghi_ly_do(self):
        self.dang_nhap(self.admin)
        url = reverse("yeu_cau_sua", args=[self.yc.pk])
        du_lieu = {"mon_hoc": self.toan.pk, "trinh_do": "Lớp 10", "muc_tieu": "Thi 10", "khung_mong_muon": ["0-TOI"]}

        r = self.client.post(url, du_lieu)
        self.assertContains(r, "Cần ghi lý do sửa")
        r = self.client.post(url, {**du_lieu, "ly_do": "Nhập sai trình độ"})
        self.assertRedirects(r, reverse("yeu_cau_chi_tiet", args=[self.yc.pk]))
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.trinh_do, "Lớp 10")


class DoiGiaSuTest(NgoaiLe):
    def test_doi_gia_su_giu_so_buoi_con_lai(self):
        self.buoi_xac_nhan()
        sap_toi = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        dn = dv.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU)
        self.assertEqual(dn.trang_thai, DoiGiaSu.TrangThai.DA_THUC_HIEN)
        sap_toi.refresh_from_db()
        self.khoa.refresh_from_db()
        self.yc.refresh_from_db()
        self.assertEqual(sap_toi.trang_thai, TT.DA_HUY)
        self.assertEqual((self.khoa.trang_thai, self.yc.trang_thai, self.yc.gia_su), (KH.TAM_DUNG, YC.DANG_TIM, None))
        # Mời gia sư mới → nhận lớp → khóa học tiếp với gia sư mới, số buổi giữ nguyên.
        (lm,), _ = dv_yc.gui_loi_moi(self.nvts, self.yc, [self.gs2.pk])
        dv_yc.chap_nhan(self.gs2, lm)
        self.khoa.refresh_from_db()
        self.yc.refresh_from_db()
        self.assertEqual((self.khoa.gia_su, self.khoa.trang_thai), (self.gs2, KH.DANG_HOC))
        self.assertEqual((self.khoa.so_buoi_da_dung, self.khoa.so_buoi_con_lai), (1, 1))
        self.assertEqual(self.yc.trang_thai, YC.CHINH_THUC)
        # Thù lao buổi đã dạy vẫn thuộc gia sư cũ; gia sư cũ không còn xem được khóa.
        self.assertEqual(ThuLao.objects.get().gia_su, self.gs)
        self.dang_nhap(self.gs)
        self.assertEqual(self.client.get(reverse("khoa_cua_toi", args=[self.khoa.pk])).status_code, 404)

    def test_lan_doi_thu_hai_cho_admin_duyet(self):
        dv.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.KHONG_PHU_HOP)
        (lm,), _ = dv_yc.gui_loi_moi(self.nvts, self.yc, [self.gs2.pk])
        dv_yc.chap_nhan(self.gs2, lm)
        self.khoa.refresh_from_db()
        dn = dv.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU)
        self.assertEqual(dn.trang_thai, DoiGiaSu.TrangThai.CHO_DUYET)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.trang_thai, KH.DANG_HOC)  # chưa đổi gì cho tới khi Admin duyệt
        dv.duyet_doi_gia_su(self.admin, dn, dong_y=True)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.trang_thai, KH.TAM_DUNG)

    def test_khong_tiep_tuc_khoa_khi_chua_co_gia_su_moi(self):
        dv.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.GIA_SU_NGHI)
        from core.services import khoa_hoc as dv_kh
        with self.assertRaisesMessage(ValidationError, "chờ gia sư mới"):
            dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.DANG_HOC)


class GanThangTest(NgoaiLe):
    def test_admin_gan_thang_vo_hieu_loi_moi_khac(self):
        yc2 = YeuCauHocTap.objects.create(hoc_vien=self.hv, mon_hoc=self.toan, trinh_do="Lớp 8", muc_tieu="x",
                                          thu_mong_muon=[1], lich_mong_muon="Tối", tao_boi=self.nvts)
        dv_yc.gui_loi_moi(self.nvts, yc2, [self.gs.pk])
        dv.gan_thang(self.admin, yc2, self.gs2, "Đã thỏa thuận qua điện thoại")
        yc2.refresh_from_db()
        self.assertEqual((yc2.trang_thai, yc2.gia_su), (YC.DA_PHAN_CONG, self.gs2))
        self.assertFalse(yc2.loi_moi.filter(trang_thai=LoiMoi.TrangThai.CHO).exists())
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Vận hành gán thẳng gia sư").exists())


class SuaLoiReviewTest(NgoaiLe):
    """Các lỗi phát hiện ở lần code-review Phần 5–6."""

    def test_huy_khoa_huy_luon_buoi_sap_toi_va_xoa_zoom(self):
        from core.services import khoa_hoc as dv_kh
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        with self.captureOnCommitCallbacks(execute=True):
            dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HUY, "Phụ huynh dừng học")
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DA_HUY)
        self.assertNotIn(b.zoom_meeting_id, zoom._fake_singleton.phong_da_tao)

    def test_huy_khoa_dang_doi_gia_su_thi_khong_song_lai(self):
        from core.services import khoa_hoc as dv_kh
        dv.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.GIA_SU_NGHI)
        self.yc.refresh_from_db()
        (lm,), _ = dv_yc.gui_loi_moi(self.nvts, self.yc, [self.gs2.pk])
        self.khoa.refresh_from_db()
        dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HUY, "Phụ huynh dừng học")
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.trang_thai, YC.DONG)
        with self.assertRaises(ValidationError):
            dv_yc.chap_nhan(self.gs2, lm)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.trang_thai, KH.HUY)

    def test_doi_lich_loi_thi_giu_nguyen_buoi_cu_va_phong_zoom(self):
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        KhoaHoc.objects.filter(pk=self.khoa.pk).update(trang_thai=KH.TAM_DUNG)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValidationError):
                dv_buoi.doi_lich(self.gs, b, ngay_mai(10))
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DA_LEN_LICH)
        self.assertIn(b.zoom_meeting_id, zoom._fake_singleton.phong_da_tao)

    def test_mo_lai_bi_chan_khi_khoa_het_cho(self):
        b = self.buoi_qua_han()
        dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(10))  # 2/2 chỗ đã lên lịch
        with self.assertRaisesMessage(ValidationError, "không còn chỗ"):
            dv.mo_lai(self.admin, b, "Quên xác nhận")

    def test_buoi_loi_zoom_qua_gio_huy_dung_ly_do_va_bao_gia_su(self):
        zoom._fake_singleton.gia_lap_loi = True
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        BuoiHoc.objects.filter(pk=b.pk).update(bat_dau=timezone.now() - timedelta(minutes=5))
        dv_buoi.quet_han()
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.ly_do_huy), (TT.DA_HUY, BuoiHoc.LyDoHuy.LOI_ZOOM))
        from core.models import NhatKyGuiTin
        self.assertTrue(NhatKyGuiTin.objects.filter(buoi_hoc=b, tieu_de__contains="chưa có phòng Zoom").exists())

    def test_loi_gio_hien_tai_o_gio_bat_dau(self):
        self.dang_nhap(self.gs)
        r = self.client.post(reverse("buoi_tao"), {"lop": f"k-{self.khoa.pk}", "ngay": "2020-01-01", "gio": "08:00"})
        self.assertEqual(r.status_code, 200)  # không tạo được buổi nào → ở lại form
        self.assertContains(r, "tương lai")
