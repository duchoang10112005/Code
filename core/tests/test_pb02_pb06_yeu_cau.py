"""Kiểm thử Phần 3 – tiến trình 3.0: PB-02, PB-03, PB-05, PB-06, PB-22, PB-24, PB-30; BRULE-11, BRULE-12."""

from datetime import time, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (HocVien, HoSoGiaSu, LichRanh, LoiMoi, MonGiaSu, MonHoc, NhatKy, User,
                         YeuCauHocTap)
from core.services import yeu_cau as dv

MK = "MatKhau@Manh123"
YC, LM = YeuCauHocTap.TrangThai, LoiMoi.TrangThai


class DuLieu(TestCase):
    def setUp(self):
        self.nvts = User.objects.create_user("ts", password=MK, vai_tro=User.VaiTro.TUYEN_SINH, ho_ten="NVTS",
                                             email="ts@test.local")
        self.admin = User.objects.create_user("ad", password=MK, vai_tro=User.VaiTro.ADMIN, ho_ten="Admin")
        self.toan = MonHoc.objects.create(ma="TOAN", ten="Toán")
        self.van = MonHoc.objects.create(ma="VAN", ten="Ngữ văn")
        self.gs_a = self.tao_gia_su("gsa", "An", thu_ranh=[0])
        self.gs_b = self.tao_gia_su("gsb", "Bình", thu_ranh=[0, 2])
        self.hv = HocVien.objects.create(ho_ten="Học Viên", lop="Lớp 9", ten_phu_huynh="Phụ Huynh",
                                         sdt_phu_huynh="84905123456")
        self.yc = YeuCauHocTap.objects.create(hoc_vien=self.hv, mon_hoc=self.toan, trinh_do="Lớp 9",
                                              muc_tieu="Thi vào 10", thu_mong_muon=[0, 2],
                                              lich_mong_muon="Tối", tao_boi=self.nvts)

    def tao_gia_su(self, username, ten, thu_ranh=(), mon=None, tt_mon=MonGiaSu.TrangThai.DA_DUYET,
                   tt_ho_so=HoSoGiaSu.TrangThai.HOAT_DONG):
        u = User.objects.create_user(username, password=MK, vai_tro=User.VaiTro.GIA_SU, ho_ten=ten,
                                     email=f"{username}@test.local")
        hs = HoSoGiaSu.objects.create(user=u, trang_thai=tt_ho_so)
        MonGiaSu.objects.create(ho_so=hs, mon_hoc=mon or self.toan, trang_thai=tt_mon)
        for t in thu_ranh:
            LichRanh.objects.create(ho_so=hs, thu=t, tu_gio=time(18), den_gio=time(20))
        return u

    def dang_nhap(self, u):
        self.client.logout()
        self.client.login(username=u.username, password=MK)

    def moi(self, *ds):
        return dv.gui_loi_moi(self.nvts, self.yc, [u.pk for u in ds])[0]


# ---------------------------------------------------------------- PB-02 / 3.1
class PB02TiepNhanTest(DuLieu):
    def du_lieu_tao(self, **kw):
        d = {"hv-ho_ten": "Bé Mới", "hv-lop": "Lớp 5", "hv-ten_phu_huynh": "Mẹ Bé",
             "hv-sdt_phu_huynh": "0935 111 222", "mon_hoc": self.toan.pk, "trinh_do": "Lớp 5",
             "muc_tieu": "Củng cố", "thu_mong_muon": ["1", "3"], "lich_mong_muon": "Chiều"}
        d.update(kw)
        return d

    def test_PB02_tao_yeu_cau_hop_le_chuan_hoa_sdt_trang_thai_moi(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("yeu_cau_tao"), self.du_lieu_tao())
        yc = YeuCauHocTap.objects.latest("pk")
        self.assertRedirects(r, reverse("yeu_cau_chi_tiet", args=[yc.pk]))
        self.assertEqual(yc.trang_thai, YC.MOI)
        self.assertEqual(yc.thu_mong_muon, [1, 3])
        self.assertEqual(yc.hoc_vien.sdt_phu_huynh, "84935111222")
        self.assertTrue(NhatKy.objects.filter(hanh_dong="Tiếp nhận yêu cầu học tập").exists())

    def test_BRULE07_thieu_thong_tin_bat_buoc_thi_khong_tao(self):
        self.dang_nhap(self.nvts)
        so_truoc = YeuCauHocTap.objects.count()
        r = self.client.post(reverse("yeu_cau_tao"), self.du_lieu_tao(muc_tieu="", thu_mong_muon=[]))
        self.assertContains(r, "Chọn ít nhất một thứ trong tuần")
        self.assertEqual(YeuCauHocTap.objects.count(), so_truoc)

    def test_BRULE08_sdt_phu_huynh_sai_thi_bao_loi(self):
        self.dang_nhap(self.nvts)
        r = self.client.post(reverse("yeu_cau_tao"), self.du_lieu_tao(**{"hv-sdt_phu_huynh": "12345"}))
        self.assertContains(r, "Số điện thoại không hợp lệ")
        self.assertFalse(HocVien.objects.filter(ho_ten="Bé Mới").exists())

    def test_PB02_chon_hoc_vien_co_san_khong_tao_trung(self):
        self.dang_nhap(self.nvts)
        d = self.du_lieu_tao(hoc_vien=self.hv.pk, **{"hv-ho_ten": "", "hv-sdt_phu_huynh": ""})
        self.client.post(reverse("yeu_cau_tao"), d)
        self.assertEqual(HocVien.objects.count(), 1)
        self.assertEqual(self.hv.yeu_cau.count(), 2)

    def test_PB24_gia_su_khong_vao_duoc_trang_yeu_cau(self):
        self.dang_nhap(self.gs_a)
        self.assertEqual(self.client.get(reverse("yeu_cau_danh_sach")).status_code, 403)
        self.assertEqual(self.client.get(reverse("yeu_cau_chi_tiet", args=[self.yc.pk])).status_code, 403)

    def test_PB24_admin_chi_xem_khong_tao_duoc(self):
        self.dang_nhap(self.admin)
        self.assertEqual(self.client.get(reverse("yeu_cau_chi_tiet", args=[self.yc.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("yeu_cau_tao")).status_code, 403)


# ---------------------------------------------------------------- PB-05 / 3.2
class PB05DeXuatTest(DuLieu):
    def test_PB05_chi_de_xuat_gia_su_hoat_dong_co_mon_da_duyet(self):
        self.tao_gia_su("cho", "Chờ duyệt", thu_ranh=[0, 2], tt_mon=MonGiaSu.TrangThai.CHO_DUYET)
        self.tao_gia_su("ngung", "Tạm ngừng", thu_ranh=[0, 2], tt_ho_so=HoSoGiaSu.TrangThai.TAM_NGUNG)
        self.tao_gia_su("khac", "Môn khác", thu_ranh=[0, 2], mon=self.van)
        khoa = self.tao_gia_su("khoa", "Bị khóa", thu_ranh=[0, 2])
        khoa.is_active = False
        khoa.save()
        ten = [g["ho_so"].user.username for g in dv.de_xuat_gia_su(self.yc)]
        self.assertCountEqual(ten, ["gsa", "gsb"])

    def test_PB05_trung_nhieu_ngay_ranh_hon_xep_truoc(self):
        ds = dv.de_xuat_gia_su(self.yc)
        self.assertEqual([g["ho_so"].user.username for g in ds], ["gsb", "gsa"])
        self.assertEqual(ds[0]["thu_trung"], [0, 2])


# ---------------------------------------------------------------- PB-03 / 3.3
class PB03GuiLoiMoiTest(DuLieu):
    def test_PB03_gui_loi_moi_chuyen_moi_sang_dang_tim_va_email(self):
        moi = self.moi(self.gs_a, self.gs_b)
        self.yc.refresh_from_db()
        self.assertEqual(len(moi), 2)
        self.assertEqual(self.yc.trang_thai, YC.DANG_TIM)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["gsa@test.local", "gsb@test.local"])

    def test_PB22_khong_gui_trung_loi_moi_dang_cho(self):
        self.moi(self.gs_a)
        moi, bo_qua = dv.gui_loi_moi(self.nvts, self.yc, [self.gs_a.pk])
        self.assertEqual((len(moi), bo_qua), (0, 1))
        self.assertEqual(LoiMoi.objects.filter(yeu_cau=self.yc, gia_su=self.gs_a).count(), 1)

    def test_BRULE11_server_bo_qua_gia_su_khong_du_dieu_kien(self):
        cho = self.tao_gia_su("cho", "Chờ duyệt", tt_mon=MonGiaSu.TrangThai.CHO_DUYET)
        moi, bo_qua = dv.gui_loi_moi(self.nvts, self.yc, [cho.pk])
        self.assertEqual((len(moi), bo_qua), (0, 1))

    def test_PB03_khong_gui_loi_moi_cho_yeu_cau_da_dong(self):
        dv.dong_yeu_cau(self.nvts, self.yc, "Phụ huynh hủy")
        with self.assertRaises(ValidationError):
            self.moi(self.gs_a)


# ---------------------------------------------------------------- PB-06 / 3.4
class PB06PhanHoiTest(DuLieu):
    def setUp(self):
        super().setUp()
        self.lm_a, self.lm_b = sorted(self.moi(self.gs_a, self.gs_b), key=lambda x: x.gia_su.username)

    def test_PB06_accept_phan_cong_dung_mot_gia_su_va_vo_hieu_loi_moi_con_lai(self):
        dv.chap_nhan(self.gs_a, self.lm_a)
        self.yc.refresh_from_db()
        self.assertEqual((self.yc.trang_thai, self.yc.gia_su), (YC.DA_PHAN_CONG, self.gs_a))
        self.lm_b.refresh_from_db()
        self.assertEqual(self.lm_b.trang_thai, LM.VOIDED)

    def test_BRULE12_accept_den_sau_that_bai_khong_tao_phan_cong_thu_hai(self):
        dv.chap_nhan(self.gs_a, self.lm_a)
        with self.assertRaisesMessage(ValidationError, "không còn hiệu lực"):
            dv.chap_nhan(self.gs_b, self.lm_b)
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.gia_su, self.gs_a)

    def test_PB22_hai_gia_su_bam_cung_luc_chi_mot_nguoi_thang(self):
        # Mô phỏng: B đã đọc lời mời của mình (còn CHO) trước khi A bấm Accept,
        # và lời mời của B chưa kịp bị vô hiệu → bước kiểm tra yêu cầu phải chặn.
        LoiMoi.objects.filter(pk=self.lm_b.pk).update(trang_thai=LM.CHO)
        dv.chap_nhan(self.gs_a, self.lm_a)
        LoiMoi.objects.filter(pk=self.lm_b.pk).update(trang_thai=LM.CHO)  # giả lập "chưa bị vô hiệu"
        with self.assertRaisesMessage(ValidationError, "đã có gia sư khác nhận trước"):
            dv.chap_nhan(self.gs_b, self.lm_b)
        self.lm_b.refresh_from_db()
        self.assertEqual(self.lm_b.trang_thai, LM.VOIDED)
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.gia_su, self.gs_a)
        self.assertEqual(LoiMoi.objects.filter(yeu_cau=self.yc, trang_thai=LM.ACCEPTED).count(), 1)

    def test_PB30_accept_loi_moi_het_han_that_bai(self):
        LoiMoi.objects.filter(pk=self.lm_a.pk).update(het_han_luc=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(ValidationError):
            dv.chap_nhan(self.gs_a, self.lm_a)
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.trang_thai, YC.DANG_TIM)

    def test_PB30_quet_chuyen_loi_moi_qua_han_sang_het_han(self):
        LoiMoi.objects.filter(pk=self.lm_a.pk).update(het_han_luc=timezone.now() - timedelta(hours=1))
        self.assertEqual(dv.quet_loi_moi_het_han(), 1)
        self.lm_a.refresh_from_db()
        self.assertEqual(self.lm_a.trang_thai, LM.HET_HAN)

    def test_PB06_reject_khong_phan_cong_yeu_cau_van_dang_tim(self):
        dv.tu_choi(self.gs_a, self.lm_a, "Bận")
        self.lm_a.refresh_from_db()
        self.yc.refresh_from_db()
        self.assertEqual(self.lm_a.trang_thai, LM.REJECTED)
        self.assertEqual(self.yc.trang_thai, YC.DANG_TIM)
        self.assertIsNone(self.yc.gia_su)

    def test_BRULE11_gia_su_bi_tam_ngung_khong_accept_duoc(self):
        HoSoGiaSu.objects.filter(user=self.gs_a).update(trang_thai=HoSoGiaSu.TrangThai.TAM_NGUNG)
        with self.assertRaisesMessage(ValidationError, "chưa đủ điều kiện"):
            dv.chap_nhan(self.gs_a, self.lm_a)

    def test_PB06_dong_yeu_cau_vo_hieu_loi_moi_dang_cho(self):
        dv.dong_yeu_cau(self.nvts, self.yc, "Không còn nhu cầu")
        self.assertFalse(LoiMoi.objects.filter(yeu_cau=self.yc, trang_thai=LM.CHO).exists())

    def test_PB06_accept_qua_giao_dien_va_email_bao_nvts(self):
        self.dang_nhap(self.gs_b)
        mail.outbox.clear()
        self.client.post(reverse("loi_moi_nhan", args=[self.lm_b.pk]))
        self.yc.refresh_from_db()
        self.assertEqual(self.yc.gia_su, self.gs_b)
        self.assertEqual(mail.outbox[-1].to, ["ts@test.local"])

    def test_PB24_gia_su_khong_phan_hoi_loi_moi_cua_nguoi_khac(self):
        self.dang_nhap(self.gs_b)
        r = self.client.post(reverse("loi_moi_nhan", args=[self.lm_a.pk]))
        self.assertEqual(r.status_code, 404)
        self.lm_a.refresh_from_db()
        self.assertEqual(self.lm_a.trang_thai, LM.CHO)

    def test_PB24_trang_loi_moi_khong_lo_sdt_phu_huynh(self):
        self.dang_nhap(self.gs_a)
        r = self.client.get(reverse("loi_moi_cua_toi"))
        self.assertContains(r, "Thi vào 10")
        self.assertNotContains(r, "84905123456")
        self.assertNotContains(r, "Phụ Huynh")


class SuaLoiCodeReviewYeuCauTest(DuLieu):
    """Hồi quy cho các lỗi code-review tìm ra (07/11/2026)."""

    def setUp(self):
        super().setUp()
        self.lm_a = self.moi(self.gs_a)[0]

    def assert_loi_moi_bi_huy(self):
        self.lm_a.refresh_from_db()
        self.assertEqual(self.lm_a.trang_thai, LM.VOIDED)

    def test_PB22_khoa_tai_khoan_gia_su_huy_loi_moi_dang_cho(self):
        self.dang_nhap(self.admin)
        self.client.post(reverse("tai_khoan_doi_trang_thai", args=[self.gs_a.pk]))
        self.assert_loi_moi_bi_huy()

    def test_PB22_doi_vai_tro_gia_su_huy_loi_moi_dang_cho(self):
        self.dang_nhap(self.admin)
        self.client.post(reverse("tai_khoan_sua", args=[self.gs_a.pk]), {
            "ho_ten": "An", "email": "gsa@test.local", "so_dien_thoai": "", "vai_tro": User.VaiTro.TUYEN_SINH})
        self.assert_loi_moi_bi_huy()

    def test_PB22_tam_ngung_ho_so_huy_loi_moi_dang_cho(self):
        from core.services.gia_su import doi_trang_thai_ho_so
        doi_trang_thai_ho_so(self.admin, self.gs_a.ho_so_gia_su, HoSoGiaSu.TrangThai.TAM_NGUNG)
        self.assert_loi_moi_bi_huy()

    def test_PB22_thu_hoi_mon_huy_loi_moi_cua_mon_do(self):
        from core.services.gia_su import tu_choi_mon
        tu_choi_mon(self.admin, MonGiaSu.objects.get(ho_so__user=self.gs_a), "Phản hồi xấu")
        self.assert_loi_moi_bi_huy()

    def test_PB03_id_trung_khong_bao_bo_qua_sai(self):
        moi, bo_qua = dv.gui_loi_moi(self.nvts, self.yc, [self.gs_b.pk, self.gs_b.pk])
        self.assertEqual((len(moi), bo_qua), (1, 0))

    def test_PB03_doi_tuong_cu_khong_gui_duoc_loi_moi_cho_yeu_cau_da_phan_cong(self):
        cu = YeuCauHocTap.objects.get(pk=self.yc.pk)  # đọc trước khi có người nhận
        dv.chap_nhan(self.gs_a, self.lm_a)
        with self.assertRaises(ValidationError):
            dv.gui_loi_moi(self.nvts, cu, [self.gs_b.pk])
        self.assertFalse(LoiMoi.objects.filter(gia_su=self.gs_b).exists())

    def test_PB03_email_loi_moi_co_link_day_du(self):
        self.assertIn("http://", mail.outbox[0].body)
        self.assertIn("/loi-moi/", mail.outbox[0].body)
