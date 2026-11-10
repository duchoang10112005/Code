"""Bước 4d – Danh sách gia sư cho Tuyển sinh và mời gia sư đăng ký qua link (SD-04)."""

from django.test import TestCase
from django.urls import reverse

from core.models import HoSoGiaSu, MaMoiGiaSu, MonGiaSu, MonHoc, ThongBao, User

MK = "MatKhau@Manh123"


class MoiDangKyTest(TestCase):
    def setUp(self):
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS Lan")
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")

    def tao_link(self):
        self.client.force_login(self.ts)
        r = self.client.post(reverse("api_ma_moi"), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 200)
        self.client.logout()
        return r.json()["data"]

    def test_link_dung_lai_ma_dang_mo(self):
        a, b = self.tao_link(), self.tao_link()
        self.assertEqual(a["ma"], b["ma"])
        self.assertIn(reverse("dang_ky_gia_su", args=[a["ma"]]), a["url"])

    def test_gia_su_khong_tao_duoc_link(self):
        gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU)
        self.client.force_login(gs)
        self.assertEqual(self.client.post(reverse("api_ma_moi"), HTTP_X_REQUESTED_WITH="fetch").status_code, 403)

    def test_dang_ky_tao_ho_so_cho_duyet_nguoi_moi_la_ts(self):
        ma = self.tao_link()["ma"]
        url = reverse("dang_ky_gia_su", args=[ma])
        self.assertContains(self.client.get(url), "TS Lan")
        r = self.client.post(url, {"ho_ten": "Nguyễn Văn Mới", "email": "Moi@x.vn", "so_dien_thoai": "0905111222",
                                   "truong_hoc": "ĐHSP", "mat_khau": "Abcdefg1", "nhap_lai": "Abcdefg1"})
        self.assertRedirects(r, reverse("ho_so_cua_toi"), fetch_redirect_response=False)
        u = User.objects.get(email="moi@x.vn")
        self.assertEqual(u.vai_tro, User.VaiTro.GIA_SU)
        hs = u.ho_so_gia_su
        self.assertEqual(hs.trang_thai, HoSoGiaSu.TrangThai.CHO_DUYET)
        self.assertEqual(hs.nguoi_moi, self.ts)
        self.assertTrue(ThongBao.objects.filter(nguoi_nhan=self.ts).exists())
        self.assertTrue(ThongBao.objects.filter(nguoi_nhan=self.ad).exists())

    def test_email_trung_va_mat_khau_yeu(self):
        User.objects.create_user("cu", email="cu@x.vn", password=MK, vai_tro=User.VaiTro.GIA_SU)
        url = reverse("dang_ky_gia_su", args=[self.tao_link()["ma"]])
        r = self.client.post(url, {"ho_ten": "A", "email": "cu@x.vn", "so_dien_thoai": "09", "mat_khau": "abc",
                                   "nhap_lai": "abd"})
        self.assertContains(r, "Hai mật khẩu chưa khớp")
        self.assertContains(r, "ít nhất 8 ký tự")
        r = self.client.post(url, {"ho_ten": "A", "email": "cu@x.vn", "so_dien_thoai": "09", "mat_khau": "Abcdefg1",
                                   "nhap_lai": "Abcdefg1"})
        self.assertContains(r, "Email này đã có tài khoản")

    def test_link_dong_bao_het_hieu_luc(self):
        ma = self.tao_link()["ma"]
        MaMoiGiaSu.objects.filter(ma=ma).update(dang_mo=False)
        r = self.client.get(reverse("dang_ky_gia_su", args=[ma]))
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "hết hiệu lực", status_code=404)
        self.assertEqual(self.client.get(reverse("dang_ky_gia_su", args=["khongco"])).status_code, 404)


class DanhSachGiaSuTest(TestCase):
    def setUp(self):
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS Lan")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.a = User.objects.create_user("a", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS An")
        self.b = User.objects.create_user("b", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS Bình")
        self.hs_a = HoSoGiaSu.objects.create(user=self.a, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG, nguoi_moi=self.ts)
        self.hs_b = HoSoGiaSu.objects.create(user=self.b, trang_thai=HoSoGiaSu.TrangThai.CHO_DUYET)
        MonGiaSu.objects.create(ho_so=self.hs_a, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        self.client.force_login(self.ts)

    def test_tab_va_loc_toi_moi(self):
        url = reverse("gia_su_danh_sach")
        r = self.client.get(url)
        self.assertEqual(r.context["dem"][""], 2)
        self.assertEqual(r.context["dem"]["dang_nhan"], 1)
        self.assertEqual(r.context["dem"]["cho_duyet_hs"], 1)
        self.assertContains(r, "Mời gia sư đăng ký")
        r = self.client.get(url, {"tinh_trang": "cho_duyet_hs"})
        self.assertEqual([x["hs"] for x in r.context["dong"]], [self.hs_b])
        r = self.client.get(url, {"toi": "1"})
        self.assertEqual([x["hs"] for x in r.context["dong"]], [self.hs_a])

    def test_khung_ben_phai_theo_chon(self):
        r = self.client.get(reverse("gia_su_danh_sach"), {"chon": self.hs_a.pk})
        self.assertEqual(r.context["chon"]["hs"], self.hs_a)
        self.assertEqual(len(r.context["chon"]["luoi"]), 4)
        self.assertContains(r, "Người mời")


class HoSoGiaSuQtvTest(TestCase):
    """Bước 5c – QTV › Hồ sơ gia sư (SD-28): duyệt môn chọn cấp độ; Tuyển sinh chỉ xem."""

    def setUp(self):
        from core.models import CapDo
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS")
        gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS Mới")
        self.hs = HoSoGiaSu.objects.create(user=gs, trang_thai=HoSoGiaSu.TrangThai.CHO_DUYET)
        toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.c8 = CapDo.objects.create(mon_hoc=toan, ten="Lớp 8")
        self.c12 = CapDo.objects.create(mon_hoc=toan, ten="Lớp 12")
        self.mg = MonGiaSu.objects.create(ho_so=self.hs, mon_hoc=toan)
        self.mg.cap_do_duyet.set([self.c8, self.c12])

    def test_duyet_bot_cap_do_roi_kich_hoat(self):
        self.client.force_login(self.ad)
        url = reverse("gia_su_chi_tiet", args=[self.hs.pk])
        self.assertContains(self.client.get(url), "Duyệt môn Toán")
        self.client.post(reverse("gia_su_xu_ly_mon", args=[self.mg.pk]), {"hanh_dong": "duyet", "cap_do": [self.c8.pk]})
        self.mg.refresh_from_db()
        self.assertEqual((self.mg.trang_thai, list(self.mg.cap_do_duyet.all())), ("DA_DUYET", [self.c8]))
        self.assertContains(self.client.get(url), "Kích hoạt hồ sơ")

    def test_tuyen_sinh_chi_xem(self):
        self.client.force_login(self.ts)
        r = self.client.get(reverse("gia_su_chi_tiet", args=[self.hs.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Duyệt môn Toán")
