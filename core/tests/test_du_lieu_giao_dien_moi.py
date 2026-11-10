"""Kiểm thử tầng dữ liệu cho UI mới (thiết kế luồng 02 · migration 0016–0018) và SD-11 (4 kết quả học thử)."""

from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import (BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, LichRanh, LoiMoi, MinhChung, MonGiaSu, MonHoc,
                         NhacViec, NhatKy, ThongBao, User, YeuCauHocTap)
from core.services import khoa_hoc as dv
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import danh_dau_da_doc, ds_chua_doc, thong_bao, thong_bao_quan_tri

MK = "MatKhau@Manh123"
YC, KQ = YeuCauHocTap.TrangThai, YeuCauHocTap.KetQuaHocThu


class DuLieu(TestCase):
    def setUp(self):
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS")
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS",
                                           email="gs@test.local")
        self.hs = HoSoGiaSu.objects.create(user=self.gs, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG)
        MonGiaSu.objects.create(ho_so=self.hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        self.hv = HocVien.objects.create(ho_ten="HV", ten_phu_huynh="PH", sdt_phu_huynh="84905123456")
        self.yc = YeuCauHocTap.objects.create(
            hoc_vien=self.hv, mon_hoc=self.toan, trinh_do="Lớp 9", muc_tieu="Thi 10", lich_mong_muon="Tối",
            trang_thai=YC.DA_PHAN_CONG, gia_su=self.gs, phan_cong_luc=timezone.now(), tao_boi=self.ts)

    def buoi_thu_hoan_tat(self):
        return BuoiHoc.objects.create(loai=BuoiHoc.Loai.HOC_THU, yeu_cau=self.yc, gia_su=self.gs, hoc_vien=self.hv,
                                      bat_dau=timezone.now() - timedelta(days=1), trang_thai=BuoiHoc.TrangThai.HOAN_TAT)


class CotMoiTest(DuLieu):
    def test_KH10_mo_khoa_sinh_ma_lop(self):
        khoa = KhoaHoc.objects.create(yeu_cau=self.yc, hoc_vien=self.hv, gia_su=self.gs, so_buoi_dang_ky=10,
                                      hoc_phi_moi_buoi=200_000, thu_lao_moi_buoi=120_000)
        self.assertEqual(khoa.ma_lop, khoa.ma)
        self.assertEqual(KhoaHoc.objects.get(pk=khoa.pk).ma_lop, khoa.ma)

    def test_ket_thuc_luc_tinh_khi_luu(self):
        bd = timezone.now() + timedelta(days=1)
        b = BuoiHoc.objects.create(loai=BuoiHoc.Loai.HOC_THU, yeu_cau=self.yc, gia_su=self.gs, hoc_vien=self.hv,
                                   bat_dau=bd, thoi_luong_phut=90)
        self.assertEqual(b.ket_thuc_luc, bd + timedelta(minutes=90))

    def test_trang_thai_hien_thi_suy_ra(self):
        now = timezone.now()
        b = BuoiHoc(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH, bat_dau=now + timedelta(hours=1), thoi_luong_phut=60)
        self.assertEqual(b.trang_thai_hien_thi[0], "sap_dien_ra")
        b.bat_dau = now - timedelta(minutes=30)
        self.assertEqual(b.trang_thai_hien_thi[0], "dang_hoc")
        b.bat_dau, b.han_xac_nhan = now - timedelta(hours=2), now + timedelta(hours=10)
        self.assertEqual(b.trang_thai_hien_thi, ("cho_xac_nhan", "Chờ xác nhận"))
        b.han_xac_nhan = now + timedelta(hours=1)
        self.assertEqual(b.trang_thai_hien_thi[0], "sap_tu_huy")
        b.trang_thai, b.ly_do_huy = BuoiHoc.TrangThai.DA_HUY, BuoiHoc.LyDoHuy.QUA_HAN
        self.assertEqual(b.trang_thai_hien_thi, ("tu_huy", "Tự hủy"))

    def test_tam_nghi_va_trang_thai_tai_khoan(self):
        self.hs.tam_nghi_den = date.today() + timedelta(days=3)
        self.assertTrue(self.hs.dang_tam_nghi)
        self.assertEqual(self.gs.trang_thai_tai_khoan, "Chưa đăng nhập")
        self.gs.is_active = False
        self.assertEqual(self.gs.trang_thai_tai_khoan, "Đã khóa")

    def test_HS01_lich_ranh_mot_khung_moi_thu(self):
        LichRanh.objects.create(ho_so=self.hs, thu=0, khung="TOI", tu_gio=time(19), den_gio=time(21))
        with self.assertRaises(IntegrityError), transaction.atomic():
            LichRanh.objects.create(ho_so=self.hs, thu=0, khung="TOI", tu_gio=time(19), den_gio=time(21))
        self.assertEqual(LichRanh.khung_cua_gio(time(18), time(21)), "TOI")

    def test_minh_chung_phai_co_tep_hoac_link(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MinhChung.objects.create(ho_so=self.hs, loai="THE_SV", kieu="LINK", url="")
        MinhChung.objects.create(ho_so=self.hs, loai="THE_SV", kieu="LINK", url="https://drive.google.com/x")

    def test_nhan_moi_dung_theo_ui(self):
        self.assertEqual(YC.DANG_TIM.label, "Đang mời gia sư")
        self.assertEqual(LoiMoi.TrangThai.CHO.label, "Đang chờ")
        self.assertEqual(User.VaiTro.ADMIN.label, "Quản trị viên")


class NhatKyThongBaoTest(DuLieu):
    def test_ghi_nhat_ky_tu_nhan_ma(self):
        nk = ghi_nhat_ky(self.ts, "Thử", "YC-0012 Học viên A")
        self.assertEqual((nk.ma_doi_tuong, nk.loai_doi_tuong), ("YC-0012", NhatKy.LoaiDoiTuong.YEU_CAU))
        nk = ghi_nhat_ky(self.ts, "Thử", "BH-00398", cu={"a": 1}, moi={"a": 2})
        self.assertEqual((nk.loai_doi_tuong, nk.gia_tri_moi), (NhatKy.LoaiDoiTuong.BUOI_HOC, {"a": 2}))

    def test_thong_bao_chuong(self):
        thong_bao(self.gs, "Có lời mời mới", url="/loi-moi/")
        thong_bao_quan_tri("Hồ sơ mới chờ duyệt")
        self.assertEqual(ds_chua_doc(self.gs).count(), 1)
        self.assertEqual(ThongBao.objects.filter(nguoi_nhan=self.ad).count(), 1)
        self.assertEqual(danh_dau_da_doc(self.gs), 1)
        self.assertEqual(ds_chua_doc(self.gs).count(), 0)


class KetQuaHocThuTest(DuLieu):
    def test_KH04_dong_y(self):
        self.buoi_thu_hoan_tat()
        dv.ghi_ket_qua_hoc_thu(self.ts, self.yc, KQ.DONG_Y)
        self.assertEqual(self.yc.trang_thai, YC.HOC_THU_XONG)
        self.assertTrue(dv.co_the_tao_khoa(self.yc))

    def test_KH05_can_them_thoi_gian_tao_nhac_va_ghi_lai_duoc(self):
        self.buoi_thu_hoan_tat()
        dv.ghi_ket_qua_hoc_thu(self.ts, self.yc, KQ.CAN_THEM_THOI_GIAN, "PH hẹn cuối tuần")
        self.assertEqual(self.yc.trang_thai, YC.DA_PHAN_CONG)
        self.assertIsNotNone(self.yc.nhac_goi_lai_luc)
        nv = NhacViec.objects.get(yeu_cau=self.yc)
        self.assertEqual((nv.loai, nv.nguoi_phu_trach), (NhacViec.Loai.GOI_LAI_PHU_HUYNH, self.ts))
        self.assertAlmostEqual((nv.han_luc - timezone.now()).total_seconds(), 2 * 86400, delta=60)
        # Gọi lại được → ghi kết quả lần nữa, nhắc cũ xong.
        dv.ghi_ket_qua_hoc_thu(self.ts, self.yc, KQ.DONG_Y)
        nv.refresh_from_db()
        self.assertIsNotNone(nv.xong_luc)
        self.assertEqual(self.yc.trang_thai, YC.HOC_THU_XONG)

    def test_KH07_khong_dang_ky_thieu_ghi_chu_bi_chan(self):
        self.buoi_thu_hoan_tat()
        with self.assertRaises(ValidationError):
            dv.ghi_ket_qua_hoc_thu(self.ts, self.yc, KQ.KHONG_DANG_KY, "")

    def test_khong_dang_ky_dong_yeu_cau_va_vo_hieu_loi_moi(self):
        self.buoi_thu_hoan_tat()
        gs2 = User.objects.create_user("gs2", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS2")
        lm = LoiMoi.objects.create(yeu_cau=self.yc, gia_su=gs2)
        dv.ghi_ket_qua_hoc_thu(self.ts, self.yc, KQ.KHONG_DANG_KY, "Chuyển nhà")
        self.assertEqual(self.yc.trang_thai, YC.DONG)
        self.assertIn("Không đăng ký sau học thử", self.yc.ly_do_dong)
        lm.refresh_from_db()
        self.assertEqual(lm.trang_thai, LoiMoi.TrangThai.VOIDED)
