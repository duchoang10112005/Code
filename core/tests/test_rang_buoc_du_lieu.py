"""Kiểm thử các ràng buộc ở tầng database — lưới an toàn cho PB-12, PB-16, PB-22."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import (BuoiHoc, HocVien, KhoaHoc, LoiMoi, MonHoc, ThuLao, User,
                         YeuCauHocTap)
from core.services.tien_ich import chuan_hoa_sdt


class DuLieuMau(TestCase):
    def setUp(self):
        self.gs = User.objects.create_user("gs", password="x", vai_tro=User.VaiTro.GIA_SU, ho_ten="GS")
        self.hv = HocVien.objects.create(ho_ten="HV", ten_phu_huynh="PH", sdt_phu_huynh="84905123456")
        self.mon = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.yc = YeuCauHocTap.objects.create(
            hoc_vien=self.hv, mon_hoc=self.mon, trinh_do="Lớp 9", muc_tieu="Thi vào 10", lich_mong_muon="Tối T2"
        )
        self.kh = KhoaHoc.objects.create(
            yeu_cau=self.yc, hoc_vien=self.hv, gia_su=self.gs,
            so_buoi_dang_ky=2, hoc_phi_moi_buoi=200_000, thu_lao_moi_buoi=120_000,
        )

    def tao_buoi(self, **kw):
        kw.setdefault("loai", BuoiHoc.Loai.CHINH_THUC)
        kw.setdefault("khoa_hoc", self.kh)
        return BuoiHoc.objects.create(
            yeu_cau=self.yc, gia_su=self.gs, hoc_vien=self.hv,
            bat_dau=timezone.now() + timedelta(days=1), **kw,
        )


class RangBuocKhoaHocTest(DuLieuMau):
    def test_PB09_khoa_moi_co_da_dung_0_con_lai_bang_dang_ky(self):
        self.assertEqual(self.kh.so_buoi_da_dung, 0)
        self.assertEqual(self.kh.so_buoi_con_lai, 2)

    def test_PB12_database_chan_dung_vuot_so_buoi_dang_ky(self):
        self.kh.so_buoi_da_dung = 3
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.kh.save()

    def test_PB12_so_buoi_co_the_xep_tru_ca_buoi_dang_len_lich(self):
        self.tao_buoi(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH)
        self.assertEqual(self.kh.so_buoi_con_lai, 2)
        self.assertEqual(self.kh.so_buoi_co_the_xep, 1)
        self.tao_buoi(trang_thai=BuoiHoc.TrangThai.DA_HUY)  # buổi hủy không giữ chỗ
        self.assertEqual(self.kh.so_buoi_co_the_xep, 1)

    def test_buoi_chinh_thuc_bat_buoc_thuoc_khoa_hoc(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.tao_buoi(khoa_hoc=None)
        # Buổi học thử thì không cần khóa học
        self.tao_buoi(loai=BuoiHoc.Loai.HOC_THU, khoa_hoc=None)


class RangBuocThuLaoTest(DuLieuMau):
    def test_PB16_moi_buoi_chi_co_mot_ban_ghi_thu_lao(self):
        buoi = self.tao_buoi(trang_thai=BuoiHoc.TrangThai.HOAN_TAT)
        thang = timezone.localdate().replace(day=1)
        ThuLao.objects.create(buoi_hoc=buoi, gia_su=self.gs, thang=thang, so_tien=120_000)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ThuLao.objects.create(buoi_hoc=buoi, gia_su=self.gs, thang=thang, so_tien=120_000)


class RangBuocLoiMoiTest(DuLieuMau):
    def test_PB22_khong_gui_trung_loi_moi_dang_cho_cho_cung_gia_su(self):
        LoiMoi.objects.create(yeu_cau=self.yc, gia_su=self.gs)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LoiMoi.objects.create(yeu_cau=self.yc, gia_su=self.gs)

    def test_PB30_loi_moi_tu_dat_han_24h(self):
        lm = LoiMoi.objects.create(yeu_cau=self.yc, gia_su=self.gs)
        con = lm.het_han_luc - timezone.now()
        self.assertTrue(timedelta(hours=23, minutes=59) < con <= timedelta(hours=24))
        self.assertTrue(lm.con_hieu_luc)


class ChuanHoaSdtTest(TestCase):
    def test_chuan_hoa_sdt_ve_dinh_dang_zalo(self):
        self.assertEqual(chuan_hoa_sdt("0905 123 456"), "84905123456")
        self.assertEqual(chuan_hoa_sdt("+84 905.123.456"), "84905123456")
        self.assertIsNone(chuan_hoa_sdt("12345"))
