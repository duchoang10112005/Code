"""Zoom: phòng bị trống rồi mở lại = nhiều lượt họp (mỗi lượt một bản ghi + một báo cáo). Gom đủ mọi lượt."""

from datetime import datetime, timezone as tz
from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.integrations.zoom import RealZoomClient


def tra(code, j=None):
    r = mock.Mock()
    r.status_code = code
    r.json.return_value = j or {}
    r.text = str(j)
    return r


@override_settings(ZOOM_MODE="real", ZOOM_ACCOUNT_ID="a", ZOOM_CLIENT_ID="b", ZOOM_CLIENT_SECRET="c",
                   ZOOM_HOST_EMAIL_MAC_DINH="gs@x.vn")
class NhieuLuotTest(SimpleTestCase):
    def tao_client(self, bang):
        z = RealZoomClient()
        goi = []

        def _goi(method, duong_dan, **kw):
            goi.append(duong_dan)
            for k, v in bang.items():
                if duong_dan.startswith(k):
                    return v
            return tra(404)
        z._goi = _goi
        z.goi = goi
        return z

    def test_gom_ban_ghi_moi_luot_chon_doan_dai_nhat(self):
        z = self.tao_client({
            "/past_meetings/123/instances": tra(200, {"meetings": [
                {"uuid": "b/B==", "start_time": "2026-11-21T11:30:00Z"}, {"uuid": "a+A==", "start_time": "2026-11-21T11:00:00Z"}]}),
            "/meetings/a%252BA%253D%253D/recordings": tra(200, {"share_url": "https://z/1", "password": "p1",
                                                                 "start_time": "2026-11-21T11:00:00Z", "duration": 40}),
            "/meetings/b%252FB%253D%253D/recordings": tra(200, {"share_url": "https://z/2", "password": "p2",
                                                                 "start_time": "2026-11-21T11:30:00Z", "duration": 5}),
        })
        bg = z.lay_ban_ghi("123")
        self.assertTrue(bg.san_sang)
        self.assertEqual([d["url"] for d in bg.cac_doan], ["https://z/1", "https://z/2"])  # theo giờ
        self.assertEqual((bg.share_url, bg.passcode), ("https://z/1", "p1"))  # đoạn dài nhất làm bản chính

    def test_thieu_quyen_instances_thi_chi_lay_luot_gan_nhat(self):
        z = self.tao_client({"/past_meetings/123/instances": tra(400),
                         "/meetings/123/recordings": tra(200, {"share_url": "https://z/x", "duration": 7,
                                                               "start_time": "2026-11-21T11:00:00Z"})})
        bg = z.lay_ban_ghi("123")
        self.assertEqual((bg.share_url, len(bg.cac_doan)), ("https://z/x", 1))

    def test_khong_co_ban_ghi_nao(self):
        z = self.tao_client({"/past_meetings/123/instances": tra(200, {"meetings": [{"uuid": "u1", "start_time": "x"}]})})
        bg = z.lay_ban_ghi("123")
        self.assertFalse(bg.san_sang)

    def test_nguoi_tham_gia_cong_gop_cac_luot(self):
        z = self.tao_client({
            "/past_meetings/123/instances": tra(200, {"meetings": [{"uuid": "u1", "start_time": "1"}, {"uuid": "u2", "start_time": "2"}]}),
            "/users/gs": tra(200, {"id": "H1", "email": "gs@x.vn"}),
            "/report/meetings/u1/participants": tra(200, {"participants": [
                {"id": "H1", "name": "GS", "join_time": "2026-11-21T11:00:00Z", "leave_time": "2026-11-21T11:20:00Z"},
                {"id": "", "name": "HV", "join_time": "2026-11-21T11:01:00Z", "leave_time": "2026-11-21T11:20:00Z"}]}),
            "/report/meetings/u2/participants": tra(200, {"participants": [
                {"id": "H1", "name": "GS", "join_time": "2026-11-21T11:30:00Z", "leave_time": "2026-11-21T11:50:00Z"}]}),
        })
        ds = z.lay_nguoi_tham_gia("123")
        self.assertEqual(len(ds), 3)
        gs = [p for p in ds if p.la_host]
        self.assertEqual(len(gs), 2)
        self.assertEqual(min(p.vao_luc for p in gs), datetime(2026, 11, 21, 11, 0, tzinfo=tz.utc))


class DoanNganBiAnTest(SimpleTestCase):
    def test_an_doan_ngan_giu_doan_chinh_va_doan_dai(self):
        from core.models import BuoiHoc
        b = BuoiHoc(ban_ghi_url="https://z/chinh", ban_ghi_cac_doan=[
            {"url": "https://z/a", "phut": 0}, {"url": "https://z/b", "phut": 2},
            {"url": "https://z/chinh", "phut": 68}, {"url": "https://z/c", "phut": 20}])
        self.assertEqual([d["url"] for d in b.doan_ghi_dang_ke], ["https://z/chinh", "https://z/c"])
        b.ban_ghi_cac_doan = [{"url": "https://z/a", "phut": 0}, {"url": "https://z/chinh", "phut": 68}]
        self.assertEqual(len(b.doan_ghi_dang_ke), 1)  # chỉ còn đoạn chính → giao diện không hiện danh sách
