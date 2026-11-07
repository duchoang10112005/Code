"""Kiểm thử bảng giá: học phí / thù lao tự tính theo CẤP ĐỘ HỌC × khung giờ × gói (PB-09, BRULE-15/16).

Quy định của trung tâm (07/11/2026) – migration 0010 tạo sẵn:
- Môn phổ thông: Cơ bản 70.000đ/giờ (giữ 8%), Nâng cao 130.000đ/giờ (giữ 10%)
- IELTS: Nền tảng 150.000đ/giờ (giữ 10%), Chuyên sâu 200.000đ/giờ (giữ 10%)
- Khung buổi 1h / 1,5h / 2h; gói 10 / 20 / 30 buổi giá như nhau, có quyền lợi;
  khuyến mãi theo mùa (nếu có) do trung tâm chịu – thù lao luôn tính trên giá GỐC.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (CapDo, GoiKhoaHoc, HocVien, HoSoGiaSu, KhoaHoc, LoaiMon, MonGiaSu, MonHoc, NhatKy, User,
                         YeuCauHocTap)
from core.services import khoa_hoc as dv_kh
from core.services.bang_gia import goi_dang_ap_dung, tinh_gia

MK = "MatKhau@Manh123"


class DuLieu(TestCase):
    def setUp(self):
        self.pho_thong = LoaiMon.objects.get(ten="Môn phổ thông")
        self.ielts_loai = LoaiMon.objects.get(ten="IELTS")
        self.co_ban = CapDo.objects.get(loai_mon=self.pho_thong, ten="Cơ bản")
        self.nang_cao = CapDo.objects.get(loai_mon=self.pho_thong, ten="Nâng cao")
        self.nen_tang = CapDo.objects.get(loai_mon=self.ielts_loai, ten="Nền tảng")
        self.chuyen_sau = CapDo.objects.get(loai_mon=self.ielts_loai, ten="Chuyên sâu")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán", loai_mon=self.pho_thong)
        self.hoa = MonHoc.objects.create(ma="HOA", ten="Hóa học", loai_mon=self.pho_thong)
        self.ielts = MonHoc.objects.create(ma="IELTS2", ten="IELTS", loai_mon=self.ielts_loai)
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.nvts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="NVTS")


class TinhGiaTest(DuLieu):
    def test_PB09_mon_pho_thong_co_ban_goi_10_buoi_1_5_gio(self):
        bg = tinh_gia(self.toan, self.co_ban, 10, 90)
        self.assertEqual((bg.hoc_phi_goc, bg.hoc_phi, bg.thu_lao, bg.tong_hoc_phi), (105_000, 105_000, 96_600, 1_050_000))

    def test_PB09_hoa_hoc_nang_cao_130k_moi_gio(self):
        bg = tinh_gia(self.hoa, self.nang_cao, 10, 60)
        self.assertEqual((bg.hoc_phi, bg.thu_lao), (130_000, 117_000))

    def test_PB09_ielts_nen_tang_va_chuyen_sau(self):
        self.assertEqual(tinh_gia(self.ielts, self.nen_tang, 10, 90).hoc_phi, 225_000)
        bg = tinh_gia(self.ielts, self.chuyen_sau, 10, 120)
        self.assertEqual((bg.hoc_phi, bg.thu_lao), (400_000, 360_000))

    def test_PB09_khong_chon_cap_do_cua_loai_mon_khac(self):
        # Hóa học là môn phổ thông → không được tính theo cấp độ IELTS
        with self.assertRaisesMessage(ValidationError, "không thuộc loại môn"):
            tinh_gia(self.hoa, self.chuyen_sau, 10, 60)

    def test_PB09_goi_dai_khong_giam_gia_nhung_co_quyen_loi(self):
        bg10, bg30 = tinh_gia(self.toan, self.co_ban, 10, 60), tinh_gia(self.toan, self.co_ban, 30, 60)
        self.assertEqual((bg10.hoc_phi, bg30.hoc_phi, bg30.tong_hoc_phi), (70_000, 70_000, 2_100_000))
        self.assertIn("Ưu tiên giữ nguyên gia sư", bg30.quyen_loi)
        self.assertNotIn("Ưu tiên giữ nguyên gia sư", bg10.quyen_loi)

    def test_PB09_khuyen_mai_5_phan_tram_thu_lao_van_tinh_tren_gia_goc(self):
        GoiKhoaHoc.objects.filter(so_buoi=30).update(ty_le_giam=Decimal("5"))
        bg = tinh_gia(self.toan, self.co_ban, 30, 60)  # 70.000 × 95% = 66.500 → làm tròn 67.000
        self.assertEqual((bg.hoc_phi, bg.thu_lao, bg.tong_hoc_phi), (67_000, 64_400, 2_010_000))
        self.assertEqual(bg.tiet_kiem, 90_000)

    def test_PB09_chi_cho_khung_1_1_5_2_gio_va_goi_dang_ap_dung(self):
        with self.assertRaises(ValidationError):
            tinh_gia(self.toan, self.co_ban, 10, 45)
        with self.assertRaises(ValidationError):
            tinh_gia(self.toan, self.co_ban, 15, 60)

    def test_PB09_muc_khuyen_mai_theo_giai_doan(self):
        hom_nay = timezone.localdate()
        GoiKhoaHoc.objects.create(so_buoi=20, ty_le_giam=Decimal("7"), hieu_luc_tu=hom_nay + timedelta(days=1),
                                  hieu_luc_den=hom_nay + timedelta(days=30))
        self.assertEqual(goi_dang_ap_dung(hom_nay)[20].ty_le_giam, Decimal("0"))
        self.assertEqual(goi_dang_ap_dung(hom_nay + timedelta(days=5))[20].ty_le_giam, Decimal("7"))
        self.assertEqual(goi_dang_ap_dung(hom_nay + timedelta(days=31))[20].ty_le_giam, Decimal("0"))


class TaoKhoaTheoCapDoTest(DuLieu):
    def setUp(self):
        super().setUp()
        gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS", email="g@t.l")
        hs = HoSoGiaSu.objects.create(user=gs, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG)
        MonGiaSu.objects.create(ho_so=hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        hv = HocVien.objects.create(ho_ten="HV", ten_phu_huynh="PH", sdt_phu_huynh="84905123456")
        self.yc = YeuCauHocTap.objects.create(hoc_vien=hv, mon_hoc=self.toan, cap_do=self.co_ban, trinh_do="L9",
                                              muc_tieu="x", thu_mong_muon=[0], lich_mong_muon="t", gia_su=gs,
                                              trang_thai=YeuCauHocTap.TrangThai.DA_PHAN_CONG)

    def test_PB09_nvts_khong_tu_dat_gia_duoc_va_doi_duoc_cap_do(self):
        self.client.login(username="ts", password=MK)
        self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]), {
            "cap_do": self.nang_cao.pk, "so_buoi": 20, "thoi_luong_phut": 120,
            "hoc_phi_moi_buoi": 1, "thu_lao_moi_buoi": 999_999})
        khoa = KhoaHoc.objects.get(yeu_cau=self.yc)
        # Nâng cao 130.000 × 2 giờ = 260.000; thù lao 260.000 × 90% = 234.000
        self.assertEqual((khoa.hoc_phi_moi_buoi, khoa.thu_lao_moi_buoi, khoa.don_gia_gio), (260_000, 234_000, 130_000))
        self.assertEqual((khoa.cap_do, khoa.ten_cap_do), (self.nang_cao, "Môn phổ thông – Nâng cao"))
        self.assertIn("Ưu tiên giữ nguyên gia sư", khoa.quyen_loi_goi)

    def test_PB09_khong_gui_cap_do_ielts_cho_mon_pho_thong(self):
        self.client.login(username="ts", password=MK)
        r = self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]),
                             {"cap_do": self.chuyen_sau.pk, "so_buoi": 10, "thoi_luong_phut": 60})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(KhoaHoc.objects.exists())

    def test_PB09_doi_bang_gia_khong_anh_huong_khoa_da_tao(self):
        khoa = dv_kh.tao_khoa_hoc(self.nvts, self.yc, 10, 60)
        CapDo.objects.filter(pk=self.co_ban.pk).update(don_gia_gio=90_000)
        khoa.refresh_from_db()
        self.assertEqual(khoa.hoc_phi_moi_buoi, 70_000)


class AdminBangGiaTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.client.login(username="ad", password=MK)

    def du_lieu_cap_do(self, cd, **kw):
        p = f"cd{cd.pk}"
        d = {f"{p}-loai_mon": cd.loai_mon_id, f"{p}-ten": cd.ten, f"{p}-mo_ta": cd.mo_ta,
             f"{p}-don_gia_gio": cd.don_gia_gio, f"{p}-ty_le_trung_tam": str(cd.ty_le_trung_tam),
             f"{p}-thu_tu": cd.thu_tu}
        d.update({f"{p}-{k}": v for k, v in kw.items()})
        return d

    def test_PB09_admin_sua_gia_cap_do_co_nhat_ky(self):
        self.client.post(reverse("bang_gia_sua_cap_do", args=[self.nang_cao.pk]),
                         self.du_lieu_cap_do(self.nang_cao, don_gia_gio=140_000))
        self.nang_cao.refresh_from_db()
        self.assertEqual(self.nang_cao.don_gia_gio, 140_000)
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Sửa giá cấp độ").exists())

    def test_PB09_admin_them_loai_mon_va_cap_do(self):
        self.client.post(reverse("bang_gia_them_loai_mon"), {"loai-ten": "Tin học"})
        tin = LoaiMon.objects.get(ten="Tin học")
        self.client.post(reverse("bang_gia_them_cap_do"), {
            "moi-loai_mon": tin.pk, "moi-ten": "Lập trình cơ bản", "moi-mo_ta": "", "moi-don_gia_gio": 100_000,
            "moi-ty_le_trung_tam": "10", "moi-thu_tu": 1})
        self.assertTrue(CapDo.objects.filter(loai_mon=tin, ten="Lập trình cơ bản").exists())

    def test_BRULE16_khong_dat_khuyen_mai_vuot_ty_le_trung_tam(self):
        r = self.client.post(reverse("bang_gia_them_goi"), {
            "so_buoi": 30, "ty_le_giam": "9", "hieu_luc_tu": timezone.localdate().isoformat()})
        self.assertContains(r, "Tối đa 8%")
        self.assertFalse(GoiKhoaHoc.objects.filter(ty_le_giam=9).exists())

    def test_BRULE16_khong_ha_ty_le_trung_tam_duoi_muc_khuyen_mai_dang_chay(self):
        GoiKhoaHoc.objects.filter(so_buoi=30).update(ty_le_giam=Decimal("5"))
        r = self.client.post(reverse("bang_gia_sua_cap_do", args=[self.co_ban.pk]),
                             self.du_lieu_cap_do(self.co_ban, ty_le_trung_tam="4"))
        self.assertContains(r, "mức khuyến mãi lớn nhất đang chạy")
        self.co_ban.refresh_from_db()
        self.assertEqual(self.co_ban.ty_le_trung_tam, Decimal("8"))

    def test_PB09_them_khuyen_mai_khong_ghi_quyen_loi_thi_giu_quyen_loi_cu(self):
        mai = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.client.post(reverse("bang_gia_them_goi"), {"so_buoi": 20, "ty_le_giam": "5", "hieu_luc_tu": mai})
        self.assertIn("Ưu tiên giữ nguyên gia sư", GoiKhoaHoc.objects.get(so_buoi=20, ty_le_giam=5).quyen_loi)

    def test_PB24_chi_admin_vao_bang_gia(self):
        self.assertContains(self.client.get(reverse("bang_gia")), "Nâng cao")
        self.client.logout()
        self.client.login(username="ts", password=MK)
        self.assertEqual(self.client.get(reverse("bang_gia")).status_code, 403)
