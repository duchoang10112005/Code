"""Gửi đánh giá buổi học cho phụ huynh qua email (song song Zalo, miễn phí)."""

from django.core import mail

from core.integrations import zalo
from core.models import BuoiHoc, HauKiemBuoi, HocVien, NhatKyGuiTin
from core.services import buoi_hoc as dv
from core.services import hau_kiem as dv_hk
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, DuLieu, ngay_mai

G = BuoiHoc.GuiZalo


class EmailPhuHuynhTest(DuLieu):
    def buoi_xong(self, **them):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=1)
        dv.xac_nhan_hoan_tat(self.gs, b, {**DANH_GIA, **them})
        b.refresh_from_db()
        return b

    def test_co_email_thi_gui_kem_html(self):
        HocVien.objects.filter(pk=self.hv.pk).update(email_phu_huynh="ph@vd.vn")
        mail.outbox.clear()
        b = self.buoi_xong()
        self.assertEqual((b.zalo_trang_thai, b.email_trang_thai), (G.DA_GUI, G.DA_GUI))
        thu = [m for m in mail.outbox if m.to == ["ph@vd.vn"]]
        self.assertEqual(len(thu), 1)
        self.assertIn(self.hv.ho_ten, thu[0].subject)
        self.assertIn(DANH_GIA["danh_gia"], thu[0].alternatives[0][0])
        self.assertTrue(NhatKyGuiTin.objects.filter(kenh="EMAIL", nguoi_nhan="ph@vd.vn", thanh_cong=True).exists())

    def test_khong_co_email_thi_bo_qua_tat_gui_thi_khong_gui(self):
        b = self.buoi_xong()
        self.assertEqual(b.email_trang_thai, G.CHUA_GUI)
        HocVien.objects.filter(pk=self.hv.pk).update(email_phu_huynh="ph@vd.vn")
        mail.outbox.clear()
        b2 = self.buoi_xong(gui_zalo_phu_huynh=False)
        self.assertEqual((b2.email_trang_thai, [m for m in mail.outbox if m.to == ["ph@vd.vn"]]), (G.CHUA_GUI, []))

    def test_hau_kiem_tinh_dat_khi_zalo_loi_nhung_email_da_gui(self):
        HocVien.objects.filter(pk=self.hv.pk).update(email_phu_huynh="ph@vd.vn")
        zalo._fake_singleton.gia_lap_loi = True
        b = self.buoi_xong()
        zalo._fake_singleton.gia_lap_loi = False
        self.assertEqual((b.zalo_trang_thai, b.email_trang_thai), (G.LOI, G.DA_GUI))
        hk = HauKiemBuoi.objects.get(buoi_hoc=b)
        self.assertTrue(dv_hk.tieu_chi(hk)[4]["dat"])
