"""Kiểm thử PB-01 (tài khoản, xác thực, phân quyền), PB-23 (nhật ký), PB-24 (kiểm soát truy cập).

Tên test ghi rõ mã yêu cầu để đối chiếu với RTM khi viết báo cáo kiểm thử.
"""

from django.test import TestCase
from django.urls import reverse

from core.models import HoSoGiaSu, NhatKy, User

MK = "MatKhau@Manh123"


def tao_user(username, vai_tro, **kw):
    kw.setdefault("email", f"{username}@test.local")
    return User.objects.create_user(username=username, password=MK, vai_tro=vai_tro, ho_ten=username, **kw)


class PB01DangNhapTest(TestCase):
    def setUp(self):
        self.gs = tao_user("gs", User.VaiTro.GIA_SU)

    def test_PB01_chua_dang_nhap_bi_chuyen_ve_trang_dang_nhap(self):
        r = self.client.get(reverse("trang_chu"))
        self.assertRedirects(r, f"{reverse('dang_nhap')}?next=/")

    def test_PB01_dang_nhap_dung_vao_duoc_trang_chu(self):
        r = self.client.post(reverse("dang_nhap"), {"username": "gs", "password": MK})
        self.assertRedirects(r, reverse("trang_chu"))

    def test_PB01_sai_mat_khau_bi_tu_choi(self):
        r = self.client.post(reverse("dang_nhap"), {"username": "gs", "password": "sai"})
        self.assertContains(r, "Email hoặc mật khẩu chưa đúng")

    def test_PB01_tai_khoan_bi_khoa_khong_dang_nhap_duoc(self):
        self.gs.is_active = False
        self.gs.save()
        r = self.client.post(reverse("dang_nhap"), {"username": "gs", "password": MK})
        self.assertContains(r, "Tài khoản đã bị khóa")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_PB01_bi_khoa_khi_dang_dang_nhap_thi_bi_dang_xuat(self):
        self.client.login(username="gs", password=MK)
        self.assertEqual(self.client.get(reverse("trang_chu")).status_code, 200)
        User.objects.filter(pk=self.gs.pk).update(is_active=False)
        r = self.client.get(reverse("trang_chu"))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class PB01PhanQuyenTest(TestCase):
    def setUp(self):
        self.admin = tao_user("ad", User.VaiTro.ADMIN)
        self.ts = tao_user("ts", User.VaiTro.TUYEN_SINH)
        self.gs = tao_user("gs", User.VaiTro.GIA_SU)

    def test_PB24_chi_admin_vao_duoc_quan_ly_tai_khoan(self):
        for username, ma in [("ad", 200), ("ts", 403), ("gs", 403)]:
            self.client.login(username=username, password=MK)
            self.assertEqual(self.client.get(reverse("tai_khoan_danh_sach")).status_code, ma, username)
            self.assertEqual(self.client.get(reverse("nhat_ky")).status_code, ma, username)
            self.client.logout()

    def test_PB24_nguoi_khong_phai_admin_khong_khoa_duoc_tai_khoan(self):
        self.client.login(username="ts", password=MK)
        r = self.client.post(reverse("tai_khoan_doi_trang_thai", args=[self.gs.pk]))
        self.assertEqual(r.status_code, 403)
        self.gs.refresh_from_db()
        self.assertTrue(self.gs.is_active)

    def test_PB01_moi_vai_tro_thay_trang_chu_rieng(self):
        for username, chu in [("ad", "Tài khoản bị khóa"), ("ts", "Đang mời gia sư"), ("gs", "Lời mời đang chờ")]:
            self.client.login(username=username, password=MK)
            self.assertContains(self.client.get(reverse("trang_chu")), chu)
            self.client.logout()


class PB01QuanLyTaiKhoanTest(TestCase):
    def setUp(self):
        self.admin = tao_user("ad", User.VaiTro.ADMIN)
        self.client.login(username="ad", password=MK)

    def _tao(self, **kw):
        data = {"username": "moi", "ho_ten": "Người Mới", "email": "moi@test.local",
                "so_dien_thoai": "", "vai_tro": User.VaiTro.GIA_SU,
                "mat_khau": MK, "nhap_lai_mat_khau": MK}
        data.update(kw)
        return self.client.post(reverse("tai_khoan_tao"), data)

    def test_PB01_admin_tao_gia_su_co_ho_so_va_nhat_ky(self):
        r = self._tao()
        self.assertRedirects(r, reverse("tai_khoan_danh_sach"))
        u = User.objects.get(username="moi")
        self.assertTrue(u.check_password(MK))
        self.assertTrue(HoSoGiaSu.objects.filter(user=u).exists())
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Tạo tài khoản", doi_tuong="moi").exists())

    def test_PB01_ten_dang_nhap_la_duy_nhat(self):
        self._tao()
        r = self._tao(email="khac@test.local")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(username="moi").count(), 1)

    def test_PB01_gia_su_bat_buoc_co_email(self):
        r = self._tao(email="")
        self.assertContains(r, "Gia sư bắt buộc có email")

    def test_PB23_khoa_va_mo_khoa_co_ghi_nhat_ky(self):
        gs = tao_user("gs", User.VaiTro.GIA_SU)
        url = reverse("tai_khoan_doi_trang_thai", args=[gs.pk])
        self.client.post(url)
        gs.refresh_from_db()
        self.assertFalse(gs.is_active)
        self.client.post(url)
        gs.refresh_from_db()
        self.assertTrue(gs.is_active)
        self.assertEqual(
            list(NhatKy.objects.filter(doi_tuong="gs").order_by("thoi_diem").values_list("hanh_dong", flat=True)),
            ["Khóa tài khoản", "Mở khóa tài khoản"],
        )

    def test_PB01_admin_khong_tu_khoa_chinh_minh(self):
        self.client.post(reverse("tai_khoan_doi_trang_thai", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_PB23_doi_vai_tro_co_ghi_nhat_ky(self):
        ts = tao_user("ts", User.VaiTro.TUYEN_SINH)
        self.client.post(reverse("tai_khoan_sua", args=[ts.pk]), {
            "ho_ten": "ts", "email": "ts@test.local", "so_dien_thoai": "", "vai_tro": User.VaiTro.GIA_SU,
        })
        ts.refresh_from_db()
        self.assertEqual(ts.vai_tro, User.VaiTro.GIA_SU)
        self.assertTrue(HoSoGiaSu.objects.filter(user=ts).exists())
        nk = NhatKy.objects.get(hanh_dong="Sửa tài khoản")
        self.assertIn("Tuyển sinh → Gia sư", nk.chi_tiet)


class SuaLoiCodeReviewTaiKhoanTest(TestCase):
    def test_PB24_khoa_tai_khoan_khong_chuyen_huong_ra_trang_ngoai(self):
        admin = tao_user("ad", User.VaiTro.ADMIN)
        gs = tao_user("gs", User.VaiTro.GIA_SU)
        self.client.login(username="ad", password=MK)
        r = self.client.post(reverse("tai_khoan_doi_trang_thai", args=[gs.pk]),
                             {"next": "https://trang-gia-mao.example/dang-nhap"})
        self.assertRedirects(r, reverse("tai_khoan_danh_sach"))
        r = self.client.post(reverse("tai_khoan_doi_trang_thai", args=[gs.pk]), {"next": "/tai-khoan/?q=gs"})
        self.assertRedirects(r, "/tai-khoan/?q=gs")
