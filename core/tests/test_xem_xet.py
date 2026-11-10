"""Bước 5b – QTV › Cần xem xét (SD-32..34): hàng đợi hợp nhất, mở lại, từ chối, khôi phục từ nháp, lỗi hệ thống."""

from django.test import override_settings
from django.urls import path, reverse

from core.models import BanNhapDanhGia, BuoiHoc, DoiGiaSu, KhoaHoc, SuCoHeThong, YeuCauXuLy
from core.services import buoi_hoc as dv_buoi
from core.services import ngoai_le as dv_nl
from core.services import xem_xet as dv
from core.tests.test_pb33_ngoai_le import NgoaiLe
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, ngay_mai

TT = BuoiHoc.TrangThai
XL = YeuCauXuLy.TrangThai


def _view_loi(request, pk):
    raise RuntimeError("lỗi giả lập")


import config.urls as goc  # noqa: E402
urlpatterns = [path("buoi-hoc/<int:pk>/loi-gia/", _view_loi)] + goc.urlpatterns


class XemXetTest(NgoaiLe):
    def test_hang_doi_gop_nguon_va_tim_theo_ma(self):
        b2 = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        b = self.buoi_qua_han()
        yc = dv_nl.gui_yeu_cau_xu_ly(self.gs, b, "MO_LAI", "Em quên xác nhận, buổi vẫn dạy đủ giờ")
        dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU)
        ds, dem, _ = dv.hang_doi()
        self.assertEqual(dem["mo_lai"], 1)  # buổi có yêu cầu không hiện thêm dòng "tự hủy"
        self.assertEqual([x["loai"] for x in ds if x["tab"] == "mo_lai"], ["mo_lai"])
        ma_so = f"bh{b.pk}"
        ds, _, khong_co = dv.hang_doi(ma_so)
        self.assertEqual([x["obj"] for x in ds], [yc])
        b2.refresh_from_db()
        ds, _, khong_co = dv.hang_doi(b2.ma.lower().replace("-", ""))
        self.assertEqual((ds, khong_co), ([], b2))

    def test_mo_lai_tu_choi_qua_giao_dien(self):
        b = self.buoi_qua_han()
        yc = dv_nl.gui_yeu_cau_xu_ly(self.gs, b, "MO_LAI", "Em quên xác nhận, buổi vẫn dạy đủ giờ")
        self.dang_nhap(self.admin)
        r = self.client.get(reverse("xem_xet"))
        self.assertEqual(r.context["chon"]["obj"], yc)
        self.assertContains(r, "Mở lại · thêm 24 giờ")
        url = reverse("xem_xet_xu_ly", args=["mo_lai", yc.pk, "tu_choi"])
        self.client.post(url, {"ly_do": ""})
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, XL.CHO_XU_LY)  # thiếu ghi chú
        self.client.post(reverse("xem_xet_xu_ly", args=["mo_lai", yc.pk, "mo_lai"]), {"ly_do": "Zoom ghi đủ giờ"})
        yc.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((yc.trang_thai, b.trang_thai), (XL.DA_XU_LY, TT.DA_LEN_LICH))

    def test_mo_lai_buoi_tu_huy_khong_co_yeu_cau(self):
        b = self.buoi_qua_han()
        self.dang_nhap(self.admin)
        self.client.post(reverse("xem_xet_xu_ly", args=["tu_huy", b.pk, "mo_lai"]), {"ly_do": "Phụ huynh xác nhận"})
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, TT.DA_LEN_LICH)

    def test_loi_he_thong_ghi_su_co_gia_han_va_khoi_phuc_tu_nhap(self):
        b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        han_cu = b.han_xac_nhan
        dv_buoi.luu_nhap(self.gs, b, DANH_GIA)
        self.dang_nhap(self.gs)
        with override_settings(ROOT_URLCONF=__name__):
            r = self.client.post(f"/buoi-hoc/{b.pk}/loi-gia/", {"noi_dung": "x", "mat_khau": "bimat"})
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "đã ghi lại lỗi", status_code=500)
        sc = SuCoHeThong.objects.get()
        self.assertEqual(sc.du_lieu_form["mat_khau"], "***")
        yc = YeuCauXuLy.objects.get(loai="LOI_HE_THONG")
        b.refresh_from_db()
        self.assertGreater(b.han_xac_nhan, han_cu)
        dv.khoi_phuc_tu_nhap(self.admin, yc, "Lỗi máy chủ, nháp đủ")
        b.refresh_from_db()
        yc.refresh_from_db()
        self.khoa.refresh_from_db()
        self.assertEqual((b.trang_thai, yc.trang_thai, self.khoa.so_buoi_da_dung), (TT.HOAN_TAT, XL.DA_XU_LY, 1))

    def test_khoi_phuc_that_bai_khi_nhap_thieu(self):
        b = self.ve_qua_khu(dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        BanNhapDanhGia.objects.create(buoi_hoc=b, du_lieu={"noi_dung": "x"})
        yc = YeuCauXuLy.objects.create(loai="LOI_HE_THONG", buoi_hoc=b, nguoi_gui=self.gs)
        from django.core.exceptions import ValidationError
        with self.assertRaisesMessage(ValidationError, "chưa đủ 3 mục"):
            dv.khoi_phuc_tu_nhap(self.admin, yc, "x")

    def test_duyet_doi_gia_su_tren_trang_moi(self):
        dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.KHONG_PHU_HOP, gia_su_moi=self.gs2, da_dong_y=True)
        self.khoa.refresh_from_db()
        dn = dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU, gia_su_moi=self.gs,
                                      da_dong_y=True)
        self.dang_nhap(self.admin)
        r = self.client.get(reverse("xem_xet"), {"tab": "doi_gia_su"})
        self.assertContains(r, "Duyệt đổi gia sư")
        self.client.post(reverse("xem_xet_xu_ly", args=["doi_gia_su", dn.pk, "duyet"]), {"ly_do": ""})
        self.khoa.refresh_from_db()
        self.assertEqual((self.khoa.gia_su, self.khoa.trang_thai), (self.gs, KhoaHoc.TrangThai.DANG_HOC))
