"""Bước 5d – Đối soát thù lao (SD-30/31): chốt cả tháng, đánh dấu chi trả, màn mới."""

from django.core.exceptions import ValidationError
from django.urls import reverse

from core.models import DoiSoatThang, ThuLao, User
from core.services import buoi_hoc as dv_buoi
from core.services import thu_lao as dv
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, MK, DuLieu, ngay_mai


class DoiSoatV2Test(DuLieu):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        dv_buoi.xac_nhan_hoan_tat(self.gs, b, DANH_GIA)
        self.thang = ThuLao.objects.get().thang

    def test_chot_thang_can_kiem_tra_het_roi_chi_tra(self):
        with self.assertRaisesMessage(ValidationError, "kiểm tra hết"):
            dv.chot_thang(self.admin, self.thang)
        dv.kiem_tra(self.nvts, self.gs, self.thang)
        self.assertEqual(dv.trang_thai_ca_thang(self.thang), "DA_KIEM_TRA")
        with self.assertRaises(ValidationError):  # chưa chốt thì chưa chi trả
            dv.danh_dau_chi_tra(self.admin, self.thang, "UNC-1")
        da, bo = dv.chot_thang(self.admin, self.thang)
        self.assertEqual((len(da), bo), (1, []))
        self.assertEqual(ThuLao.objects.get().trang_thai, ThuLao.TrangThai.DA_DOI_SOAT)
        with self.assertRaises(ValidationError):
            dv.danh_dau_chi_tra(self.admin, self.thang, "")
        self.assertEqual(dv.danh_dau_chi_tra(self.admin, self.thang, "UNC-1"), 1)
        self.assertEqual(DoiSoatThang.objects.get().trang_thai, "DA_CHI_TRA")
        self.assertEqual(dv.trang_thai_ca_thang(self.thang), "DA_CHI_TRA")

    def test_man_hinh_ts_kiem_tra_qtv_chot(self):
        q = {"thang": f"{self.thang:%Y-%m}"}
        self.client.force_login(self.nvts)
        r = self.client.get(reverse("doi_soat"), q)
        self.assertContains(r, "Đánh dấu kiểm tra")
        self.assertNotContains(r, "Chốt tháng")
        self.client.post(reverse("doi_soat_kiem_tra", args=[self.gs.pk]), q)
        self.assertEqual(self.client.post(reverse("doi_soat_chot_thang"), q).status_code, 403)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("doi_soat"), q)
        self.assertTrue(r.context["chot_duoc"])
        self.client.post(reverse("doi_soat_chot_thang"), q)
        r = self.client.get(reverse("doi_soat"), q)
        self.assertTrue(r.context["chi_tra_duoc"])
        self.client.post(reverse("doi_soat_chi_tra"), {**q, "chung_tu": "UNC-9"})
        self.assertContains(self.client.get(reverse("doi_soat"), q), "UNC-9")
        self.assertRedirects(self.client.get(reverse("doi_soat_gia_su", args=[self.gs.pk]), q),
                             reverse("doi_soat") + f"?thang={self.thang:%Y-%m}")
