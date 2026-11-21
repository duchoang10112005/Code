"""seed_mo_rong: dữ liệu demo phong phú, nhất quán, chạy lại không tạo trùng."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import BuoiHoc, HauKiemBuoi, KhoaHoc, ThuLao, User, YeuCauHocTap
from core.services import xem_xet


class SeedMoRongTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_mo_rong", stdout=StringIO())

    def test_du_trang_thai(self):
        self.assertGreaterEqual(User.objects.filter(vai_tro="GIA_SU").count(), 12)
        self.assertEqual(set(YeuCauHocTap.objects.values_list("trang_thai", flat=True)),
                         {"MOI", "DANG_TIM", "DA_PHAN_CONG", "HOC_THU_XONG", "CHINH_THUC", "DONG"})
        self.assertEqual(set(KhoaHoc.objects.values_list("trang_thai", flat=True)),
                         {"DANG_HOC", "TAM_DUNG", "HOAN_THANH", "HUY"})
        self.assertEqual(set(HauKiemBuoi.objects.values_list("ket_luan", flat=True)), {"CHUA_KIEM_TRA", "HOP_LE", "CO_VAN_DE"})
        _, dem, _ = xem_xet.hang_doi()
        self.assertTrue(all(dem[k] for k in ("mo_lai", "loi", "doi_gia_su", "ho_so")), dem)

    def test_nhat_quan_so_buoi_va_thu_lao(self):
        for k in KhoaHoc.objects.all():
            n = k.buoi_hoc.filter(trang_thai__in=["HOAN_TAT", "DANG_XEM_XET"]).count()
            self.assertEqual(n, k.so_buoi_da_dung, k.ma)
        tinh = BuoiHoc.objects.filter(khoa_hoc__isnull=False, trang_thai__in=["HOAN_TAT", "DANG_XEM_XET"]).count()
        self.assertEqual(ThuLao.objects.count(), tinh)

    def test_chay_lai_khong_tao_trung(self):
        truoc = (User.objects.count(), BuoiHoc.objects.count())
        call_command("seed_mo_rong", stdout=StringIO())
        self.assertEqual((User.objects.count(), BuoiHoc.objects.count()), truoc)
