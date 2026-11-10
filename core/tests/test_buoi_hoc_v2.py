"""Bước 3 – màn Gia sư: tạo nhiều buổi (SD-13), vào lớp (SD-14), nháp (SD-15), xác nhận v2 (SD-16),
xin mở lại (SD-19). Mã tình huống theo docs/thiet-ke-luong/20_Ma-tran-tinh-huong.md."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (BanNhapDanhGia, BuoiHoc, HauKiemBuoi, LichRanh, NhatKyGuiTin, TaiKhoanZoom, ThongBao,
                         YeuCauXuLy)
from core.services import buoi_hoc as dv
from core.services.ngoai_le import gui_yeu_cau_xu_ly
from core.tests.test_pb11_pb15_buoi_hoc import DANH_GIA, TT, DuLieu, ngay_mai


def gio_dia_phuong(ngay_sau=2, gio=19, phut=0):
    d = timezone.localtime() + timedelta(days=ngay_sau)
    return d.replace(hour=gio, minute=phut, second=0, microsecond=0)


class TaoNhieuBuoiTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.khoa.so_buoi_dang_ky = 16
        self.khoa.save()

    def test_BH01_tao_3_buoi_lap_tuan(self):
        bd = gio_dia_phuong()
        kq = dv.tao_nhieu_buoi(self.gs, self.khoa, [bd + timedelta(weeks=i) for i in range(3)])
        buoi = [x["buoi"] for x in kq]
        self.assertTrue(all(buoi))
        self.assertEqual([b.trang_thai for b in buoi], [TT.DA_LEN_LICH] * 3)
        self.assertEqual([dv.nhan_buoi(b) for b in buoi], ["Buổi 1/16", "Buổi 2/16", "Buổi 3/16"])

    def test_BH02_mot_buoi_trung_gio_cac_buoi_khac_van_tao(self):
        bd = gio_dia_phuong()
        dv.tao_buoi_chinh_thuc(self.gs, self.khoa, bd + timedelta(weeks=1))
        ke = dv.kiem_tra_ke_hoach(self.gs, self.khoa, [bd + timedelta(weeks=i) for i in range(3)])
        self.assertEqual([x["muc"] for x in ke][1], "chan")
        kq = dv.tao_nhieu_buoi(self.gs, self.khoa, [bd + timedelta(weeks=i) for i in range(3)])
        self.assertEqual(sum(1 for x in kq if x["buoi"]), 2)
        self.assertIn("trùng", kq[1]["loi"])

    def test_BH04_ket_thuc_sau_22h_bi_chan(self):
        ke = dv.kiem_tra_ke_hoach(self.gs, self.khoa, [gio_dia_phuong(gio=21, phut=30)])
        self.assertEqual(ke[0]["muc"], "chan")
        self.assertIn("22:00", ke[0]["ly_do"])

    def test_BH05_ngoai_gio_ranh_chi_canh_bao(self):
        bd = gio_dia_phuong()
        ke = dv.kiem_tra_ke_hoach(self.gs, self.khoa, [bd])
        self.assertEqual(ke[0]["muc"], "canh_bao")
        LichRanh.objects.create(ho_so=self.gs.ho_so_gia_su, thu=bd.weekday(), khung="TOI",
                                tu_gio=bd.time().replace(hour=19), den_gio=bd.time().replace(hour=21))
        self.assertEqual(dv.kiem_tra_ke_hoach(self.gs, self.khoa, [bd])[0]["muc"], "ok")

    def test_BH06_vuot_so_buoi_con_xep(self):
        self.khoa.so_buoi_dang_ky = 2
        self.khoa.save()
        bd = gio_dia_phuong()
        ke = dv.kiem_tra_ke_hoach(self.gs, self.khoa, [bd + timedelta(weeks=i) for i in range(3)])
        self.assertEqual([x["muc"] for x in ke][2], "chan")

    def test_BH09_hoc_bu_moi_buoi_huy_chi_bu_mot_lan(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, gio_dia_phuong())
        dv.huy_buoi(self.gs, b, BuoiHoc.LyDoHuy.HOC_VIEN_HUY, "Ốm")
        b.refresh_from_db()
        self.assertEqual(b.ly_do_huy_ghi_chu, "Ốm")
        kq = dv.tao_nhieu_buoi(self.gs, self.khoa, [gio_dia_phuong(ngay_sau=3)], hoc_bu_cho=b)
        self.assertEqual(kq[0]["buoi"].hoc_bu_cho, b)
        self.assertIn("Học bù", dv.nhan_buoi(kq[0]["buoi"]))
        with self.assertRaisesMessage(ValidationError, "đã có buổi học bù"):
            dv.kiem_tra_ke_hoach(self.gs, self.khoa, [gio_dia_phuong(ngay_sau=4)], hoc_bu_cho=b)

    def test_nhom_host_zoom_quyet_dinh_so_phong(self):
        TaiKhoanZoom.objects.create(email_host="host1@gso.vn", host_key="123456")
        TaiKhoanZoom.objects.create(email_host="host2@gso.vn", host_key="654321")
        bd = gio_dia_phuong()
        b1 = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, bd)
        yc2 = self.tao_yc(self.gs2)
        b2 = dv.tao_buoi_hoc_thu(self.gs2, yc2, bd, 60)  # cùng giờ, host thứ 2
        self.assertEqual({b1.tai_khoan_zoom.email_host, b2.tai_khoan_zoom.email_host}, {"host1@gso.vn", "host2@gso.vn"})

    def test_KH02_dang_ky_thang_thi_khong_tao_hoc_thu(self):
        yc = self.tao_yc(self.gs2)
        yc.dang_ky_thang = True
        yc.save()
        self.assertNotIn(yc, dv.yeu_cau_co_the_hoc_thu(self.gs2))
        with self.assertRaises(ValidationError):
            dv.tao_buoi_hoc_thu(self.gs2, yc, gio_dia_phuong(), 60)

    def test_api_kiem_tra_lich(self):
        self.dang_nhap(self.gs)
        bd = gio_dia_phuong()
        j = self.client.post(reverse("api_kiem_tra_lich"), {"lop": f"k-{self.khoa.pk}", "ngay": f"{bd:%Y-%m-%d}",
                                                            "gio": "19:00", "so_buoi": 3}).json()
        self.assertTrue(j["ok"])
        self.assertEqual(len(j["data"]["dong"]), 3)
        self.dang_nhap(self.gs2)  # lớp của người khác → 404
        r = self.client.post(reverse("api_kiem_tra_lich"), {"lop": f"k-{self.khoa.pk}", "ngay": f"{bd:%Y-%m-%d}",
                                                            "gio": "19:00"})
        self.assertEqual(r.status_code, 404)


class VaoLopTest(DuLieu):
    def tao_buoi_luc(self, phut_toi):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, gio_dia_phuong())
        bd = timezone.now() + timedelta(minutes=phut_toi)
        BuoiHoc.objects.filter(pk=b.pk).update(bat_dau=bd, ket_thuc_luc=bd + timedelta(minutes=b.thoi_luong_phut))
        b.refresh_from_db()
        return b

    def test_BH10_tin_nhan_lop(self):
        TaiKhoanZoom.objects.create(email_host="host1@gso.vn", host_key="987654")
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, gio_dia_phuong())
        tn = dv.noi_dung_moi_vao_lop(b)
        self.assertIn(f"/lop/{self.khoa.ma_lop}/", tn)
        self.assertIn("Meeting ID", tn)
        self.assertNotIn("987654", tn)  # không lộ host key
        self.assertNotIn(self.hv.sdt_phu_huynh, tn)

    def test_BH11_truoc_gio_15_phut_la_trang_cho(self):
        self.tao_buoi_luc(15)
        r = self.client.get(reverse("vao_lop", args=[self.khoa.ma_lop]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "chưa tới giờ học")

    def test_BH12_truoc_gio_5_phut_chuyen_vao_zoom(self):
        b = self.tao_buoi_luc(5)
        r = self.client.get(reverse("vao_lop", args=[self.khoa.ma_lop]))
        self.assertRedirects(r, b.zoom_join_url, fetch_redirect_response=False)

    def test_BH13_gia_su_mo_phong_som_bi_chan(self):
        b = self.tao_buoi_luc(30)
        with self.assertRaisesMessage(ValidationError, "Phòng mở lúc"):
            dv.lay_link_mo_phong(self.gs, b)

    def test_lop_khong_co_buoi(self):
        self.assertContains(self.client.get(reverse("vao_lop", args=["KH-9999"])), "chưa có buổi sắp tới")


class NhapVaXacNhanTest(DuLieu):
    def test_BH14_tu_luu_nhap_va_nap_lai(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        self.dang_nhap(self.gs)
        j = self.client.post(reverse("api_luu_nhap", args=[b.pk]), {"noi_dung": "Ôn tập chương 2", "xep_loai": "KHA"},
                             content_type="application/json").json()
        self.assertTrue(j["ok"])
        self.assertContains(self.client.get(reverse("buoi_chi_tiet", args=[b.pk])), "Ôn tập chương 2")
        self.dang_nhap(self.gs2)
        self.assertEqual(self.client.post(reverse("api_luu_nhap", args=[b.pk]), {}).status_code, 404)

    def test_BH17_nhan_xet_ngan_bi_chan(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        with self.assertRaises(ValidationError):
            dv.xac_nhan_hoan_tat(self.gs, b, {**DANH_GIA, "danh_gia": "Tốt"})
        self.dang_nhap(self.gs)
        r = self.client.post(reverse("buoi_xac_nhan", args=[b.pk]), {**DANH_GIA, "danh_gia": "Tốt"})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "ít nhất 30 ký tự", status_code=400)

    def test_HK01_xac_nhan_xoa_nhap_tao_hau_kiem(self):
        hs = self.gs.ho_so_gia_su
        hs.nguoi_moi = self.nvts
        hs.save()
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        dv.luu_nhap(self.gs, b, {"noi_dung": "x"})
        dv.xac_nhan_hoan_tat(self.gs, b, {**DANH_GIA, "ghi_chu_tuyen_sinh": "Mạng yếu"})
        self.assertFalse(BanNhapDanhGia.objects.filter(buoi_hoc=b).exists())
        hk = HauKiemBuoi.objects.get(buoi_hoc=b)
        self.assertEqual((hk.nguoi_phu_trach, hk.ket_luan), (self.nvts, HauKiemBuoi.KetLuan.CHUA_KIEM_TRA))
        b.refresh_from_db()
        self.assertEqual(b.ghi_chu_tuyen_sinh, "Mạng yếu")

    def test_BH20_tat_gui_zalo(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()))
        self.dang_nhap(self.gs)
        self.client.post(reverse("buoi_xac_nhan", args=[b.pk]), DANH_GIA)  # không tick gửi Zalo
        b.refresh_from_db()
        self.assertEqual((b.trang_thai, b.zalo_trang_thai), (TT.HOAN_TAT, BuoiHoc.GuiZalo.CHUA_GUI))
        self.assertFalse(NhatKyGuiTin.objects.filter(buoi_hoc=b, kenh="ZALO").exists())
        j = self.client.post(reverse("api_gui_lai_zalo", args=[b.pk])).json()  # gửi tay sau
        self.assertTrue(j["ok"])


class XinMoLaiTest(DuLieu):
    def tu_huy(self):
        b = self.ve_qua_khu(dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai()), ket_thuc_truoc_gio=13)
        dv.quet_han()
        b.refresh_from_db()
        self.assertTrue(b.tu_huy)
        return b

    def test_BH26_xin_mo_lai_buoi_chua_tu_huy_bi_chan(self):
        b = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, ngay_mai())
        with self.assertRaisesMessage(ValidationError, "tự hủy"):
            gui_yeu_cau_xu_ly(self.gs, b, YeuCauXuLy.Loai.MO_LAI, "Em bị sốt nên quên xác nhận")

    def test_BH27_xin_mo_lai_lan_2_bi_chan_va_qtv_mo_lai_dong_yeu_cau(self):
        from core.models import User
        from core.services.ngoai_le import mo_lai
        ad = User.objects.create_user("ad", password="x", vai_tro=User.VaiTro.ADMIN, ho_ten="QTV")
        b = self.tu_huy()
        self.dang_nhap(self.gs)
        self.client.post(reverse("buoi_xin_mo_lai", args=[b.pk]), {"noi_dung": "Tối đó em bị sốt nên quên xác nhận"})
        yc = YeuCauXuLy.objects.get(buoi_hoc=b)
        self.assertEqual(yc.trang_thai, YeuCauXuLy.TrangThai.CHO_XU_LY)
        self.assertTrue(ThongBao.objects.filter(nguoi_nhan=ad).exists())
        with self.assertRaisesMessage(ValidationError, "đã gửi yêu cầu"):
            gui_yeu_cau_xu_ly(self.gs, b, YeuCauXuLy.Loai.MO_LAI, "Gửi lần nữa cho chắc ạ")
        mo_lai(ad, b, "Gia sư có lý do chính đáng")
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, YeuCauXuLy.TrangThai.DA_XU_LY)
        b.refresh_from_db()
        self.assertTrue(b.cho_xac_nhan)

    def test_trang_chi_tiet_cac_trang_thai_khong_loi(self):
        self.dang_nhap(self.gs)
        b1 = dv.tao_buoi_chinh_thuc(self.gs, self.khoa, gio_dia_phuong(ngay_sau=3))
        self.assertContains(self.client.get(reverse("buoi_chi_tiet", args=[b1.pk])), "Báo hủy")
        b2 = self.tu_huy()
        self.assertContains(self.client.get(reverse("buoi_chi_tiet", args=[b2.pk])), "Xin mở lại")
