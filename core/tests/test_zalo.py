"""Zalo ZNS thật: token OA tự làm mới (refresh token dùng 1 lần), chuẩn hóa tham số, gửi lại khi lỗi."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from core.integrations import zalo
from core.models import TokenZalo

CAU_HINH = dict(ZALO_MODE="real", ZALO_APP_ID="123", ZALO_SECRET_KEY="bi-mat", ZALO_TEMPLATE_ID="999",
                ZALO_ACCESS_TOKEN="", ZALO_ZNS_DEV=False, ZALO_REDIRECT_URI="https://vd.vn/cb")


def phan_hoi(j):
    r = mock.Mock()
    r.json.return_value = j
    return r


@override_settings(**CAU_HINH)
class TokenZaloTest(TestCase):
    def test_con_han_thi_dung_lai(self):
        TokenZalo.objects.create(access_token="A", refresh_token="R", het_han_luc=timezone.now() + timedelta(hours=5))
        with mock.patch("requests.post") as p:
            self.assertEqual(zalo.lay_access_token(), "A")
            p.assert_not_called()

    def test_sap_het_han_thi_lam_moi_va_luu_cap_moi(self):
        TokenZalo.objects.create(access_token="A", refresh_token="R1", het_han_luc=timezone.now() + timedelta(minutes=3))
        with mock.patch("requests.post", return_value=phan_hoi(
                {"access_token": "B", "refresh_token": "R2", "expires_in": "90000"})) as p:
            self.assertEqual(zalo.lay_access_token(), "B")
        self.assertEqual(p.call_args.kwargs["data"]["refresh_token"], "R1")
        self.assertEqual(p.call_args.kwargs["headers"]["secret_key"], "bi-mat")
        t = TokenZalo.objects.get()
        self.assertEqual((t.access_token, t.refresh_token), ("B", "R2"))
        self.assertGreater(t.het_han_luc, timezone.now() + timedelta(hours=24))

    def test_chua_ket_noi_thi_bao_ro(self):
        with self.assertRaisesMessage(zalo.LoiZalo, "zalo_ket_noi"):
            zalo.lay_access_token()

    def test_gui_zns_cat_tham_so_va_che_do_dev(self):
        TokenZalo.objects.create(access_token="A", refresh_token="R", het_han_luc=timezone.now() + timedelta(hours=5))
        with override_settings(ZALO_ZNS_DEV=True), mock.patch("requests.post", return_value=phan_hoi(
                {"error": 0, "data": {"msg_id": "m1"}})) as p:
            kq = zalo.lay_zalo_client().gui_zns("84905123456", {"ten_hoc_vien": "x" * 50, "nhan_xet": None})
        self.assertTrue(kq.thanh_cong)
        body = p.call_args.kwargs["json"]
        self.assertEqual((body["mode"], len(body["template_data"]["ten_hoc_vien"]), body["template_data"]["nhan_xet"]),
                         ("development", 30, "—"))
        self.assertEqual(p.call_args.kwargs["headers"]["access_token"], "A")

    def test_link_cap_quyen_co_pkce(self):
        url, verifier = zalo.tao_link_cap_quyen()
        self.assertIn("app_id=123", url)
        self.assertIn("code_challenge=", url)
        self.assertEqual(len(verifier), 43)
