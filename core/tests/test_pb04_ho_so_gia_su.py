"""Kiểm thử PB-04 (hồ sơ & chuyên môn gia sư; BRULE-09, BRULE-10), PB-19 (lọc), PB-24 (truy cập)."""

from datetime import time

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.models import HoSoGiaSu, LichRanh, MonGiaSu, MonHoc, NhatKy, User

MK = "MatKhau@Manh123"


class DuLieu(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.ts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS")
        self.gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="Gia Sư A",
                                           email="gs@test.local")
        self.gs2 = User.objects.create_user("gs2", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="Gia Sư B",
                                            email="gs2@test.local")
        self.ho_so = HoSoGiaSu.objects.create(user=self.gs)
        self.ho_so2 = HoSoGiaSu.objects.create(user=self.gs2)
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.anh = MonHoc.objects.create(ma="ANH", ten="Tiếng Anh")

    def dang_nhap(self, u):
        self.client.login(username=u.username, password=MK)


class PB04GiaSuTest(DuLieu):
    def test_PB04_gia_su_cap_nhat_kinh_nghiem_va_email_zoom(self):
        self.dang_nhap(self.gs)
        r = self.client.post(reverse("ho_so_cap_nhat"), {
            "trinh_do": "Cử nhân Sư phạm Toán", "kinh_nghiem": "3 năm", "email_zoom": "gs@zoom.local",
            "so_dien_thoai": "0905123456",
        })
        self.assertRedirects(r, reverse("ho_so_cua_toi"))
        self.ho_so.refresh_from_db()
        self.assertEqual(self.ho_so.email_zoom, "gs@zoom.local")
        self.gs.refresh_from_db()
        self.assertEqual(self.gs.so_dien_thoai, "0905123456")

    def test_BRULE10_dang_ky_mon_moi_luon_o_trang_thai_cho_duyet(self):
        self.dang_nhap(self.gs)
        self.client.post(reverse("ho_so_dang_ky_mon"), {"mon_hoc": self.toan.pk, "cap_do": "Lớp 9"})
        mg = MonGiaSu.objects.get(ho_so=self.ho_so)
        self.assertEqual(mg.trang_thai, MonGiaSu.TrangThai.CHO_DUYET)

    def test_BRULE10_gia_su_khong_tu_rut_mon_da_duyet(self):
        mg = MonGiaSu.objects.create(ho_so=self.ho_so, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        self.dang_nhap(self.gs)
        self.client.post(reverse("ho_so_rut_mon", args=[mg.pk]))
        self.assertTrue(MonGiaSu.objects.filter(pk=mg.pk).exists())

    def test_PB04_gia_su_rut_duoc_mon_dang_cho(self):
        mg = MonGiaSu.objects.create(ho_so=self.ho_so, mon_hoc=self.toan)
        self.dang_nhap(self.gs)
        self.client.post(reverse("ho_so_rut_mon", args=[mg.pk]))
        mg.refresh_from_db()
        self.assertEqual(mg.trang_thai, MonGiaSu.TrangThai.DA_RUT)  # HS-08: giữ bản ghi

    def test_PB24_gia_su_khong_dung_vao_mon_cua_nguoi_khac(self):
        mg = MonGiaSu.objects.create(ho_so=self.ho_so2, mon_hoc=self.toan)
        self.dang_nhap(self.gs)
        r = self.client.post(reverse("ho_so_rut_mon", args=[mg.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(MonGiaSu.objects.filter(pk=mg.pk).exists())

    def test_PB04_dang_ky_lai_mon_bi_tu_choi_quay_ve_cho_duyet(self):
        MonGiaSu.objects.create(ho_so=self.ho_so, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.TU_CHOI,
                                ghi_chu_duyet="Thiếu bằng cấp")
        self.dang_nhap(self.gs)
        self.client.post(reverse("ho_so_dang_ky_mon"), {"mon_hoc": self.toan.pk, "cap_do": "Lớp 9"})
        mg = MonGiaSu.objects.get(ho_so=self.ho_so, mon_hoc=self.toan)
        self.assertEqual(mg.trang_thai, MonGiaSu.TrangThai.CHO_DUYET)
        self.assertEqual(mg.ghi_chu_duyet, "")

    def test_PB04_lich_ranh_chan_khung_trung_va_gio_nguoc(self):
        self.dang_nhap(self.gs)
        url = reverse("ho_so_them_lich")
        self.client.post(url, {"thu": 0, "tu_gio": "18:00", "den_gio": "20:00"})
        r = self.client.post(url, {"thu": 0, "tu_gio": "19:00", "den_gio": "21:00"})
        self.assertContains(r, "bị trùng", status_code=400)
        r = self.client.post(url, {"thu": 1, "tu_gio": "20:00", "den_gio": "18:00"})
        self.assertContains(r, "Giờ kết thúc phải sau giờ bắt đầu", status_code=400)
        self.client.post(url, {"thu": 0, "tu_gio": "20:00", "den_gio": "21:00"})  # sát nhau thì hợp lệ
        self.assertEqual(self.ho_so.lich_ranh.count(), 2)


class PB04AdminTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.mg = MonGiaSu.objects.create(ho_so=self.ho_so, mon_hoc=self.toan, cap_do="Lớp 9")
        self.dang_nhap(self.admin)

    def xu_ly(self, hanh_dong, ly_do=""):
        return self.client.post(reverse("gia_su_xu_ly_mon", args=[self.mg.pk]), {"hanh_dong": hanh_dong, "ly_do": ly_do})

    def test_PB04_admin_duyet_mon_ghi_nhat_ky_va_email(self):
        self.xu_ly("duyet")
        self.mg.refresh_from_db()
        self.assertEqual(self.mg.trang_thai, MonGiaSu.TrangThai.DA_DUYET)
        self.assertEqual(self.mg.duyet_boi, self.admin)
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Duyệt môn dạy", doi_tuong="gs").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["gs@test.local"])

    def test_PB04_tu_choi_bat_buoc_co_ly_do(self):
        self.xu_ly("tu_choi", "")
        self.mg.refresh_from_db()
        self.assertEqual(self.mg.trang_thai, MonGiaSu.TrangThai.CHO_DUYET)
        self.xu_ly("tu_choi", "Chưa có chứng chỉ")
        self.mg.refresh_from_db()
        self.assertEqual(self.mg.trang_thai, MonGiaSu.TrangThai.TU_CHOI)
        self.assertIn("Chưa có chứng chỉ", mail.outbox[-1].body)

    def test_PB04_khong_cho_hoat_dong_khi_chua_co_mon_duyet(self):
        self.client.post(reverse("gia_su_doi_trang_thai", args=[self.ho_so.pk]), {"trang_thai": "HOAT_DONG"})
        self.ho_so.refresh_from_db()
        self.assertEqual(self.ho_so.trang_thai, HoSoGiaSu.TrangThai.CHO_DUYET)
        self.xu_ly("duyet")
        self.client.post(reverse("gia_su_doi_trang_thai", args=[self.ho_so.pk]), {"trang_thai": "HOAT_DONG"})
        self.ho_so.refresh_from_db()
        self.assertEqual(self.ho_so.trang_thai, HoSoGiaSu.TrangThai.HOAT_DONG)

    def test_PB04_thu_hoi_mon_cuoi_cung_thi_ho_so_tu_tam_ngung(self):
        self.xu_ly("duyet")
        self.client.post(reverse("gia_su_doi_trang_thai", args=[self.ho_so.pk]), {"trang_thai": "HOAT_DONG"})
        self.xu_ly("thu_hoi", "Nhiều phản hồi xấu")
        self.ho_so.refresh_from_db()
        self.assertEqual(self.ho_so.trang_thai, HoSoGiaSu.TrangThai.TAM_NGUNG)
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Thu hồi môn đã duyệt").exists())

    def test_PB24_chi_admin_duoc_duyet_mon(self):
        for u in (self.ts, self.gs):
            self.client.logout()
            self.dang_nhap(u)
            self.assertEqual(self.xu_ly("duyet").status_code, 403)
        self.mg.refresh_from_db()
        self.assertEqual(self.mg.trang_thai, MonGiaSu.TrangThai.CHO_DUYET)


class PB19LocGiaSuTest(DuLieu):
    def setUp(self):
        super().setUp()
        MonGiaSu.objects.create(ho_so=self.ho_so, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        MonGiaSu.objects.create(ho_so=self.ho_so2, mon_hoc=self.toan)  # chỉ đang chờ duyệt
        MonGiaSu.objects.create(ho_so=self.ho_so2, mon_hoc=self.anh, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        LichRanh.objects.create(ho_so=self.ho_so2, thu=2, tu_gio=time(18), den_gio=time(20))

    def ten_trong_ket_qua(self, **loc):
        r = self.client.get(reverse("gia_su_danh_sach"), loc)
        return [hs.user.username for hs in r.context["trang"]]

    def test_PB19_loc_theo_mon_chi_tinh_mon_da_duyet(self):
        self.dang_nhap(self.ts)
        self.assertEqual(self.ten_trong_ket_qua(mon=self.toan.pk), ["gs"])

    def test_PB19_loc_theo_ngay_ranh_va_mon_cho_duyet(self):
        self.dang_nhap(self.admin)
        self.assertEqual(self.ten_trong_ket_qua(thu=2), ["gs2"])
        self.assertEqual(self.ten_trong_ket_qua(cho_duyet="on"), ["gs2"])

    def test_PB19_doi_vai_tro_khoi_gia_su_thi_an_khoi_danh_sach(self):
        self.gs2.vai_tro = User.VaiTro.TUYEN_SINH
        self.gs2.save()
        self.dang_nhap(self.admin)
        self.assertEqual(self.ten_trong_ket_qua(), ["gs"])

    def test_PB24_gia_su_khong_xem_danh_sach_gia_su_khac(self):
        self.dang_nhap(self.gs)
        self.assertEqual(self.client.get(reverse("gia_su_danh_sach")).status_code, 403)
        self.assertEqual(self.client.get(reverse("gia_su_chi_tiet", args=[self.ho_so2.pk])).status_code, 403)


class SuaLoiCodeReviewGiaSuTest(PB19LocGiaSuTest):
    """Hồi quy cho các lỗi code-review tìm ra (07/11/2026)."""

    def test_PB19_loc_ngay_ranh_khong_nhan_doi_so_mon_cho_duyet(self):
        # gs2 có 2 khung rảnh cùng Thứ 4 và 1 môn chờ duyệt → vẫn phải đếm là 1.
        LichRanh.objects.create(ho_so=self.ho_so2, thu=2, tu_gio=time(20), den_gio=time(21))
        self.dang_nhap(self.admin)
        r = self.client.get(reverse("gia_su_danh_sach"), {"thu": 2})
        ds = list(r.context["trang"])
        self.assertEqual([(hs.user.username, hs.so_cho_duyet) for hs in ds], [("gs2", 1)])

    def test_PB04_duyet_mon_hai_lan_chi_ghi_mot_lan(self):
        mg = MonGiaSu.objects.get(ho_so=self.ho_so2, mon_hoc=self.toan)
        self.dang_nhap(self.admin)
        url = reverse("gia_su_xu_ly_mon", args=[mg.pk])
        self.client.post(url, {"hanh_dong": "duyet"})
        self.client.post(url, {"hanh_dong": "duyet"})
        self.assertEqual(NhatKy.objects.filter(hanh_dong="Duyệt môn dạy").count(), 1)
        self.assertEqual(len(mail.outbox), 1)
