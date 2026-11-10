"""Bước 5f – Quét định kỳ (SD-36)."""

from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from core.integrations import zoom
from core.models import BuoiHoc, HoSoGiaSu, KhoaHoc, NhacViec, NhatKy, YeuCauXuLy
from core.services import buoi_hoc as dv_buoi
from core.services import dinh_ky as dv
from core.services import ngoai_le as dv_nl
from core.tests.test_pb33_ngoai_le import NgoaiLe
from core.tests.test_pb11_pb15_buoi_hoc import ngay_mai


class DinhKyTest(NgoaiLe):
    def test_mo_dong_phong(self):
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        dv.mo_dong_phong(b.bat_dau - timedelta(minutes=5))
        b.refresh_from_db()
        self.assertIsNotNone(b.phong_mo_luc)
        r = dv.mo_dong_phong(b.ket_thuc_luc + timedelta(minutes=6))
        b.refresh_from_db()
        self.assertEqual(r["dong_phong"], 1)
        self.assertIn(b.zoom_meeting_id, zoom._fake_singleton.phong_da_ket_thuc)
        self.assertEqual(dv.mo_dong_phong(b.ket_thuc_luc + timedelta(minutes=7))["dong_phong"], 0)  # không lặp

    def test_nhac_gia_han_va_tu_choi_mo_lai_qua_han(self):
        KhoaHoc.objects.filter(pk=self.khoa.pk).update(tuyen_sinh_phu_trach=self.nvts)
        self.assertEqual(dv.nhac_viec()["nhac_gia_han"], 1)  # khóa 2 buổi → sắp hết
        self.assertEqual(dv.nhac_viec()["nhac_gia_han"], 0)
        nv = NhacViec.objects.get()
        NhacViec.objects.filter(pk=nv.pk).update(han_luc=timezone.now() - timedelta(minutes=1))
        self.assertEqual(dv.nhac_viec()["bao_nhac_viec"], 1)
        self.assertEqual(dv.nhac_viec()["bao_nhac_viec"], 0)  # một lần mỗi ngày
        b = self.buoi_qua_han()
        yc = dv_nl.gui_yeu_cau_xu_ly(self.gs, b, "MO_LAI", "Em quên xác nhận, buổi vẫn dạy đủ")
        dv.nhac_viec(yc.han_xu_ly + timedelta(minutes=1))
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, YeuCauXuLy.TrangThai.TU_CHOI)

    def test_het_tam_nghi_va_lenh_quet(self):
        HoSoGiaSu.objects.filter(user=self.gs).update(tam_nghi_den=timezone.localdate() - timedelta(days=1))
        call_command("quet_dinh_ky", stdout=open("NUL" if __import__("os").name == "nt" else "/dev/null", "w"))
        self.assertIsNone(HoSoGiaSu.objects.get(user=self.gs).tam_nghi_den)
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Quét định kỳ").exists())
