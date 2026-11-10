"""Bước 4d – Tuyển sinh › Học viên: tình trạng suy ra, tab, Tôi phụ trách, sửa thông tin trong hộp thoại."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from core.models import HocVien, KhoaHoc, MonHoc, User, YeuCauHocTap
from core.services import hoc_vien as dv

MK = "MatKhau@Manh123"
YC = YeuCauHocTap.TrangThai


class HocVienTest(TestCase):
    def setUp(self):
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS Lan")
        self.gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS An")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.a = self.hv("Trần Gia Bảo", self.ts)
        self.b = self.hv("Võ Khánh Linh")
        self.c = self.hv("Mai Thanh Tâm")
        yc_a = self.yc(self.a, YC.CHINH_THUC, gia_su=self.gs)
        KhoaHoc.objects.create(yeu_cau=yc_a, hoc_vien=self.a, gia_su=self.gs, so_buoi_dang_ky=10, hoc_phi_moi_buoi=200000,
                               thu_lao_moi_buoi=150000, tao_boi=self.ts)
        self.yc(self.a, YC.DONG)
        self.yc(self.b, YC.DANG_TIM)
        self.yc(self.c, YC.DONG)
        self.client.force_login(self.ts)

    def hv(self, ten, pt=None):
        return HocVien.objects.create(ho_ten=ten, ten_phu_huynh="PH " + ten, sdt_phu_huynh="84905111222",
                                      tuyen_sinh_phu_trach=pt)

    def yc(self, hv, tt, gia_su=None):
        return YeuCauHocTap.objects.create(hoc_vien=hv, mon_hoc=self.toan, trinh_do="Lớp 8", muc_tieu="x",
                                           trang_thai=tt, gia_su=gia_su, tao_boi=self.ts)

    def test_tinh_trang_uu_tien_khoa_dang_hoc(self):
        d = {x["hv"].pk: x["tt"][0] for x in dv.ds_hoc_vien()}
        self.assertEqual(d, {self.a.pk: "dang_hoc", self.b.pk: "dang_tim", self.c.pk: "ket_thuc"})

    def test_tab_va_toi_phu_trach(self):
        url = reverse("hoc_vien_danh_sach")
        r = self.client.get(url, {"tinh_trang": "dang_tim"})
        self.assertEqual([x["hv"] for x in r.context["trang"]], [self.b])
        r = self.client.get(url, {"toi": "1"})
        self.assertEqual([x["hv"] for x in r.context["trang"]], [self.a])
        r = self.client.get(url, {"q": "0905 111 222"})
        self.assertEqual(r.context["trang"].paginator.count, 3)

    def test_chi_tiet_chuyen_ve_danh_sach_va_sua(self):
        url = reverse("hoc_vien_chi_tiet", args=[self.b.pk])
        r = self.client.get(url)
        self.assertRedirects(r, reverse("hoc_vien_danh_sach") + f"?chon={self.b.pk}", fetch_redirect_response=False)
        r = self.client.get(r.url)
        self.assertEqual(r.context["chon"]["hv"], self.b)
        self.assertContains(r, "0905 111 222")
        r = self.client.post(url, {"hv-ho_ten": "Võ Khánh Linh", "hv-ten_phu_huynh": "Chị Lan", "hv-sdt_phu_huynh": "abc"})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.context["mo_sua"])
        r = self.client.post(url, {"hv-ho_ten": "Võ Khánh Linh", "hv-ten_phu_huynh": "Chị Lan",
                                   "hv-sdt_phu_huynh": "0905 333 444"})
        self.assertEqual(r.status_code, 302)
        self.b.refresh_from_db()
        self.assertEqual(self.b.sdt_phu_huynh, "84905333444")
