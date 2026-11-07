"""Tích hợp Zalo ZNS qua adapter (giống zoom.py). Chọn chế độ bằng ZALO_MODE trong .env.

ZNS thật cần: OA doanh nghiệp đã xác thực + template đã được Zalo duyệt + access token.
Khi chưa có, dùng FakeZaloClient (ghi nội dung tin vào nhật ký như đã gửi).
"""

from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class KetQuaGui:
    thanh_cong: bool
    phan_hoi: str


class ZaloClient:
    def gui_zns(self, sdt_84, du_lieu_template: dict) -> KetQuaGui:
        raise NotImplementedError


@dataclass
class FakeZaloClient(ZaloClient):
    da_gui: list = field(default_factory=list)
    gia_lap_loi: bool = False

    def gui_zns(self, sdt_84, du_lieu_template):
        if self.gia_lap_loi:
            return KetQuaGui(False, "Giả lập lỗi gửi ZNS")
        self.da_gui.append((sdt_84, du_lieu_template))
        return KetQuaGui(True, "Giả lập: đã gửi")


class RealZaloClient(ZaloClient):
    def __init__(self):
        if not (settings.ZALO_ACCESS_TOKEN and settings.ZALO_TEMPLATE_ID):
            raise RuntimeError("Chưa cấu hình ZALO_ACCESS_TOKEN / ZALO_TEMPLATE_ID trong .env")

    # Gọi API ZNS thật sẽ được viết ở Phần 5.


_fake_singleton = FakeZaloClient()


def lay_zalo_client() -> ZaloClient:
    if settings.ZALO_MODE == "real":
        return RealZaloClient()
    return _fake_singleton
