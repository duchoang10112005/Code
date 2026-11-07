"""Kiểm thử bảng giá: học phí / thù lao tự tính theo nhóm môn × khung giờ × gói (PB-09, BRULE-15/16).

Quy định của trung tâm (07/11/2026): môn thường 70.000đ/giờ – trung tâm giữ 8%; IELTS 130.000đ/giờ – 10%;
khung buổi 1h / 1,5h / 2h; gói 10 / 20 / 30 buổi KHÔNG giảm giá mà có quyền lợi; khuyến mãi theo mùa
(nếu Admin đặt) do trung tâm chịu – thù lao luôn tính trên giá GỐC.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import GoiKhoaHoc, HocVien, HoSoGiaSu, KhoaHoc, MonGiaSu, MonHoc, NhatKy, NhomGia, User, YeuCauHocTap
from core.services import khoa_hoc as dv_kh
from core.services.bang_gia import goi_dang_ap_dung, tinh_gia

MK = "MatKhau@Manh123"


class DuLieu(TestCase):
    """Migration 0006–0007 đã tạo: Môn thường 70k/8%, IELTS 130k/10%, gói 10/20/30 giảm 0% kèm quyền lợi."""

    def setUp(self):
        self.thuong = NhomGia.objects.get(ten="Môn thường")
        self.ielts_nhom = NhomGia.objects.get(ten="IELTS")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán", nhom_gia=self.thuong)
        self.ielts = MonHoc.objects.create(ma="IELTS2", ten="IELTS", nhom_gia=self.ielts_nhom)
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.nvts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="NVTS")


class TinhGiaTest(DuLieu):
    def test_PB09_mon_thuong_goi_10_buoi_1_5_gio(self):
        bg = tinh_gia(self.toan, 10, 90)
        self.assertEqual((bg.hoc_phi_goc, bg.hoc_phi, bg.thu_lao, bg.tong_hoc_phi), (105_000, 105_000, 96_600, 1_050_000))

    def test_PB09_ielts_1_5_gio_trung_tam_giu_10_phan_tram(self):
        bg = tinh_gia(self.ielts, 10, 90)
        self.assertEqual((bg.hoc_phi_goc, bg.thu_lao), (195_000, 175_500))

    def test_PB09_goi_dai_khong_giam_gia_nhung_co_quyen_loi(self):
        bg10, bg30 = tinh_gia(self.toan, 10, 60), tinh_gia(self.toan, 30, 60)
        self.assertEqual((bg10.hoc_phi, bg30.hoc_phi, bg30.tong_hoc_phi), (70_000, 70_000, 2_100_000))
        self.assertIn("Ưu tiên giữ nguyên gia sư", bg30.quyen_loi)
        self.assertNotIn("Ưu tiên giữ nguyên gia sư", bg10.quyen_loi)

    def test_PB09_khuyen_mai_5_phan_tram_thu_lao_van_tinh_tren_gia_goc(self):
        GoiKhoaHoc.objects.filter(so_buoi=30).update(ty_le_giam=Decimal("5"))
        bg = tinh_gia(self.toan, 30, 60)  # 70.000 × 95% = 66.500 → làm tròn 67.000
        self.assertEqual((bg.hoc_phi, bg.thu_lao, bg.tong_hoc_phi), (67_000, 64_400, 2_010_000))
        self.assertEqual(bg.tiet_kiem, 90_000)

    def test_PB09_chi_cho_khung_1_1_5_2_gio(self):
        with self.assertRaises(ValidationError):
            tinh_gia(self.toan, 10, 45)

    def test_PB09_chi_cho_goi_dang_ap_dung(self):
        with self.assertRaises(ValidationError):
            tinh_gia(self.toan, 15, 60)

    def test_PB09_mon_chua_co_nhom_gia_thi_bao_loi(self):
        with self.assertRaisesMessage(ValidationError, "chưa được gán nhóm giá"):
            tinh_gia(MonHoc.objects.create(ma="SU", ten="Lịch sử"), 10, 60)

    def test_PB09_muc_giam_theo_giai_doan_chon_muc_moi_nhat_con_hieu_luc(self):
        hom_nay = timezone.localdate()
        GoiKhoaHoc.objects.create(so_buoi=20, ty_le_giam=Decimal("7"), hieu_luc_tu=hom_nay + timedelta(days=1),
                                  hieu_luc_den=hom_nay + timedelta(days=30))
        self.assertEqual(goi_dang_ap_dung(hom_nay)[20].ty_le_giam, Decimal("0"))
        self.assertEqual(goi_dang_ap_dung(hom_nay + timedelta(days=5))[20].ty_le_giam, Decimal("7"))
        self.assertEqual(goi_dang_ap_dung(hom_nay + timedelta(days=31))[20].ty_le_giam, Decimal("0"))


class TaoKhoaTheoBangGiaTest(DuLieu):
    def setUp(self):
        super().setUp()
        gs = User.objects.create_user("gs", password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten="GS", email="g@t.l")
        hs = HoSoGiaSu.objects.create(user=gs, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG)
        MonGiaSu.objects.create(ho_so=hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        hv = HocVien.objects.create(ho_ten="HV", ten_phu_huynh="PH", sdt_phu_huynh="84905123456")
        self.yc = YeuCauHocTap.objects.create(hoc_vien=hv, mon_hoc=self.toan, trinh_do="L9", muc_tieu="x",
                                              thu_mong_muon=[0], lich_mong_muon="t", gia_su=gs,
                                              trang_thai=YeuCauHocTap.TrangThai.DA_PHAN_CONG)

    def test_PB09_nvts_khong_tu_dat_gia_duoc(self):
        self.client.login(username="ts", password=MK)
        self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]),
                         {"so_buoi": 20, "thoi_luong_phut": 120, "hoc_phi_moi_buoi": 1, "thu_lao_moi_buoi": 999_999})
        khoa = KhoaHoc.objects.get(yeu_cau=self.yc)
        # 2 giờ × 70.000 = 140.000 (không giảm); thù lao 140.000 × 92% = 128.800
        self.assertEqual((khoa.hoc_phi_moi_buoi, khoa.thu_lao_moi_buoi, khoa.hoc_phi_goc_moi_buoi), (140_000, 128_800, 140_000))
        self.assertEqual((khoa.ty_le_giam, khoa.ty_le_trung_tam, khoa.don_gia_gio), (Decimal("0"), Decimal("8"), 70_000))
        self.assertIn("Ưu tiên giữ nguyên gia sư", khoa.quyen_loi_goi)  # chụp lại quyền lợi

    def test_PB09_doi_bang_gia_khong_anh_huong_khoa_da_tao(self):
        khoa = dv_kh.tao_khoa_hoc(self.nvts, self.yc, 10, 60)
        NhomGia.objects.filter(pk=self.thuong.pk).update(don_gia_gio=90_000)
        khoa.refresh_from_db()
        self.assertEqual(khoa.hoc_phi_moi_buoi, 70_000)


class AdminBangGiaTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.client.login(username="ad", password=MK)

    def test_BRULE16_khong_dat_giam_vuot_ty_le_trung_tam(self):
        r = self.client.post(reverse("bang_gia_them_goi"), {
            "so_buoi": 30, "ty_le_giam": "9", "hieu_luc_tu": timezone.localdate().isoformat()})
        self.assertContains(r, "Tối đa 8%")
        self.assertFalse(GoiKhoaHoc.objects.filter(ty_le_giam=9).exists())

    def test_PB09_admin_dat_muc_giam_moi_co_nhat_ky(self):
        mai = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.client.post(reverse("bang_gia_them_goi"), {"so_buoi": 30, "ty_le_giam": "8", "hieu_luc_tu": mai})
        self.assertTrue(GoiKhoaHoc.objects.filter(so_buoi=30, ty_le_giam=8).exists())
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Đặt giảm giá gói").exists())

    def test_BRULE16_khong_ha_ty_le_trung_tam_duoi_muc_giam_dang_ap_dung(self):
        GoiKhoaHoc.objects.filter(so_buoi=30).update(ty_le_giam=Decimal("5"))  # đang chạy khuyến mãi 5%
        r = self.client.post(reverse("bang_gia_sua_nhom", args=[self.thuong.pk]),
                             {f"n{self.thuong.pk}-don_gia_gio": 70_000, f"n{self.thuong.pk}-ty_le_trung_tam": "4"})
        self.assertContains(r, "mức giảm giá lớn nhất đang áp dụng")
        self.thuong.refresh_from_db()
        self.assertEqual(self.thuong.ty_le_trung_tam, Decimal("8"))

    def test_PB09_them_khuyen_mai_khong_ghi_quyen_loi_thi_giu_quyen_loi_cu(self):
        mai = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.client.post(reverse("bang_gia_them_goi"), {"so_buoi": 20, "ty_le_giam": "5", "hieu_luc_tu": mai})
        moi = GoiKhoaHoc.objects.get(so_buoi=20, ty_le_giam=5)
        self.assertIn("Ưu tiên giữ nguyên gia sư", moi.quyen_loi)

    def test_PB09_sua_quyen_loi_khong_doi_khoa_da_tao(self):
        goi = GoiKhoaHoc.objects.get(so_buoi=10)
        self.client.post(reverse("bang_gia_sua_quyen_loi", args=[goi.pk]), {"quyen_loi": "Tặng tài liệu"})
        goi.refresh_from_db()
        self.assertEqual(goi.ds_quyen_loi, ["Tặng tài liệu"])

    def test_PB24_chi_admin_vao_bang_gia(self):
        self.assertContains(self.client.get(reverse("bang_gia")), "Giá mỗi buổi")
        self.client.logout()
        self.client.login(username="ts", password=MK)
        self.assertEqual(self.client.get(reverse("bang_gia")).status_code, 403)
        r = self.client.post(reverse("bang_gia_them_goi"), {"so_buoi": 10, "ty_le_giam": "1",
                                                           "hieu_luc_tu": timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 403)
