"""Bước 4e – Hậu kiểm buổi học (SD-20..22): chấm 5 tiêu chí, Tuyển sinh người mời kết luận, xử lý."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from core.integrations import zoom
from core.integrations.zoom import NguoiThamGia
from core.models import BuoiHoc, DieuChinhThuLao, HauKiemBuoi, HoSoGiaSu, ThuLao, User
from core.services import buoi_hoc as dv_buoi
from core.services import hau_kiem as dv
from core.tests.test_pb33_ngoai_le import NgoaiLe
from core.tests.test_pb11_pb15_buoi_hoc import MK

KL = HauKiemBuoi.KetLuan
TT = BuoiHoc.TrangThai


class HauKiemTest(NgoaiLe):
    def setUp(self):
        super().setUp()
        self.ts2 = User.objects.create_user("ts2", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="TS Hai")
        HoSoGiaSu.objects.filter(user=self.gs).update(nguoi_moi=self.nvts)
        self.gs.refresh_from_db()

    def buoi_cham(self, phut_gs=60, phut_hv=60, tre=0, gio=19):
        b = self.buoi_xac_nhan(gio=gio)
        t0 = b.bat_dau
        zoom._fake_singleton.kich_ban_tham_gia[b.zoom_meeting_id] = [
            NguoiThamGia("GS", "", t0 + timedelta(minutes=tre), t0 + timedelta(minutes=tre + phut_gs), la_host=True),
            NguoiThamGia("HV", "", t0, t0 + timedelta(minutes=phut_hv))]
        dv_buoi.hau_kiem()
        return HauKiemBuoi.objects.get(buoi_hoc=b)

    def test_cham_5_tieu_chi_va_nguoi_phu_trach(self):
        hk = self.buoi_cham(phut_gs=30, tre=20)
        self.assertEqual(hk.nguoi_phu_trach, self.nvts)
        self.assertEqual((hk.tre_phut, hk.ty_le_gia_su, hk.ty_le_hoc_vien), (20, 50, 100))
        dat = [t["dat"] for t in dv.tieu_chi(hk)]
        self.assertEqual(dat, [False, False, True, True, True])
        self.assertEqual(hk.so_canh_bao, 2)
        self.assertEqual(hk.buoi_hoc.trang_thai, TT.HOAN_TAT)

    def test_quyen_chi_nguoi_moi_ket_luan(self):
        hk = self.buoi_cham()
        with self.assertRaisesMessage(PermissionDenied, "NVTS"):
            dv.ket_luan(self.ts2, hk, KL.HOP_LE)
        self.dang_nhap(self.ts2)
        r = self.client.post(reverse("api_hau_kiem_ket_luan", args=[hk.buoi_hoc_id]), {"ket_luan": "HOP_LE"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 404)  # ngoài phạm vi xem của TS khác
        self.dang_nhap(self.admin)
        r = self.client.post(reverse("api_hau_kiem_ket_luan", args=[hk.buoi_hoc_id]), {"ket_luan": "HOP_LE"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 403)
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("api_hau_kiem_ket_luan", args=[hk.buoi_hoc_id]), {"ket_luan": "HOP_LE"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(r.json()["ok"])
        self.assertIn("Hợp lệ", r.json()["message"])
        r = self.client.post(reverse("api_hau_kiem_ket_luan", args=[hk.buoi_hoc_id]), {"ket_luan": "HOP_LE"},
                             HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json()["message"], "Buổi đã được kiểm tra.")

    def test_co_van_de_bat_buoc_ly_do_va_ghi_chu(self):
        hk = self.buoi_cham()
        with self.assertRaises(ValidationError):
            dv.ket_luan(self.nvts, hk, KL.CO_VAN_DE, "VAO_TRE", "")
        dv.ket_luan(self.nvts, hk, KL.CO_VAN_DE, "VAO_TRE", "Vào trễ 20 phút")
        b = hk.buoi_hoc
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, ThuLao.objects.get(buoi_hoc=b).trang_thai), (TT.DANG_XEM_XET, ThuLao.TrangThai.TAM_GIU))

    def test_duyet_hang_loat_chi_buoi_sach(self):
        sach = self.buoi_cham(gio=8)
        ban = self.buoi_cham(phut_hv=10, gio=12)
        da, bo = dv.duyet_hang_loat(self.nvts, [sach.pk, ban.pk], chi_buoi_sach=True)
        self.assertEqual((da, bo), (1, 1))
        sach.refresh_from_db()
        ban.refresh_from_db()
        self.assertEqual((sach.ket_luan, sach.hang_loat, ban.ket_luan), (KL.HOP_LE, True, KL.CHUA_KIEM_TRA))
        self.assertEqual(dv.duyet_hang_loat(self.ts2, [ban.pk]), (0, 1))  # không thuộc quyền

    def test_xu_ly_vẫn_tinh_va_khong_tinh(self):
        a = self.buoi_cham(gio=8)
        dv.ket_luan(self.nvts, a, KL.CO_VAN_DE, "THIEU_GIO", "x")
        dv.xu_ly(self.nvts, a, True, "Phụ huynh xác nhận đủ giờ")
        a.refresh_from_db()
        self.assertEqual((a.ket_luan, a.buoi_hoc.trang_thai), (KL.DA_XU_LY_TINH, TT.HOAN_TAT))
        self.assertEqual(ThuLao.objects.get(buoi_hoc=a.buoi_hoc).trang_thai, ThuLao.TrangThai.TAM_TINH)
        b = self.buoi_cham(gio=12)
        dv.ket_luan(self.nvts, b, KL.CO_VAN_DE, "THIEU_GIO", "x")
        dv.xu_ly(self.nvts, b, False, "Học viên không vào lớp")
        b.refresh_from_db()
        self.khoa.refresh_from_db()
        self.assertEqual((b.ket_luan, b.buoi_hoc.trang_thai), (KL.DA_XU_LY_KHONG_TINH, TT.DA_HUY))
        self.assertEqual(self.khoa.so_buoi_da_dung, 1)

    def test_khong_tinh_khi_thang_da_chot_tao_dieu_chinh_tru(self):
        hk = self.buoi_cham()
        dv.ket_luan(self.nvts, hk, KL.CO_VAN_DE, "THIEU_GIO", "x")
        ThuLao.objects.filter(buoi_hoc=hk.buoi_hoc).update(trang_thai=ThuLao.TrangThai.DA_DOI_SOAT)
        dv.xu_ly(self.nvts, hk, False, "Không công nhận")
        dc = DieuChinhThuLao.objects.get()
        self.assertEqual(dc.so_tien, -ThuLao.objects.get().so_tien)
        hk.refresh_from_db()
        self.assertEqual(hk.ket_luan, KL.DA_XU_LY_KHONG_TINH)

    def test_man_hinh_ts_va_qtv_chi_xem(self):
        hk = self.buoi_cham(phut_hv=10)
        self.dang_nhap(self.nvts)
        r = self.client.get(reverse("hau_kiem"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["chon"], hk)
        self.assertTrue(r.context["co_quyen"])
        self.assertContains(r, "Kết luận của bạn")
        r = self.client.get(reverse("hau_kiem"), {"tab": "canh_bao"})
        self.assertEqual(len(r.context["ds"]), 1)
        self.dang_nhap(self.ts2)
        self.assertEqual(len(self.client.get(reverse("hau_kiem")).context["ds"]), 0)
        self.dang_nhap(self.admin)
        r = self.client.get(reverse("hau_kiem"))
        self.assertFalse(r.context["co_quyen"])
        self.assertNotContains(r, "Kết luận của bạn")
