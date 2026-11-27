"""Bước 4d – Khóa học: hoàn thành sớm (SD-23), gia hạn / sửa nhập nhầm (SD-24), đổi gia sư chọn sẵn (SD-25), màn mới."""

from django.core.exceptions import ValidationError
from django.urls import reverse

from core.models import BuoiHoc, DoiGiaSu, GiaHanKhoa, KhoaHoc, NhacViec, ThongBao, YeuCauHocTap
from core.services import buoi_hoc as dv_buoi
from core.services import khoa_hoc as dv_kh
from core.services import ngoai_le as dv_nl
from core.tests.test_pb33_ngoai_le import NgoaiLe
from core.tests.test_pb11_pb15_buoi_hoc import ngay_mai

KH = KhoaHoc.TrangThai
TT = BuoiHoc.TrangThai
YC = YeuCauHocTap.TrangThai


class TrangThaiKhoaV2Test(NgoaiLe):
    def test_hoan_thanh_som_huy_buoi_sap_toi_va_gia_han_mo_lai(self):
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        with self.assertRaises(ValidationError):
            dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HOAN_THANH, "")
        dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HOAN_THANH, "Đã đạt mục tiêu")
        self.khoa.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(self.khoa.trang_thai, KH.HOAN_THANH)
        self.assertIsNotNone(self.khoa.hoan_thanh_luc)
        self.assertEqual(b.trang_thai, TT.DA_HUY)
        # Gia hạn → học lại
        NhacViec.objects.create(nguoi_phu_trach=self.nvts, loai=NhacViec.Loai.HOI_GIA_HAN, khoa_hoc=self.khoa,
                                han_luc=b.bat_dau)
        cu = self.khoa.so_buoi_dang_ky
        dv_kh.gia_han(self.nvts, self.khoa, 4, "Phụ huynh đăng ký thêm")
        self.khoa.refresh_from_db()
        self.assertEqual((self.khoa.trang_thai, self.khoa.so_buoi_dang_ky), (KH.DANG_HOC, cu + 4))
        self.assertIsNone(self.khoa.hoan_thanh_luc)
        g = GiaHanKhoa.objects.get()
        self.assertEqual((g.loai, g.so_buoi_cu, g.so_buoi_moi), (GiaHanKhoa.Loai.GIA_HAN, cu, cu + 4))
        self.assertFalse(NhacViec.objects.filter(xong_luc__isnull=True).exists())

    def test_gia_han_kiem_tra_dau_vao(self):
        for so, ly_do in ((0, "x"), (3, ""), ("abc", "x")):
            with self.assertRaises(ValidationError):
                dv_kh.gia_han(self.nvts, self.khoa, so, ly_do)
        with self.assertRaises(ValidationError):  # học phí thấp hơn thù lao
            dv_kh.gia_han(self.nvts, self.khoa, 2, "x", hoc_phi_moi_buoi=1000)
        dv_kh.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HUY, "Chuyển nơi ở")
        with self.assertRaisesMessage(ValidationError, "Chỉ gia hạn"):
            dv_kh.gia_han(self.nvts, self.khoa, 2, "x")

    def test_qtv_sua_nhap_nham_ghi_lich_su(self):
        dv_nl.sua_so_buoi(self.admin, self.khoa, 5, "Nhập nhầm")
        self.assertEqual(GiaHanKhoa.objects.get().loai, GiaHanKhoa.Loai.SUA_NHAP_NHAM)

    def test_ts_gia_han_qua_man_hinh(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_gia_han", args=[self.khoa.pk]), {"so_buoi_them": "", "ly_do": ""})
        self.assertRedirects(r, reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk]) + "?mo=gia-han",
                             fetch_redirect_response=False)
        r = self.client.post(reverse("khoa_hoc_gia_han", args=[self.khoa.pk]), {"so_buoi_them": "3", "ly_do": "Thêm"})
        self.assertRedirects(r, reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk]), fetch_redirect_response=False)
        self.dang_nhap(self.admin)
        self.assertEqual(self.client.post(reverse("khoa_hoc_gia_han", args=[self.khoa.pk]),
                                          {"so_buoi_them": "3", "ly_do": "x"}).status_code, 403)


class DoiGiaSuV2Test(NgoaiLe):
    def test_chon_san_gia_su_moi_chuyen_buoi_da_xep(self):
        sap_toi = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        with self.assertRaises(ValidationError):  # chưa tick đồng ý
            dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU, gia_su_moi=self.gs2)
        with self.assertRaises(ValidationError):  # trùng gia sư cũ
            dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU, gia_su_moi=self.gs,
                                     da_dong_y=True)
        dn = dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU, gia_su_moi=self.gs2,
                                      thu_lao_moi=130000, da_dong_y=True)
        dn.refresh_from_db()
        self.assertEqual((dn.trang_thai, dn.so_buoi_chuyen), (DoiGiaSu.TrangThai.DA_THUC_HIEN, 1))
        self.khoa.refresh_from_db()
        self.yc.refresh_from_db()
        sap_toi.refresh_from_db()
        self.assertEqual((self.khoa.gia_su, self.khoa.trang_thai, self.khoa.thu_lao_moi_buoi), (self.gs2, KH.DANG_HOC, 130000))
        self.assertEqual((self.yc.gia_su, self.yc.trang_thai), (self.gs2, YC.CHINH_THUC))
        self.assertEqual((sap_toi.gia_su, sap_toi.trang_thai, sap_toi.thu_lao_du_kien), (self.gs2, TT.LOI_ZOOM if
                         sap_toi.trang_thai == TT.LOI_ZOOM else TT.DA_LEN_LICH, 130000))

    def test_buoi_trung_lich_gia_su_moi_bi_huy(self):
        b = dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        # Gia sư mới đã có buổi khác cùng giờ (lớp khác).
        yc2 = self.tao_yc(self.gs2)
        k2 = dv_kh.tao_khoa_hoc(self.nvts, yc2, {**{f: getattr(self.khoa, f) for f in (
            "so_buoi_dang_ky", "hoc_phi_moi_buoi", "thu_lao_moi_buoi", "thoi_luong_phut")}})
        BuoiHoc.objects.create(loai=BuoiHoc.Loai.CHINH_THUC, khoa_hoc=k2, yeu_cau=yc2, gia_su=self.gs2, hoc_vien=self.hv,
                               bat_dau=b.bat_dau, thoi_luong_phut=b.thoi_luong_phut, trang_thai=TT.DA_LEN_LICH)
        dn = dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.LICH_KHONG_KHOP, gia_su_moi=self.gs2,
                                      da_dong_y=True)
        dn.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((dn.so_buoi_chuyen, b.trang_thai, b.gia_su), (0, TT.DA_HUY, self.gs))

    def test_lan_hai_cho_qtv_duyet_roi_moi_chuyen(self):
        dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.PHU_HUYNH_YEU_CAU, gia_su_moi=self.gs2,
                                 da_dong_y=True)
        self.khoa.refresh_from_db()
        dn = dv_nl.de_nghi_doi_gia_su(self.nvts, self.khoa, DoiGiaSu.LyDo.KHONG_PHU_HOP, gia_su_moi=self.gs,
                                      da_dong_y=True)
        self.assertEqual(dn.trang_thai, DoiGiaSu.TrangThai.CHO_DUYET)
        self.assertTrue(ThongBao.objects.filter(nguoi_nhan=self.admin).exists())
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.gia_su, self.gs2)
        dv_nl.duyet_doi_gia_su(self.admin, dn, dong_y=True)
        self.khoa.refresh_from_db()
        self.assertEqual((self.khoa.gia_su, self.khoa.trang_thai), (self.gs, KH.DANG_HOC))

    def test_man_chi_tiet_va_danh_sach(self):
        dv_buoi.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai(8))
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["ho_so"].user for x in r.context["goi_y_gs"]], [self.gs2])
        self.assertEqual(r.context["tien_do"]["da_xep"], 1)
        self.assertContains(r, "Đánh dấu hoàn thành")
        r = self.client.post(reverse("khoa_hoc_doi_gia_su", args=[self.khoa.pk]),
                             {"gia_su_moi": self.gs2.pk, "ly_do": "PHU_HUYNH_YEU_CAU", "thu_lao_moi": "120000",
                              "da_dong_y": "1"})
        self.assertRedirects(r, reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk]), fetch_redirect_response=False)
        self.khoa.refresh_from_db()
        self.assertEqual(self.khoa.gia_su, self.gs2)
        r = self.client.get(reverse("khoa_hoc_danh_sach"), {"tinh_trang": "sap_het"})  # 2 buổi → sắp hết
        self.assertEqual([k.pk for k in r.context["trang"]], [self.khoa.pk])
        self.assertContains(r, self.khoa.ma)


class MoKhoaLichGoiYTest(NgoaiLe):
    """Hộp thoại Mở khóa: lịch điền sẵn từ khung phụ huynh mong muốn; lỗi thiếu giờ hiện rõ thay vì im lặng."""

    def yc_cho_mo_khoa(self):
        yc = self.tao_yc(self.gs2)
        YeuCauHocTap.objects.filter(pk=yc.pk).update(dang_ky_thang=True, khung_mong_muon=["1-TOI_SOM", "3-TOI_SOM", "5-SANG"])
        yc.refresh_from_db()
        return yc

    def test_lich_dien_san_tu_khung_mong_muon(self):
        from core.views.yeu_cau import _lich_goi_y
        yc = self.yc_cho_mo_khoa()
        self.assertEqual(_lich_goi_y(yc), {"lich_thu_1": "1", "lich_gio_1": "17:30", "lich_thu_2": "3",
                                           "lich_gio_2": "17:30", "lich_thu_3": "5", "lich_gio_3": "08:00"})
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("yeu_cau_chi_tiet", args=[yc.pk]))
        self.assertContains(r, 'name="lich_gio_1"')
        self.assertEqual(r.context["form_khoa"].initial["lich_gio_1"], "17:30")

    def test_thieu_gio_hien_thong_bao_loi(self):
        yc = self.yc_cho_mo_khoa()
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_tao", args=[yc.pk]), {
            "so_buoi_dang_ky": 10, "thoi_luong_phut": 90, "hoc_phi_moi_buoi": 200000, "thu_lao_moi_buoi": 150000,
            "lich_thu_1": "1", "lich_gio_1": ""})
        self.assertContains(r, "Chọn đủ thứ và giờ cho buổi cố định này.")
        self.assertFalse(KhoaHoc.objects.filter(yeu_cau=yc).exists())


class TimKiemYeuCauTest(NgoaiLe):
    """Ô tìm ở trang Yêu cầu học tập từng lỗi 500 (only + select_related)."""

    def test_tim_theo_ma_va_ten(self):
        yc = self.tao_yc(self.gs2)
        self.dang_nhap(self.nvts)
        for q in (f"YC-{yc.pk:04d}", f"yc{yc.pk}", yc.hoc_vien.ho_ten.split()[-1].lower()):
            r = self.client.get(reverse("yeu_cau_danh_sach"), {"q": q})
            self.assertEqual(r.status_code, 200, q)
            self.assertIn(yc, [d["yc"] for d in r.context["dong"]], q)
        r = self.client.get(reverse("yeu_cau_danh_sach"), {"q": "khongco999"})
        self.assertEqual(len(r.context["dong"]), 0)


class LocLoaiBuoiTest(NgoaiLe):
    """Trang Buổi học của gia sư có bộ lọc loại buổi (học thử / chính thức)."""

    def test_loc_hoc_thu(self):
        yc = self.tao_yc(self.gs2)
        self.dang_nhap(self.gs2)
        r = self.client.get(reverse("buoi_cua_toi"), {"loai": "HOC_THU"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(d["b"].loai == "HOC_THU" for d in r.context["ds"]))
        self.assertContains(r, 'name="loai"')
        r = self.client.get(reverse("buoi_cua_toi"), {"loai": "CHINH_THUC"})
        self.assertTrue(all(d["b"].loai == "CHINH_THUC" for d in r.context["ds"]))
