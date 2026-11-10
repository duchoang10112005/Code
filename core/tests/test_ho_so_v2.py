"""Bước 3f – Hồ sơ của tôi: lưới giờ rảnh (SD-26), đăng ký môn 4 bước (SD-27). Mã HS-xx theo 20_Ma-tran-tinh-huong.md."""

import shutil
import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (CapDo, HoSoGiaSu, LichRanh, LoiMoi, MinhChung, MonGiaSu, MonHoc, ThongBao, User,
                         HocVien, YeuCauHocTap)
from core.services import gia_su as dv

MK = "MatKhau@Manh123"
THU_MUC_TAM = tempfile.mkdtemp()


def anh(ten="kq.png", kb=10):
    return SimpleUploadedFile(ten, b"x" * (kb * 1024), content_type="image/png")


@override_settings(MEDIA_ROOT=THU_MUC_TAM)
class HoSoV2Test(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_TAM, ignore_errors=True)

    def setUp(self):
        self.ad = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")
        self.gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS A")
        self.gs2 = User.objects.create_user("gs2", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS B")
        self.hs = HoSoGiaSu.objects.create(user=self.gs)
        HoSoGiaSu.objects.create(user=self.gs2)
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.c9 = CapDo.objects.create(mon_hoc=self.toan, ten="Lớp 8–9")
        self.client.force_login(self.gs)

    def du_lieu(self, **them):
        d = {"v2": "1", "mon_hoc": self.toan.pk, "cap_do_ids": [self.c9.pk], "diem_test": "8,5",
             "anh_ket_qua_test": anh(), "mc_so": "1", "mc-0-loai": "THE_SV", "mc-0-url": "https://drive.google.com/x",
             "ly_do_dang_ky": "2 năm dạy kèm Toán THCS", "cam_ket": "1"}
        d.update(them)
        return {k: v for k, v in d.items() if v is not None}

    def gui(self, **them):
        return self.client.post(reverse("ho_so_dang_ky_mon"), self.du_lieu(**them), HTTP_X_REQUESTED_WITH="fetch")

    def test_dang_ky_day_du_thanh_cong(self):
        j = self.gui().json()
        self.assertTrue(j["ok"], j)
        mg = MonGiaSu.objects.get(ho_so=self.hs, mon_hoc=self.toan)
        self.assertEqual((mg.trang_thai, str(mg.diem_test)), (MonGiaSu.TrangThai.CHO_DUYET, "8.50"))
        self.assertEqual(list(mg.cap_do_duyet.all()), [self.c9])
        self.assertTrue(mg.anh_ket_qua_test)
        self.assertEqual(MinhChung.objects.filter(mon_gia_su=mg).count(), 1)
        self.assertTrue(ThongBao.objects.filter(nguoi_nhan=self.ad).exists())

    def test_HS03_thieu_ket_qua_test_bi_chan(self):
        j = self.gui(anh_ket_qua_test=None).json()
        self.assertFalse(j["ok"])
        self.assertIn("anh_ket_qua_test", j["errors"])
        j = self.gui(diem_test="").json()
        self.assertIn("diem_test", j["errors"])

    def test_HS04_link_minh_chung_http_bi_chan(self):
        j = self.gui(**{"mc-0-url": "http://drive.google.com/x"}).json()
        self.assertFalse(j["ok"])
        self.assertIn("https://", j["message"])

    def test_HS05_tep_qua_5MB_hoac_sai_dinh_dang_bi_chan(self):
        j = self.gui(anh_ket_qua_test=anh(kb=5 * 1024 + 1)).json()
        self.assertIn("5 MB", j["message"])
        j = self.gui(anh_ket_qua_test=SimpleUploadedFile("kq.exe", b"x", content_type="application/x-msdownload")).json()
        self.assertIn("PDF, JPG hoặc PNG", j["message"])
        self.assertFalse(MonGiaSu.objects.exists())

    def test_thieu_cam_ket_hoac_minh_chung_bi_chan(self):
        self.assertFalse(self.gui(cam_ket=None).json()["ok"])
        self.assertIn("minh_chung", self.gui(**{"mc_so": "0"}).json()["errors"])

    def test_HS06_gui_lai_mon_bi_tu_choi_cung_ban_ghi(self):
        mg = MonGiaSu.objects.create(ho_so=self.hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.TU_CHOI,
                                     ghi_chu_duyet="Thiếu bằng cấp")
        self.assertTrue(self.gui().json()["ok"])
        mg.refresh_from_db()
        self.assertEqual((mg.trang_thai, mg.ghi_chu_duyet), (MonGiaSu.TrangThai.CHO_DUYET, ""))
        self.assertEqual(MonGiaSu.objects.count(), 1)

    def test_HS08_rut_mon_cho_duyet_va_xem_tep_co_phan_quyen(self):
        self.gui()
        mg = MonGiaSu.objects.get()
        url = reverse("ho_so_xem_tep", args=["kq", mg.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.gs2)
        self.assertEqual(self.client.get(url).status_code, 404)  # gia sư khác không xem được
        self.client.force_login(self.ad)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.gs)
        self.client.post(reverse("ho_so_rut_mon", args=[mg.pk]))
        mg.refresh_from_db()
        self.assertEqual(mg.trang_thai, MonGiaSu.TrangThai.DA_RUT)

    def test_HS01_luoi_gio_ranh(self):
        j = self.client.post(reverse("api_gio_ranh"), {"khung": ["0-TOI", "2-TOI", "5-SANG", "9-TOI", "0-XYZ"]},
                             content_type="application/json").json()
        self.assertTrue(j["ok"])
        self.assertEqual(set(self.hs.lich_ranh.values_list("thu", "khung")), {(0, "TOI"), (2, "TOI"), (5, "SANG")})
        self.client.post(reverse("api_gio_ranh"), {"khung": ["0-TOI"]}, content_type="application/json")
        self.assertEqual(self.hs.lich_ranh.count(), 1)
        lr = LichRanh.objects.get(ho_so=self.hs)
        self.assertEqual((lr.tu_gio.hour, lr.den_gio.hour), (19, 21))

    def test_HS02_tam_nghi_vo_hieu_loi_moi_dang_cho(self):
        hv = HocVien.objects.create(ho_ten="HV", ten_phu_huynh="PH", sdt_phu_huynh="84905000111")
        yc = YeuCauHocTap.objects.create(hoc_vien=hv, mon_hoc=self.toan, trinh_do="Lớp 9", muc_tieu="x",
                                         lich_mong_muon="Tối", trang_thai="DANG_TIM")
        lm = LoiMoi.objects.create(yeu_cau=yc, gia_su=self.gs)
        self.client.post(reverse("ho_so_cap_nhat"), {"tam_nghi_den": f"{date.today() + timedelta(days=5):%Y-%m-%d}"})
        lm.refresh_from_db()
        self.assertEqual(lm.trang_thai, LoiMoi.TrangThai.VOIDED)
        self.hs.refresh_from_db()
        self.assertTrue(self.hs.dang_tam_nghi)

    def test_trang_ho_so_hien_wizard(self):
        r = self.client.get(reverse("ho_so_cua_toi"))
        self.assertContains(r, "Bước 1/4")
        import json
        mon = json.loads(r.context["du_lieu_mon"])
        self.assertEqual(mon[0]["cap_do"][0]["ten"], "Lớp 8–9")
