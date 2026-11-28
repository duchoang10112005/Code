"""Bước 4d – Danh sách gia sư cho Tuyển sinh; Admin tạo tài khoản gia sư (thay cho link mời)."""

from django.test import TestCase
from django.urls import reverse

from core.models import HoSoGiaSu, MonGiaSu, MonHoc, ThongBao, User

MK = "MatKhau@Manh123"


class AdminTaoGiaSuTest(TestCase):
    """Admin tạo tài khoản gia sư (sau phỏng vấn) kèm môn được duyệt sẵn và NV tuyển sinh phụ trách; không còn link mời / tự đăng ký."""

    def setUp(self):
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS Lan")
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")
        self.mon = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.url = reverse("tai_khoan_tao")
        self.du_lieu = {"ho_ten": "Nguyễn Văn Mới", "email": "moi@x.vn", "so_dien_thoai": "0905111222",
                        "vai_tro": "GIA_SU", "username": "", "tuyen_sinh_phu_trach": self.ts.pk, "mon_day": [self.mon.pk]}

    def test_tao_gia_su_hoat_dong_co_mon_duyet_san(self):
        self.client.force_login(self.ad)
        r = self.client.post(self.url, self.du_lieu)
        self.assertRedirects(r, reverse("tai_khoan_danh_sach"), fetch_redirect_response=False)
        hs = User.objects.get(email="moi@x.vn").ho_so_gia_su
        self.assertEqual(hs.trang_thai, HoSoGiaSu.TrangThai.HOAT_DONG)
        self.assertEqual(hs.nguoi_moi, self.ts)
        m = MonGiaSu.objects.get(ho_so=hs)
        self.assertEqual((m.mon_hoc, m.trang_thai, m.duyet_boi), (self.mon, MonGiaSu.TrangThai.DA_DUYET, self.ad))

    def test_gia_su_bat_buoc_co_ts_va_mon(self):
        self.client.force_login(self.ad)
        r = self.client.post(self.url, {**self.du_lieu, "tuyen_sinh_phu_trach": "", "mon_day": []})
        self.assertContains(r, "Chọn nhân viên tuyển sinh phụ trách")
        self.assertContains(r, "Chọn ít nhất một môn")
        self.assertFalse(User.objects.filter(email="moi@x.vn").exists())

    def test_tao_tuyen_sinh_khong_can_mon(self):
        self.client.force_login(self.ad)
        self.client.post(self.url, {"ho_ten": "TS Mới", "email": "ts2@x.vn", "vai_tro": "TUYEN_SINH", "username": ""})
        self.assertTrue(User.objects.filter(email="ts2@x.vn", vai_tro="TUYEN_SINH").exists())

    def test_khong_con_link_moi(self):
        from django.urls import NoReverseMatch
        for ten in ("api_ma_moi", "dang_ky_gia_su"):
            with self.assertRaises(NoReverseMatch):
                reverse(ten, args=["x"] if ten == "dang_ky_gia_su" else [])


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
        self.assertNotContains(r, "Mời gia sư đăng ký")
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
