"""Kiểm thử Phần 6 – thu nhập gia sư, đối soát (NVTS kiểm tra → Admin chốt), dashboard Admin."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from core.integrations import zoom
from core.integrations.zoom import NguoiThamGia
from core.models import DoiSoatThang, ThuLao, User
from core.services import buoi_hoc as dv_buoi
from core.services import thu_lao as dv
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, MK, DuLieu, ngay_mai

TL = ThuLao.TrangThai


class ThuLaoTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        dv_buoi.xac_nhan_hoan_tat(self.gs, self.b, DANH_GIA)
        self.b.refresh_from_db()
        self.thang = ThuLao.objects.get().thang

    def test_tong_thang_tinh_ca_dieu_chinh_am(self):
        dv.them_dieu_chinh(self.nvts, self.gs, self.thang, -20_000, "Đi muộn 15 phút")
        (d,) = dv.tong_hop(self.thang)
        self.assertEqual((d.so_buoi, d.tam_tinh, d.dieu_chinh, d.tong), (1, 120_000, -20_000, 100_000))

    def test_tam_giu_khong_tinh_va_chan_kiem_tra(self):
        zoom._fake_singleton.kich_ban_tham_gia[self.b.zoom_meeting_id] = [
            NguoiThamGia("GS", "", self.b.bat_dau, self.b.bat_dau + timedelta(minutes=60), la_host=True)]
        dv_buoi.hau_kiem()
        from core.services import hau_kiem as dv_hk
        self.b.refresh_from_db()
        dv_hk.ket_luan(self.nvts, self.b.hau_kiem, "CO_VAN_DE", "THIEU_GIO", "Học viên không vào lớp")
        (d,) = dv.tong_hop(self.thang)
        self.assertEqual((d.tong, d.tam_giu, d.so_tam_giu), (0, 120_000, 1))
        with self.assertRaisesMessage(ValidationError, "tạm giữ"):
            dv.kiem_tra(self.nvts, self.gs, self.thang)

    def test_kiem_soat_hai_nguoi_va_khong_chot_hai_lan(self):
        with self.assertRaisesMessage(ValidationError, "chưa kiểm tra"):
            dv.chot(self.admin, self.gs, self.thang)
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        dv.chot(self.admin, self.gs, self.thang)
        self.assertEqual(ThuLao.objects.get().trang_thai, TL.DA_DOI_SOAT)
        self.assertEqual(DoiSoatThang.objects.get().trang_thai, DoiSoatThang.TrangThai.DA_CHOT)
        with self.assertRaisesMessage(ValidationError, "đã chốt"):
            dv.chot(self.admin, self.gs, self.thang)

    def test_so_lieu_doi_sau_kiem_tra_thi_phai_kiem_tra_lai(self):
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        dv.them_dieu_chinh(self.admin, self.gs, self.thang, 50_000, "Thưởng chuyên cần")
        with self.assertRaisesMessage(ValidationError, "chưa kiểm tra"):
            dv.chot(self.admin, self.gs, self.thang)

    def test_thang_da_chot_khoa_so(self):
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        dv.chot(self.admin, self.gs, self.thang)
        with self.assertRaisesMessage(ValidationError, "đã chốt"):
            dv.them_dieu_chinh(self.nvts, self.gs, self.thang, -10_000, "Sửa sai")
        # Buổi muộn của tháng đã chốt được ghi sang tháng mở kế tiếp.
        self.assertEqual(dv.thang_ghi_nhan(self.gs, self.thang), dv.thang_sau(self.thang))

    def test_nvts_khong_chot_duoc_qua_giao_dien(self):
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("doi_soat_chot", args=[self.gs.pk]), {"thang": f"{self.thang:%Y-%m}"})
        self.assertEqual(r.status_code, 403)

    def test_gia_su_chi_xem_thu_nhap_cua_minh(self):
        self.dang_nhap(self.gs2)
        r = self.client.get(reverse("thu_nhap"), {"thang": f"{self.thang:%Y-%m}"})
        self.assertNotContains(r, self.b.ma)
        self.assertEqual(self.client.get(reverse("doi_soat")).status_code, 403)
        self.dang_nhap(self.gs)
        self.assertContains(self.client.get(reverse("thu_nhap"), {"thang": f"{self.thang:%Y-%m}"}), self.b.ma)

    def test_xuat_csv(self):
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("doi_soat_csv"), {"thang": f"{self.thang:%Y-%m}"})
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Gia Sư A", r.content.decode("utf-8-sig"))

    def test_dashboard_admin_hien_thang_cho_chot(self):
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        self.dang_nhap(self.admin)
        r = self.client.get(reverse("trang_chu"))
        self.assertContains(r, "Thù lao chờ chốt")
        self.assertContains(r, "Gia Sư A")
