"""Kiểm thử Phần 5a – buổi học: tạo buổi + Zoom, hủy/dời lịch, xác nhận hoàn tất, Zalo, hạn 12h, hậu kiểm.

Backlog: PB-07 (gia sư tạo buổi học thử), PB-11..PB-15, PB-16, PB-29, PB-31, PB-32.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.integrations import zalo, zoom
from core.integrations.zoom import NguoiThamGia
from core.models import BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, MonGiaSu, MonHoc, NhatKyGuiTin, ThuLao, User, YeuCauHocTap
from core.services import buoi_hoc as dv
from core.services import khoa_hoc as dv_kh

MK = "MatKhau@Manh123"
TT = BuoiHoc.TrangThai
YC = YeuCauHocTap.TrangThai
KHOA = {"so_buoi_dang_ky": 2, "thoi_luong_phut": 60, "hoc_phi_moi_buoi": 200_000, "thu_lao_moi_buoi": 120_000}
DANH_GIA = {"noi_dung": "Phương trình bậc hai", "xep_loai": "TOT", "danh_gia": "Em làm bài tốt",
            "dan_do_buoi_sau": "Làm bài 1-5"}


def ngay_mai(gio=19):
    return (timezone.now() + timedelta(days=1)).replace(hour=gio, minute=0, second=0, microsecond=0)


class DuLieu(TestCase):
    def setUp(self):
        # Test luôn chạy với thời lượng thật, dù file .env đang bật chế độ chạy thử.
        self.enterContext(override_settings(NGHIEP_VU={**settings.NGHIEP_VU, "THOI_LUONG_BUOI_DEMO": 0}))
        zoom._fake_singleton.gia_lap_loi = False
        zoom._fake_singleton.kich_ban_tham_gia.clear()
        zalo._fake_singleton.gia_lap_loi = False
        self.nvts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="NVTS")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.gs = self.tao_gia_su("gs", "Gia Sư A")
        self.gs2 = self.tao_gia_su("gs2", "Gia Sư B")
        self.hv = HocVien.objects.create(ho_ten="Học Viên", lop="Lớp 9", ten_phu_huynh="PH",
                                         sdt_phu_huynh="84905123456", dong_y_ghi_hinh=True)
        self.yc = self.tao_yc(self.gs)
        self.khoa = dv_kh.tao_khoa_hoc(self.nvts, self.yc, KHOA)

    def tearDown(self):
        zoom._fake_singleton.gia_lap_loi = False
        zalo._fake_singleton.gia_lap_loi = False

    def tao_gia_su(self, username, ten):
        u = User.objects.create_user(username, password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten=ten,
                                     email=f"{username}@test.local")
        hs = HoSoGiaSu.objects.create(user=u, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG)
        MonGiaSu.objects.create(ho_so=hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        return u

    def tao_yc(self, gs):
        return YeuCauHocTap.objects.create(
            hoc_vien=self.hv, mon_hoc=self.toan, trinh_do="Lớp 9", muc_tieu="Thi 10", thu_mong_muon=[0],
            lich_mong_muon="Tối", trang_thai=YC.DA_PHAN_CONG, gia_su=gs, phan_cong_luc=timezone.now(),
            tao_boi=self.nvts)

    def ve_qua_khu(self, buoi, ket_thuc_truoc_gio=1):
        """Dời buổi về quá khứ: đã kết thúc `ket_thuc_truoc_gio` giờ trước (giữ đúng hạn 12h)."""
        bat_dau = timezone.now() - timedelta(hours=ket_thuc_truoc_gio, minutes=buoi.thoi_luong_phut)
        BuoiHoc.objects.filter(pk=buoi.pk).update(
            bat_dau=bat_dau, han_xac_nhan=bat_dau + timedelta(minutes=buoi.thoi_luong_phut, hours=12))
        buoi.refresh_from_db()
        return buoi

    def dang_nhap(self, u):
        self.client.logout()
        self.client.login(username=u.username, password=MK)


class TaoBuoiTest(DuLieu):
    def test_PB11_tao_buoi_chinh_thuc_co_phong_zoom(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        self.assertEqual(b.trang_thai, TT.DA_LEN_LICH)
        self.assertTrue(b.zoom_join_url and b.zoom_meeting_id)
        self.assertEqual(b.thu_lao_du_kien, 120_000)
        self.assertEqual(b.han_xac_nhan, b.ket_thuc + timedelta(hours=12))
        self.assertEqual(b.ban_ghi_trang_thai, BuoiHoc.BanGhi.CHO_XU_LY)  # phụ huynh đồng ý ghi hình

    def test_PB12_khong_xep_vuot_so_buoi_dang_ky(self):
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(10))
        with self.assertRaisesMessage(ValidationError, "đủ số buổi"):
            dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(14))

    def test_trung_gio_cua_chinh_minh_bi_chan(self):
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(19))
        with self.assertRaisesMessage(ValidationError, "trùng khung giờ"):
            dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(19) + timedelta(minutes=30))

    def test_mot_tai_khoan_zoom_chan_trung_gio_toan_trung_tam(self):
        yc2 = self.tao_yc(self.gs2)
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(19))
        with self.assertRaisesMessage(ValidationError, "phòng Zoom của trung tâm"):
            dv.tao_buoi_hoc_thu(self.gs2, yc2, ngay_mai(19) + timedelta(minutes=15), 60)
        # Khác giờ thì được.
        self.assertEqual(dv.tao_buoi_hoc_thu(self.gs2, yc2, ngay_mai(21), 60).trang_thai, TT.DA_LEN_LICH)

    def test_gio_qua_khu_bi_chan(self):
        with self.assertRaisesMessage(ValidationError, "tương lai"):
            dv.tao_buoi_chinh_thuc(self.gs, self.khoa, timezone.now() - timedelta(hours=1))

    def test_PB29_zoom_loi_thi_luu_LOI_ZOOM_va_thu_lai_duoc(self):
        zoom._fake_singleton.gia_lap_loi = True
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        self.assertEqual(b.trang_thai, TT.LOI_ZOOM)
        self.assertIn("Zoom", b.zoom_loi)
        zoom._fake_singleton.gia_lap_loi = False
        self.assertTrue(dv.thu_lai_zoom(self.gs, b))
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DA_LEN_LICH)

    def test_PB07_gia_su_tao_buoi_hoc_thu_mot_lan(self):
        yc2 = self.tao_yc(self.gs2)
        dv.tao_buoi_hoc_thu(self.gs2, yc2, ngay_mai(8), 60)
        with self.assertRaisesMessage(ValidationError, "đã có buổi học thử"):
            dv.tao_buoi_hoc_thu(self.gs2, yc2, ngay_mai(10), 60)

    def test_khoa_tam_dung_khong_tao_buoi(self):
        KhoaHoc.objects.filter(pk=self.khoa.pk).update(trang_thai=KhoaHoc.TrangThai.TAM_DUNG)
        with self.assertRaisesMessage(ValidationError, "Tạm dừng"):
            dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())

    def test_tao_buoi_qua_giao_dien(self):
        self.dang_nhap(self.gs)
        gio = ngay_mai().astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%dT%H:%M")
        r = self.client.post(reverse("buoi_tao"), {"lop": f"k-{self.khoa.pk}", "bat_dau": gio})
        b = BuoiHoc.objects.get()
        self.assertRedirects(r, reverse("buoi_chi_tiet", args=[b.pk]))
        self.assertContains(self.client.get(reverse("buoi_chi_tiet", args=[b.pk])), b.zoom_join_url)


class CheDoChayThuTest(DuLieu):
    def test_buoi_hoc_dai_1_phut_khi_bat_che_do_chay_thu(self):
        with override_settings(NGHIEP_VU={**settings.NGHIEP_VU, "THOI_LUONG_BUOI_DEMO": 1}):
            b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, timezone.now() + timedelta(minutes=2))
            self.assertEqual(b.thoi_luong_phut, 1)
            BuoiHoc.objects.filter(pk=b.pk).update(bat_dau=timezone.now() - timedelta(minutes=2))
            b.refresh_from_db()
            dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
            self.assertEqual(ThuLao.objects.get(buoi_hoc=b).so_tien, 120_000)


class HuyDoiLichTest(DuLieu):
    def test_PB13_doi_lich_huy_buoi_cu_tao_buoi_moi(self):
        cu = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        moi = dv.doi_lich(self.gs, cu, ngay_mai(8) + timedelta(days=1))
        cu.refresh_from_db()
        self.assertEqual((cu.trang_thai, cu.ly_do_huy), (TT.DA_HUY, BuoiHoc.LyDoHuy.DOI_LICH))
        self.assertEqual(moi.thay_the_cho, cu)
        self.assertNotEqual(moi.zoom_meeting_id, cu.zoom_meeting_id)

    def test_doi_lich_sang_gio_trung_thi_giu_nguyen_buoi_cu(self):
        cu = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(10))
        with self.assertRaises(ValidationError):
            dv.doi_lich(self.gs, cu, ngay_mai(10))
        cu.refresh_from_db()
        self.assertEqual(cu.trang_thai, TT.DA_LEN_LICH)

    def test_huy_buoi_tra_lai_cho_xep_lich(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(10))
        dv.huy_buoi(self.gs, b, BuoiHoc.LyDoHuy.HOC_VIEN_HUY)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.so_buoi_co_the_xep, 1)


class XacNhanTest(DuLieu):
    def test_PB14_xac_nhan_cong_so_buoi_tao_thu_lao_gui_zalo(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        b.refresh_from_db()
        self.khoa.refresh_from_db()
        self.assertEqual((b.trang_thai, b.so_thu_tu), (TT.HOAN_TAT, 1))
        self.assertEqual(self.khoa.so_buoi_da_dung, 1)
        tl = ThuLao.objects.get(buoi_hoc=b)
        self.assertEqual((tl.so_tien, tl.trang_thai), (120_000, ThuLao.TrangThai.TAM_TINH))
        self.assertEqual(b.zalo_trang_thai, BuoiHoc.GuiZalo.DA_GUI)
        self.assertTrue(NhatKyGuiTin.objects.filter(kenh="ZALO", buoi_hoc=b, thanh_cong=True).exists())

    def test_PB16_xac_nhan_hai_lan_chi_cong_mot_buoi(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        with self.assertRaises(ValidationError):
            dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.so_buoi_da_dung, 1)
        self.assertEqual(ThuLao.objects.count(), 1)

    def test_chua_het_gio_chua_xac_nhan_duoc(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        with self.assertRaisesMessage(ValidationError, "sau giờ kết thúc"):
            dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)

    def test_du_so_buoi_thi_khoa_hoan_thanh(self):
        for gio in (8, 10):
            b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(gio)), ket_thuc_truoc_gio=gio - 6)
            dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.trang_thai, KhoaHoc.TrangThai.HOAN_THANH)

    def test_PB15_zalo_loi_van_hoan_tat(self):
        zalo._fake_singleton.gia_lap_loi = True
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.zalo_trang_thai), (TT.HOAN_TAT, BuoiHoc.GuiZalo.LOI))
        self.assertIn("Em làm bài tốt", dv.noi_dung_gui_phu_huynh(b))

    def test_xac_nhan_qua_giao_dien_thieu_nhan_xet_bao_loi_tai_o(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        self.dang_nhap(self.gs)
        r = self.client.post(reverse("buoi_xac_nhan", args=[b.pk]), {**DANH_GIA, "danh_gia": ""})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "tom-tat-loi", status_code=400)
        r = self.client.post(reverse("buoi_xac_nhan", args=[b.pk]), DANH_GIA)
        self.assertRedirects(r, reverse("buoi_chi_tiet", args=[b.pk]))


class HanVaHauKiemTest(DuLieu):
    def test_PB31_qua_12h_tu_huy_va_khong_xac_nhan_duoc(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=13)
        self.assertEqual(dv.quet_han(), 1)
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.ly_do_huy), (TT.DA_HUY, BuoiHoc.LyDoHuy.QUA_HAN))
        with self.assertRaises(ValidationError):
            dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.so_buoi_da_dung, 0)

    def test_nhac_han_gui_mot_lan(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=10)
        dv.quet_han()
        dv.quet_han()
        self.assertEqual(NhatKyGuiTin.objects.filter(buoi_hoc=b, tieu_de__startswith="Nhắc xác nhận").count(), 1)

    def _xac_nhan_xong(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        dv.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        b.refresh_from_db()
        return b

    def _kich_ban(self, b, phut_hoc_vien):
        t0 = b.bat_dau
        zoom._fake_singleton.kich_ban_tham_gia[b.zoom_meeting_id] = [
            NguoiThamGia("GS", "host@x", t0, t0 + timedelta(minutes=60), la_host=True),
            NguoiThamGia("HV", "", t0, t0 + timedelta(minutes=phut_hoc_vien)),
        ]

    def test_PB32_hau_kiem_dat(self):
        b = self._xac_nhan_xong()
        self._kich_ban(b, 55)
        dv.hau_kiem()
        b.refresh_from_db()
        self.assertEqual((b.kiem_tra, b.phut_tham_gia_chung), (BuoiHoc.KiemTra.HOP_LE, 55))
        self.assertEqual(b.ban_ghi_trang_thai, BuoiHoc.BanGhi.SAN_SANG)

    def test_PB32_hau_kiem_khong_dat_tam_giu_thu_lao(self):
        b = self._xac_nhan_xong()
        self._kich_ban(b, 10)
        dv.hau_kiem()
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.kiem_tra), (TT.DANG_XEM_XET, BuoiHoc.KiemTra.CO_VAN_DE))
        self.assertEqual(ThuLao.objects.get(buoi_hoc=b).trang_thai, ThuLao.TrangThai.TAM_GIU)
        self.assertTrue(NhatKyGuiTin.objects.filter(buoi_hoc=b, tieu_de__contains="đang được xem xét").exists())

    def test_goi_free_khong_co_du_lieu_thi_giu_nguyen(self):
        b = self._xac_nhan_xong()
        dv.hau_kiem()
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.kiem_tra), (TT.HOAN_TAT, BuoiHoc.KiemTra.KHONG_DU_LIEU))
        self.assertEqual(ThuLao.objects.get(buoi_hoc=b).trang_thai, ThuLao.TrangThai.TAM_TINH)


class QuyenTest(DuLieu):
    def test_PB24_gia_su_khac_khong_xem_khong_sua_buoi(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        self.dang_nhap(self.gs2)
        self.assertEqual(self.client.get(reverse("buoi_chi_tiet", args=[b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("buoi_huy", args=[b.pk]), {"ly_do_huy": "GIA_SU_HUY"}).status_code, 404)
        with self.assertRaises(ValidationError):
            dv.tao_buoi_chinh_thuc(self.gs2, self.khoa, ngay_mai(8))

    def test_nvts_khong_vao_trang_buoi_cua_gia_su(self):
        self.dang_nhap(self.nvts)
        self.assertEqual(self.client.get(reverse("buoi_cua_toi")).status_code, 403)
