"""Bước 2 – khung giao diện mới: SD-01 (đăng nhập), SD-02 (đổi mật khẩu bắt buộc), chuông thông báo, Ctrl+K (SD-35)."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, MonHoc, NhatKy, ThongBao, User, YeuCauHocTap
from core.services.thong_bao import thong_bao
from core.services.tim_kiem import chuan_hoa, tim

MK = "MatKhau@Manh123"


class DuLieu(TestCase):
    def setUp(self):
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Hoàng Văn Minh",
                                           email="minh@gso.vn", so_dien_thoai="0905100200")
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="Trần Thu Trang",
                                           email="trang@gso.vn")
        self.gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="Phạm Ngọc Lan",
                                           email="lan@gmail.com", so_dien_thoai="84912345678")
        self.gs2 = User.objects.create_user("gs2", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="Lê Nam")
        HoSoGiaSu.objects.create(user=self.gs)

    def dn(self, u):
        self.client.force_login(u)


class DangNhapTest(DuLieu):
    def test_TK01_dang_nhap_bang_email_va_sdt(self):
        for dinh_danh in ("lan@gmail.com", "LAN@gmail.com", "0912 345 678", "+84912345678", "gs"):
            self.client.logout()
            r = self.client.post(reverse("dang_nhap"), {"username": dinh_danh, "password": MK, "ghi_nho": "1"})
            self.assertRedirects(r, reverse("trang_chu"), fetch_redirect_response=False, msg_prefix=dinh_danh)

    def test_sai_mat_khau_bao_chung(self):
        r = self.client.post(reverse("dang_nhap"), {"username": "lan@gmail.com", "password": "sai"})
        self.assertContains(r, "Email hoặc mật khẩu chưa đúng")

    def test_TK02_bi_khoa_bao_kem_ly_do(self):
        User.objects.filter(pk=self.gs.pk).update(is_active=False, ly_do_khoa="Nghỉ dạy không báo trước")
        r = self.client.post(reverse("dang_nhap"), {"username": "lan@gmail.com", "password": MK})
        self.assertContains(r, "Tài khoản đã bị khóa")
        self.assertContains(r, "Nghỉ dạy không báo trước")
        # Sai mật khẩu thì KHÔNG lộ là tài khoản bị khóa.
        r = self.client.post(reverse("dang_nhap"), {"username": "lan@gmail.com", "password": "sai"})
        self.assertNotContains(r, "Nghỉ dạy")

    def test_khong_ghi_nho_thi_het_phien_khi_dong_trinh_duyet(self):
        self.client.post(reverse("dang_nhap"), {"username": "gs", "password": MK})
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.logout()
        self.client.post(reverse("dang_nhap"), {"username": "gs", "password": MK, "ghi_nho": "1"})
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_trang_dang_nhap_co_lien_he_qtv(self):
        r = self.client.get(reverse("dang_nhap"))
        self.assertContains(r, "Hoàng Văn Minh")
        self.assertContains(r, "Ghi nhớ đăng nhập")


class DoiMatKhauBatBuocTest(DuLieu):
    def setUp(self):
        super().setUp()
        User.objects.filter(pk=self.gs.pk).update(phai_doi_mat_khau=True)
        self.gs.refresh_from_db()
        self.dn(self.gs)

    def test_TK04_moi_trang_chuyen_ve_dat_mat_khau(self):
        for url in (reverse("trang_chu"), reverse("thu_nhap")):
            self.assertRedirects(self.client.get(url), reverse("doi_mat_khau") + "?bat_buoc=1",
                                 fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("api_thong_bao")).status_code, 403)
        self.assertContains(self.client.get(reverse("doi_mat_khau")), "Đặt mật khẩu mới")

    def test_mat_khau_yeu_hoac_trung_mat_khau_tam_bi_chan(self):
        for mk in ("abcdefgh1", "Abcdefgh", MK):
            r = self.client.post(reverse("doi_mat_khau"), {"new_password1": mk, "new_password2": mk})
            self.assertEqual(r.status_code, 200, mk)
        self.gs.refresh_from_db()
        self.assertTrue(self.gs.phai_doi_mat_khau)

    def test_doi_xong_tat_co_va_ghi_nhat_ky(self):
        r = self.client.post(reverse("doi_mat_khau"), {"new_password1": "MoiMoi2026x", "new_password2": "MoiMoi2026x"})
        self.assertRedirects(r, reverse("trang_chu"), fetch_redirect_response=False)
        self.gs.refresh_from_db()
        self.assertFalse(self.gs.phai_doi_mat_khau)
        self.assertTrue(self.gs.check_password("MoiMoi2026x"))
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Đổi mật khẩu", nguoi_thuc_hien=self.gs).exists())
        self.assertEqual(self.client.get(reverse("thu_nhap")).status_code, 200)  # vẫn đăng nhập


class KhungVaMenuTest(DuLieu):
    def test_menu_theo_vai_tro(self):
        self.dn(self.ts)
        r = self.client.get(reverse("doi_mat_khau"))
        self.assertContains(r, "Bảng điều phối")
        self.assertContains(r, "Yêu cầu học tập")
        self.assertContains(r, "Hậu kiểm buổi học")
        self.assertNotContains(r, "Nhật ký thao tác")
        self.dn(self.gs)
        r = self.client.get(reverse("doi_mat_khau"))
        self.assertContains(r, "Góc giảng dạy")
        self.assertContains(r, "Lời mời nhận lớp")
        self.assertNotContains(r, "Đối soát thù lao")

    def test_tu_doi_mat_khau_can_mat_khau_cu(self):
        self.dn(self.ts)
        r = self.client.post(reverse("doi_mat_khau"), {"old_password": "sai", "new_password1": "MoiMoi2026x",
                                                       "new_password2": "MoiMoi2026x"})
        self.assertContains(r, "Còn 1 mục cần sửa")


class ApiThongBaoTest(DuLieu):
    def test_chua_dang_nhap_401(self):
        self.assertEqual(self.client.get(reverse("api_thong_bao")).status_code, 401)

    def test_doc_va_danh_dau(self):
        thong_bao(self.gs, "Lời mời mới YC-0001", url="/loi-moi/")
        thong_bao(self.ts, "Không phải của gia sư")
        self.dn(self.gs)
        j = self.client.get(reverse("api_thong_bao")).json()
        self.assertTrue(j["ok"])
        self.assertEqual((j["data"]["chua_doc"], len(j["data"]["thong_bao"])), (1, 1))
        self.assertEqual(self.client.get(reverse("api_thong_bao_da_doc")).status_code, 405)
        j = self.client.post(reverse("api_thong_bao_da_doc"), {}, content_type="application/json").json()
        self.assertEqual(j["data"]["so"], 1)
        self.assertEqual(ThongBao.objects.filter(nguoi_nhan=self.ts, da_doc=False).count(), 1)


class TimKiemTest(DuLieu):
    def setUp(self):
        super().setUp()
        toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.hv = HocVien.objects.create(ho_ten="Trần Gia Bảo", ten_phu_huynh="Trần Văn Hải",
                                         sdt_phu_huynh="84905000111")
        self.yc = YeuCauHocTap.objects.create(hoc_vien=self.hv, mon_hoc=toan, trinh_do="Lớp 9", muc_tieu="x",
                                              lich_mong_muon="Tối", trang_thai="CHINH_THUC", gia_su=self.gs)
        self.khoa = KhoaHoc.objects.create(yeu_cau=self.yc, hoc_vien=self.hv, gia_su=self.gs, so_buoi_dang_ky=10,
                                           hoc_phi_moi_buoi=200_000, thu_lao_moi_buoi=120_000)
        self.buoi = BuoiHoc.objects.create(loai="CHINH_THUC", khoa_hoc=self.khoa, yeu_cau=self.yc, gia_su=self.gs,
                                           hoc_vien=self.hv, bat_dau=timezone.now() + timedelta(days=1))

    def test_chuan_hoa(self):
        self.assertEqual(chuan_hoa("BH-00399"), "bh00399")
        self.assertEqual(chuan_hoa("Gia Bảo"), "giabao")
        self.assertEqual(chuan_hoa("Đức"), "duc")

    def test_tim_theo_ma_va_ten_khong_dau(self):
        kq = tim(self.ts, f"bh{self.buoi.pk}")
        self.assertEqual(kq[0]["ten"], "Buổi học")
        kq = tim(self.ts, "gia bao")
        self.assertEqual({n["ten"] for n in kq}, {"Yêu cầu", "Khóa học", "Học viên"})
        self.assertTrue(any(n["ten"] == "Gia sư" for n in tim(self.ts, "ngoc lan")))

    def test_gia_su_chi_thay_lop_cua_minh(self):
        self.assertTrue(tim(self.gs, "gia bao"))
        self.assertEqual(tim(self.gs2, "gia bao"), [])
        self.assertEqual(tim(self.gs2, self.buoi.ma), [])
        self.assertEqual(tim(self.gs, self.yc.ma), [])  # gia sư không tra yêu cầu
        self.dn(self.gs)
        j = self.client.get(reverse("api_tim_kiem"), {"q": "Gia Bảo"}).json()
        self.assertNotIn("84905000111", str(j))  # không lộ SĐT phụ huynh

    def test_chi_qtv_tim_duoc_tai_khoan(self):
        self.assertTrue(any(n["ten"] == "Tài khoản" for n in tim(self.ad, "thu trang")))
        self.assertFalse(any(n["ten"] == "Tài khoản" for n in tim(self.ts, "thu trang")))
