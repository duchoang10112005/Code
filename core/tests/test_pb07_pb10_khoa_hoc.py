"""Kiểm thử Phần 4 – tiến trình 4.0: PB-07 (kết quả học thử), PB-08, PB-09, PB-10, PB-24; BRULE-13..16."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, MonGiaSu, MonHoc, NhatKy, User, YeuCauHocTap
from core.services import khoa_hoc as dv
from core.services import yeu_cau as dv_yc

MK = "MatKhau@Manh123"
YC, KQ, KH = YeuCauHocTap.TrangThai, YeuCauHocTap.KetQuaHocThu, KhoaHoc.TrangThai
KHOA = {"so_buoi_dang_ky": 12, "thoi_luong_phut": 90, "hoc_phi_moi_buoi": 200_000, "thu_lao_moi_buoi": 120_000}


class DuLieu(TestCase):
    def setUp(self):
        self.nvts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="NVTS")
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.gs = self.tao_gia_su("gs", "Gia Sư A")
        self.gs2 = self.tao_gia_su("gs2", "Gia Sư B")
        self.hv = HocVien.objects.create(ho_ten="Học Viên", lop="Lớp 9", ten_phu_huynh="Phụ Huynh",
                                         sdt_phu_huynh="84905123456")
        self.yc = YeuCauHocTap.objects.create(
            hoc_vien=self.hv, mon_hoc=self.toan, trinh_do="Lớp 9", muc_tieu="Thi 10", thu_mong_muon=[0],
            lich_mong_muon="Tối", trang_thai=YC.DA_PHAN_CONG, gia_su=self.gs,
            phan_cong_luc=timezone.now(), tao_boi=self.nvts)

    def tao_gia_su(self, username, ten):
        u = User.objects.create_user(username, password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten=ten,
                                     email=f"{username}@test.local")
        hs = HoSoGiaSu.objects.create(user=u, trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG)
        MonGiaSu.objects.create(ho_so=hs, mon_hoc=self.toan, trang_thai=MonGiaSu.TrangThai.DA_DUYET)
        return u

    def tao_buoi_thu(self, trang_thai=BuoiHoc.TrangThai.HOAN_TAT, gia_su=None):
        return BuoiHoc.objects.create(loai=BuoiHoc.Loai.HOC_THU, yeu_cau=self.yc, gia_su=gia_su or self.gs,
                                      hoc_vien=self.hv, bat_dau=timezone.now() - timedelta(days=1),
                                      trang_thai=trang_thai)

    def dang_nhap(self, u):
        self.client.logout()
        self.client.login(username=u.username, password=MK)


# ------------------------------------------------------------ nhánh A / PB-09
class NhanhATest(DuLieu):
    def test_BRULE14_nhanh_A_tao_khoa_thang_tu_da_phan_cong(self):
        khoa = dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.trang_thai, YC.CHINH_THUC)
        self.assertEqual((khoa.gia_su, khoa.hoc_vien), (self.gs, self.hv))   # PB-08: kế thừa đúng
        self.assertEqual((khoa.so_buoi_da_dung, khoa.so_buoi_con_lai), (0, 12))  # PB-09
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Tạo khóa học chính thức").exists())

    def test_PB09_tao_khoa_qua_giao_dien(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]), KHOA)
        khoa = KhoaHoc.objects.get(yeu_cau=self.yc)
        self.assertRedirects(r, reverse("khoa_hoc_chi_tiet", args=[khoa.pk]))



    def test_BRULE16_thu_lao_lon_hon_hoc_phi_bi_bao_loi(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]), {**KHOA, "thu_lao_moi_buoi": 250_000})
        self.assertContains(r, "không được lớn hơn học phí")
        self.assertFalse(KhoaHoc.objects.exists())

    def test_BRULE15_so_buoi_bang_0_bi_bao_loi(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]), {**KHOA, "so_buoi_dang_ky": 0})
        self.assertContains(r, "Số buổi đăng ký phải lớn hơn 0")
        self.assertFalse(KhoaHoc.objects.exists())

    def test_PB09_chi_cho_khung_1_1_5_2_gio(self):
        self.dang_nhap(self.nvts)
        self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]), {**KHOA, "thoi_luong_phut": 45})
        self.assertFalse(KhoaHoc.objects.exists())

    def test_BRULE16_database_chan_thu_lao_vuot_hoc_phi(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            KhoaHoc.objects.create(yeu_cau=self.yc, hoc_vien=self.hv, gia_su=self.gs, so_buoi_dang_ky=5,
                                   hoc_phi_moi_buoi=100, thu_lao_moi_buoi=200)

    def test_PB09_khong_tao_duoc_khoa_thu_hai(self):
        dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        with self.assertRaises(ValidationError):
            dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        self.assertEqual(KhoaHoc.objects.count(), 1)

    def test_PB09_yeu_cau_chua_phan_cong_khong_tao_khoa(self):
        YeuCauHocTap.objects.filter(pk=self.yc.pk).update(trang_thai=YC.DANG_TIM, gia_su=None)
        with self.assertRaises(ValidationError):
            dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)


# ------------------------------------------------------------ nhánh B / PB-08
class NhanhBTest(DuLieu):
    def test_BRULE13_chua_co_buoi_thu_hoan_tat_thi_khong_ghi_ket_qua(self):
        self.tao_buoi_thu(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH)
        with self.assertRaises(ValidationError):
            dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.DONG_Y)

    def test_BRULE14_da_hoc_thu_thi_phai_co_ket_qua_tiep_tuc_moi_tao_khoa(self):
        self.tao_buoi_thu()
        with self.assertRaisesMessage(ValidationError, "Đồng ý đăng ký"):
            dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.DONG_Y)
        self.assertEqual(self.yc.trang_thai, YC.HOC_THU_XONG)
        khoa = dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        self.assertEqual(khoa.gia_su, self.gs)

    def test_PB08_khong_tiep_tuc_thi_dong_yeu_cau_va_khong_tao_khoa(self):
        self.tao_buoi_thu()
        with self.assertRaises(ValidationError):
            dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.KHONG_DANG_KY, "")  # thiếu lý do
        dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.KHONG_DANG_KY, "Gia đình chuyển nhà")
        self.assertEqual(self.yc.trang_thai, YC.DONG)
        with self.assertRaises(ValidationError):
            dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)

    def test_PB08_tim_gia_su_khac_quay_ve_dang_tim_va_moi_duoc_nguoi_moi(self):
        self.tao_buoi_thu()
        dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.TIM_GIA_SU_KHAC, "Muốn gia sư nữ")
        self.assertEqual((self.yc.trang_thai, self.yc.gia_su), (YC.DANG_TIM, None))
        moi, _ = dv_yc.gui_loi_moi(self.nvts, self.yc, [self.gs2.pk])
        dv_yc.chap_nhan(self.gs2, moi[0])
        self.yc.refresh_from_db()
        # Học thử cũ là với gia sư A → với gia sư B được đăng ký thẳng (nhánh A).
        self.assertTrue(dv.co_the_tao_khoa(self.yc))
        khoa = dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)
        self.assertEqual(khoa.gia_su, self.gs2)

    def test_PB08_ghi_ket_qua_qua_giao_dien_chuyen_sang_trang_tao_khoa(self):
        self.tao_buoi_thu()
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("yeu_cau_ket_qua_hoc_thu", args=[self.yc.pk]), {"ket_qua": "DONG_Y"})
        self.assertRedirects(r, reverse("yeu_cau_chi_tiet", args=[self.yc.pk]) + "?mo=khoa")


# ------------------------------------------------------------ PB-10 / trạng thái khóa
class TheoDoiKhoaTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.khoa = dv.tao_khoa_hoc(self.nvts, self.yc, {**KHOA, "so_buoi_dang_ky": 10})

    def test_PB10_so_con_lai_va_co_the_xep(self):
        KhoaHoc.objects.filter(pk=self.khoa.pk).update(so_buoi_da_dung=8)
        self.khoa.refresh_from_db()
        BuoiHoc.objects.create(loai=BuoiHoc.Loai.CHINH_THUC, khoa_hoc=self.khoa, yeu_cau=self.yc, gia_su=self.gs,
                               hoc_vien=self.hv, bat_dau=timezone.now() + timedelta(days=1),
                               trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH)
        self.assertEqual((self.khoa.so_buoi_con_lai, self.khoa.so_buoi_co_the_xep), (2, 1))

    def test_PB10_loc_sap_het_buoi(self):
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("khoa_hoc_danh_sach"), {"sap_het": "on"})
        self.assertEqual(len(r.context["trang"]), 0)
        KhoaHoc.objects.filter(pk=self.khoa.pk).update(so_buoi_da_dung=8)
        r = self.client.get(reverse("khoa_hoc_danh_sach"), {"sap_het": "on"})
        self.assertEqual([k.pk for k in r.context["trang"]], [self.khoa.pk])

    def test_PB09_tam_dung_va_huy_bat_buoc_ly_do(self):
        with self.assertRaises(ValidationError):
            dv.doi_trang_thai_khoa(self.nvts, self.khoa, KH.TAM_DUNG, "")
        dv.doi_trang_thai_khoa(self.nvts, self.khoa, KH.TAM_DUNG, "Học viên ốm")
        dv.doi_trang_thai_khoa(self.nvts, self.khoa, KH.DANG_HOC)
        dv.doi_trang_thai_khoa(self.nvts, self.khoa, KH.HUY, "Chuyển trung tâm")
        with self.assertRaises(ValidationError):  # đã hủy thì không mở lại
            dv.doi_trang_thai_khoa(self.nvts, self.khoa, KH.DANG_HOC)


# ------------------------------------------------------------ PB-24 phân quyền
class PhanQuyenKhoaTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.khoa = dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)

    def test_PB24_gia_su_xem_khoa_cua_minh_khong_thay_hoc_phi_va_sdt(self):
        self.dang_nhap(self.gs)
        r = self.client.get(reverse("khoa_cua_toi", args=[self.khoa.pk]))
        self.assertContains(r, "120.000đ")       # thù lao
        self.assertNotContains(r, "200.000")     # học phí
        self.assertNotContains(r, "84905123456")  # SĐT phụ huynh
        self.assertContains(self.client.get(reverse("lop_cua_toi")), self.khoa.ma)

    def test_PB24_gia_su_khac_khong_xem_duoc_khoa(self):
        self.dang_nhap(self.gs2)
        self.assertEqual(self.client.get(reverse("khoa_cua_toi", args=[self.khoa.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk])).status_code, 403)

    def test_PB24_admin_chi_xem_khong_doi_trang_thai(self):
        self.dang_nhap(self.admin)
        self.assertEqual(self.client.get(reverse("khoa_hoc_chi_tiet", args=[self.khoa.pk])).status_code, 200)
        r = self.client.post(reverse("khoa_hoc_doi_trang_thai", args=[self.khoa.pk]),
                             {"trang_thai": "TAM_DUNG", "ly_do": "x"})
        self.assertEqual(r.status_code, 403)


class SuaLoiCodeReviewPhan4Test(DuLieu):
    """Hồi quy cho các lỗi code-review Phần 4 tìm ra (07/11/2026)."""

    def test_PB08_buoi_thu_da_huy_van_cho_dang_ky_thang(self):
        self.tao_buoi_thu(trang_thai=BuoiHoc.TrangThai.DA_HUY)
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("yeu_cau_chi_tiet", args=[self.yc.pk]))
        self.assertIsNone(r.context["buoi_thu"])
        self.assertContains(r, "Đăng ký chính thức luôn")
        self.assertTrue(dv.co_the_tao_khoa(self.yc))

    def test_BRULE11_khoa_gia_su_sau_khi_nhan_lop_thi_go_phan_cong(self):
        self.dang_nhap(self.admin)
        self.client.post(reverse("tai_khoan_doi_trang_thai", args=[self.gs.pk]))
        self.yc.refresh_from_db()
        self.assertEqual((self.yc.trang_thai, self.yc.gia_su), (YC.DANG_TIM, None))

    def test_BRULE11_khong_tao_khoa_cho_gia_su_het_dieu_kien(self):
        HoSoGiaSu.objects.filter(user=self.gs).update(trang_thai=HoSoGiaSu.TrangThai.TAM_NGUNG)
        with self.assertRaisesMessage(ValidationError, "không còn đủ điều kiện"):
            dv.tao_khoa_hoc(self.nvts, self.yc, KHOA)

    def test_PB08_tim_gia_su_khac_huy_buoi_thu_chua_hoc_cua_gia_su_cu(self):
        self.tao_buoi_thu()
        sap_toi = self.tao_buoi_thu(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH)
        dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.TIM_GIA_SU_KHAC)
        sap_toi.refresh_from_db()
        self.assertEqual(sap_toi.trang_thai, BuoiHoc.TrangThai.DA_HUY)

    def test_PB03_loc_cho_chot_gom_ca_hoc_thu_xong(self):
        self.tao_buoi_thu()
        dv.ghi_ket_qua_hoc_thu(self.nvts, self.yc, KQ.DONG_Y)
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("yeu_cau_danh_sach"), {"cho_chot": "on"})
        self.assertEqual([y.pk for y in r.context["trang"]], [self.yc.pk])


class DangKyThangTest(DuLieu):
    """SD-10 / KH-01: đăng ký chính thức luôn; SD-12: mở khóa có lịch cố định, thông báo gia sư."""

    def test_KH01_dang_ky_thang_bi_chan_khi_da_co_buoi_thu(self):
        self.tao_buoi_thu(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH)
        with self.assertRaisesMessage(ValidationError, "đã có buổi học thử"):
            dv.danh_dau_dang_ky_thang(self.nvts, self.yc)

    def test_dang_ky_thang_roi_mo_khoa_co_lich_co_dinh(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("yeu_cau_dang_ky_thang", args=[self.yc.pk]))
        self.assertRedirects(r, reverse("yeu_cau_chi_tiet", args=[self.yc.pk]) + "?mo=khoa")
        self.yc.refresh_from_db()
        self.assertTrue(self.yc.dang_ky_thang)
        r = self.client.post(reverse("khoa_hoc_tao", args=[self.yc.pk]),
                             {**KHOA, "lich_thu_1": "1", "lich_gio_1": "19:30", "zalo_nhom": "Toán 9 – HV"})
        khoa = KhoaHoc.objects.get(yeu_cau=self.yc)
        self.assertEqual(khoa.lich_co_dinh, [{"thu": 1, "gio": "19:30"}])
        self.assertEqual((khoa.zalo_nhom, khoa.tuyen_sinh_phu_trach), ("Toán 9 – HV", self.nvts))
        self.assertTrue(self.gs.thong_bao.filter(tieu_de__contains=khoa.ma).exists())
