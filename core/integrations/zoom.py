"""Tích hợp Zoom qua lớp trung gian (adapter).

Code nghiệp vụ chỉ gọi `lay_zoom_client()` và các hàm của ZoomClient, không quan tâm
đang chạy giả lập hay thật. Chọn chế độ bằng ZOOM_MODE trong file .env.

- FakeZoomClient: dùng khi demo/test, không cần mạng, không cần tài khoản Zoom.
- RealZoomClient: gọi Zoom API thật (Server-to-Server OAuth) — hoàn thiện ở Phần 5.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

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

    def xoa_phong(self, meeting_id) -> None:
        raise NotImplementedError

    def lay_nguoi_tham_gia(self, meeting_id) -> list[NguoiThamGia]:
        raise NotImplementedError

    def lay_ban_ghi(self, meeting_id) -> ThongTinBanGhi:
        raise NotImplementedError


@dataclass
class FakeZoomClient(ZoomClient):
    """Giả lập Zoom. Đặt `kich_ban_tham_gia` trong test để mô phỏng học viên có/không vào phòng."""

    phong_da_tao: dict = field(default_factory=dict)
    kich_ban_tham_gia: dict = field(default_factory=dict)  # meeting_id -> list[NguoiThamGia]

    def tao_phong(self, host_email, chu_de, bat_dau, thoi_luong_phut, ghi_hinh):
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

    def xoa_phong(self, meeting_id):
        self.phong_da_tao.pop(meeting_id, None)

    def lay_nguoi_tham_gia(self, meeting_id):
        return self.kich_ban_tham_gia.get(meeting_id, [])

    def lay_ban_ghi(self, meeting_id):
        return ThongTinBanGhi(
            san_sang=True,
            share_url=f"https://zoom.us/rec/share/gia-lap-{meeting_id}",
            passcode="Rec@123",
        )


class RealZoomClient(ZoomClient):
    def __init__(self):
        if not (settings.ZOOM_ACCOUNT_ID and settings.ZOOM_CLIENT_ID and settings.ZOOM_CLIENT_SECRET):
            raise ZoomError("Chưa cấu hình ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET trong .env")

    # Các hàm gọi API thật sẽ được viết ở Phần 5.


_fake_singleton = FakeZoomClient()


def lay_zoom_client() -> ZoomClient:
    if settings.ZOOM_MODE == "real":
        return RealZoomClient()
    return _fake_singleton
