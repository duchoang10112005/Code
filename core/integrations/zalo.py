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

    def gui_zns(self, sdt_84, du_lieu_template):
        import uuid

        import requests

        try:
            r = requests.post(
                "https://business.openapi.zalo.me/message/template",
                headers={"access_token": settings.ZALO_ACCESS_TOKEN, "Content-Type": "application/json"},
                json={"phone": sdt_84, "template_id": settings.ZALO_TEMPLATE_ID,
                      "template_data": du_lieu_template, "tracking_id": uuid.uuid4().hex},
                timeout=15,
            )
            j = r.json()
        except (requests.RequestException, ValueError) as exc:
            return KetQuaGui(False, f"Không kết nối được Zalo: {exc}")
        if j.get("error") == 0:
            return KetQuaGui(True, f"OK msg_id={j.get('data', {}).get('msg_id', '')}")
        return KetQuaGui(False, f"Zalo lỗi {j.get('error')}: {j.get('message', '')}")


_fake_singleton = FakeZaloClient()


def lay_zalo_client() -> ZaloClient:
    if settings.ZALO_MODE == "real":
        return RealZaloClient()
    return _fake_singleton
