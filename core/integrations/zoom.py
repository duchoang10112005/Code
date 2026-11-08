"""Tích hợp Zoom qua lớp trung gian (adapter).

Code nghiệp vụ chỉ gọi `lay_zoom_client()` và các hàm của ZoomClient, không quan tâm
đang chạy giả lập hay thật. Chọn chế độ bằng ZOOM_MODE trong file .env.

- FakeZoomClient: dùng khi demo/test, không cần mạng, không cần tài khoản Zoom.
- RealZoomClient: gọi Zoom API thật (Server-to-Server OAuth), dùng 1 tài khoản Zoom của trung tâm.
"""

import base64
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings


class ZoomError(Exception):
    """Lỗi khi gọi Zoom (mạng, sai khóa, hết quota…). View bắt lỗi này để báo người dùng."""


@dataclass
class ThongTinPhong:
    meeting_id: str
    join_url: str
    start_url: str
    passcode: str


@dataclass
class NguoiThamGia:
    ten: str
    email: str
    vao_luc: datetime
    ra_luc: datetime
    la_host: bool = False


@dataclass
class ThongTinBanGhi:
    san_sang: bool
    share_url: str = ""
    passcode: str = ""
    ghi_chu: str = ""


class ZoomClient:
    def tao_phong(self, host_email, chu_de, bat_dau, thoi_luong_phut, ghi_hinh) -> ThongTinPhong:
        raise NotImplementedError

    def lay_start_url(self, meeting_id) -> str:
        """Link mở phòng cho host. Link nhận lúc tạo phòng chỉ dùng được ~2 giờ nên lấy mới mỗi lần mở."""
        raise NotImplementedError

    def xoa_phong(self, meeting_id) -> None:
        raise NotImplementedError

    def lay_nguoi_tham_gia(self, meeting_id) -> list[NguoiThamGia] | None:
        """None = gói Zoom không cung cấp dữ liệu này (VD gói Free) → không hậu kiểm được."""
        raise NotImplementedError

    def lay_ban_ghi(self, meeting_id) -> ThongTinBanGhi:
        raise NotImplementedError


@dataclass
class FakeZoomClient(ZoomClient):
    """Giả lập Zoom. Trong test: đặt `kich_ban_tham_gia[meeting_id]` để mô phỏng học viên có/không vào phòng;
    `gia_lap_loi = True` để mô phỏng Zoom lỗi khi tạo phòng."""

    phong_da_tao: dict = field(default_factory=dict)
    kich_ban_tham_gia: dict = field(default_factory=dict)  # meeting_id -> list[NguoiThamGia]
    gia_lap_loi: bool = False

    def tao_phong(self, host_email, chu_de, bat_dau, thoi_luong_phut, ghi_hinh):
        if self.gia_lap_loi:
            raise ZoomError("Giả lập: Zoom không phản hồi")
        mid = str(random.randint(80_000_000_000, 89_999_999_999))
        passcode = f"{random.randint(0, 999999):06d}"
        phong = ThongTinPhong(
            meeting_id=mid,
            join_url=f"https://zoom.us/j/{mid}?pwd=gia-lap",
            start_url=f"https://zoom.us/s/{mid}?zak=gia-lap",
            passcode=passcode,
        )
        self.phong_da_tao[mid] = phong
        return phong

    def lay_start_url(self, meeting_id):
        return f"https://zoom.us/s/{meeting_id}?zak=gia-lap"

    def xoa_phong(self, meeting_id):
        self.phong_da_tao.pop(meeting_id, None)

    def lay_nguoi_tham_gia(self, meeting_id):
        # Không có kịch bản → coi như gói Zoom không trả dữ liệu tham gia (giống tài khoản Free).
        return self.kich_ban_tham_gia.get(meeting_id)

    def lay_ban_ghi(self, meeting_id):
        return ThongTinBanGhi(
            san_sang=True,
            share_url=f"https://zoom.us/rec/share/gia-lap-{meeting_id}",
            passcode="Rec@123",
        )


API = "https://api.zoom.us/v2"
_token_cache = {"token": "", "het_han": 0.0}


def _thoi_gian_zoom(s):
    """'2026-11-08T12:00:00Z' → datetime có múi giờ."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


class RealZoomClient(ZoomClient):
    """Server-to-Server OAuth app trên marketplace.zoom.us (hướng dẫn trong README_DEMO.md).

    Mọi phòng tạo dưới 1 tài khoản host (ZOOM_HOST_EMAIL_MAC_DINH; để trống = chủ tài khoản "me").
    Gói Free: buổi tối đa 40 phút, không có cloud recording, không có báo cáo người tham gia.
    """

    def __init__(self):
        if not (settings.ZOOM_ACCOUNT_ID and settings.ZOOM_CLIENT_ID and settings.ZOOM_CLIENT_SECRET):
            raise ZoomError("Chưa cấu hình ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET trong .env")
        self.host = settings.ZOOM_HOST_EMAIL_MAC_DINH or "me"

    # Token hết hạn sau 1 giờ → giữ trong bộ nhớ, không xin lại mỗi lần gọi.
    def _token(self):
        if _token_cache["token"] and time.time() < _token_cache["het_han"] - 60:
            return _token_cache["token"]
        cap = base64.b64encode(f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}".encode()).decode()
        try:
            r = requests.post("https://zoom.us/oauth/token",
                              params={"grant_type": "account_credentials", "account_id": settings.ZOOM_ACCOUNT_ID},
                              headers={"Authorization": f"Basic {cap}"}, timeout=15)
        except requests.RequestException as exc:
            raise ZoomError(f"Không kết nối được Zoom: {exc}") from exc
        if r.status_code != 200:
            raise ZoomError(f"Zoom từ chối khóa (HTTP {r.status_code}). Kiểm tra lại 3 khóa trong .env "
                            "và app đã được Activate chưa.")
        j = r.json()
        _token_cache.update(token=j["access_token"], het_han=time.time() + int(j.get("expires_in", 3600)))
        return _token_cache["token"]

    def _goi(self, method, duong_dan, **kw):
        try:
            return requests.request(method, API + duong_dan, timeout=20,
                                    headers={"Authorization": f"Bearer {self._token()}"}, **kw)
        except requests.RequestException as exc:
            raise ZoomError(f"Không kết nối được Zoom: {exc}") from exc

    @staticmethod
    def _loi(r, viec):
        try:
            msg = r.json().get("message", "")
        except ValueError:
            msg = r.text[:200]
        return ZoomError(f"Zoom lỗi khi {viec} (HTTP {r.status_code}): {msg}")

    def tao_phong(self, host_email, chu_de, bat_dau, thoi_luong_phut, ghi_hinh):
        body = {
            "topic": chu_de[:200],
            "type": 2,  # cuộc họp có lịch
            "start_time": bat_dau.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration": thoi_luong_phut,
            "timezone": "Asia/Ho_Chi_Minh",
            "settings": {
                "join_before_host": False,
                "waiting_room": False,
                "mute_upon_entry": True,
                "auto_recording": "cloud" if ghi_hinh else "none",
            },
        }
        r = self._goi("POST", f"/users/{host_email or self.host}/meetings", json=body)
        if r.status_code != 201:
            raise self._loi(r, "tạo phòng")
        j = r.json()
        return ThongTinPhong(meeting_id=str(j["id"]), join_url=j["join_url"],
                             start_url=j["start_url"], passcode=j.get("password", ""))

    def lay_start_url(self, meeting_id):
        r = self._goi("GET", f"/meetings/{meeting_id}")
        if r.status_code != 200:
            raise self._loi(r, "lấy link mở phòng")
        return r.json()["start_url"]

    def xoa_phong(self, meeting_id):
        r = self._goi("DELETE", f"/meetings/{meeting_id}")
        if r.status_code not in (204, 404):  # 404: phòng không còn → coi như đã xóa
            raise self._loi(r, "xóa phòng")

    def lay_nguoi_tham_gia(self, meeting_id):
        r = self._goi("GET", f"/report/meetings/{meeting_id}/participants", params={"page_size": 300})
        if r.status_code in (400, 401, 403):
            return None  # gói Free không có báo cáo, hoặc app thiếu quyền report:read
        if r.status_code != 200:
            raise self._loi(r, "lấy danh sách người tham gia")  # VD 404 khi Zoom chưa tổng hợp xong
        host_id, host_email = self._thong_tin_host()
        ds = []
        for p in r.json().get("participants", []):
            email = (p.get("user_email") or "").lower()
            ds.append(NguoiThamGia(
                ten=p.get("name", ""), email=email,
                vao_luc=_thoi_gian_zoom(p.get("join_time")), ra_luc=_thoi_gian_zoom(p.get("leave_time")),
                la_host=(bool(host_id) and p.get("id") == host_id) or (bool(email) and email == host_email),
            ))
        return ds

    def _thong_tin_host(self):
        """(id, email) của tài khoản host: gia sư mở phòng bằng link host nên Zoom ghi nhận là tài khoản này."""
        r = self._goi("GET", f"/users/{self.host}")
        if r.status_code != 200:
            return "", self.host.lower()
        j = r.json()
        return j.get("id", ""), (j.get("email") or "").lower()

    def lay_ban_ghi(self, meeting_id):
        r = self._goi("GET", f"/meetings/{meeting_id}/recordings")
        if r.status_code == 404:
            return ThongTinBanGhi(san_sang=False, ghi_chu="Zoom chưa có bản ghi")
        if r.status_code in (400, 401, 403):
            return ThongTinBanGhi(san_sang=False, ghi_chu="Gói Zoom không hỗ trợ ghi hình trên cloud")
        if r.status_code != 200:
            raise self._loi(r, "lấy bản ghi")
        j = r.json()
        return ThongTinBanGhi(san_sang=bool(j.get("share_url")), share_url=j.get("share_url", ""),
                              passcode=j.get("password", ""))


_fake_singleton = FakeZoomClient()


def lay_zoom_client() -> ZoomClient:
    if settings.ZOOM_MODE == "real":
        return RealZoomClient()
    return _fake_singleton
