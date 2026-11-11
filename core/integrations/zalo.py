"""Tích hợp Zalo ZNS qua adapter (giống zoom.py). Chọn chế độ bằng ZALO_MODE trong .env.

ZNS thật cần: OA đã xác thực + liên kết Zalo Cloud Account (có số dư) + template đã được Zalo duyệt
+ app trên developers.zalo.me (App ID, Secret Key). Token OA lấy một lần bằng lệnh
`python manage.py zalo_ket_noi`, sau đó hệ thống tự làm mới (bảng TokenZalo).
Khi chưa có, dùng FakeZaloClient (ghi nội dung tin vào nhật ký như đã gửi).
"""

import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

OAUTH = "https://oauth.zaloapp.com/v4/oa"
ZNS_URL = "https://business.openapi.zalo.me/message/template"

# Độ dài tối đa từng tham số template (Zalo từ chối tin nếu vượt): tên 30, còn lại 100 ký tự.
DO_DAI_THAM_SO = {"ten_hoc_vien": 30, "gia_su": 30, "mon_hoc": 30, "thoi_gian": 30,
                  "danh_gia": 30, "noi_dung": 100, "nhan_xet": 100}


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


# ----------------------------------------------------------------------------- token OA
class LoiZalo(Exception):
    pass


def _goi_oauth(du_lieu):
    import requests
    if not (settings.ZALO_APP_ID and settings.ZALO_SECRET_KEY):
        raise LoiZalo("Chưa cấu hình ZALO_APP_ID / ZALO_SECRET_KEY trong .env")
    try:
        r = requests.post(f"{OAUTH}/access_token", timeout=15, data={"app_id": settings.ZALO_APP_ID, **du_lieu},
                          headers={"secret_key": settings.ZALO_SECRET_KEY,
                                   "Content-Type": "application/x-www-form-urlencoded"})
        j = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise LoiZalo(f"Không kết nối được Zalo: {exc}") from exc
    if not j.get("access_token"):
        raise LoiZalo(f"Zalo từ chối cấp token: {j.get('error_name') or j.get('error')} {j.get('error_description') or j.get('message') or ''}".strip())
    return j


def _luu_token(j):
    from core.models import TokenZalo
    t = TokenZalo.objects.order_by("pk").first() or TokenZalo()
    t.access_token, t.refresh_token = j["access_token"], j.get("refresh_token", t.refresh_token)
    t.het_han_luc = timezone.now() + timedelta(seconds=int(j.get("expires_in", 90000)))
    t.save()
    return t


def tao_link_cap_quyen():
    """→ (url, code_verifier). OAuth v4 có PKCE: mở url bằng tài khoản quản trị OA, bấm Cho phép."""
    verifier = secrets.token_urlsafe(32)[:43]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    from urllib.parse import urlencode
    url = f"{OAUTH}/permission?" + urlencode({"app_id": settings.ZALO_APP_ID, "redirect_uri": settings.ZALO_REDIRECT_URI,
                                              "code_challenge": challenge, "state": uuid.uuid4().hex[:8]})
    return url, verifier


def doi_code_lay_token(code, verifier):
    return _luu_token(_goi_oauth({"code": code, "grant_type": "authorization_code", "code_verifier": verifier}))


def lay_access_token():
    """Token còn hạn (> 10 phút) thì dùng; sắp hết thì làm mới bằng refresh token rồi lưu cặp mới."""
    from django.db import transaction
    from core.models import TokenZalo
    with transaction.atomic():
        t = TokenZalo.objects.select_for_update().order_by("pk").first()
        if t and t.access_token and t.het_han_luc and t.het_han_luc > timezone.now() + timedelta(minutes=10):
            return t.access_token
        if t and t.refresh_token:
            return _luu_token(_goi_oauth({"refresh_token": t.refresh_token, "grant_type": "refresh_token"})).access_token
    if settings.ZALO_ACCESS_TOKEN:  # dán tay (sống ~25 giờ) – chỉ để thử nhanh
        return settings.ZALO_ACCESS_TOKEN
    raise LoiZalo("Chưa kết nối Zalo OA. Chạy: python manage.py zalo_ket_noi")


# ----------------------------------------------------------------------------- gửi ZNS
def chuan_hoa_tham_so(du_lieu):
    return {k: str(v or "—")[:DO_DAI_THAM_SO.get(k, 100)] for k, v in du_lieu.items()}


class RealZaloClient(ZaloClient):
    def __init__(self):
        if not settings.ZALO_TEMPLATE_ID:
            raise RuntimeError("Chưa cấu hình ZALO_TEMPLATE_ID trong .env")

    def gui_zns(self, sdt_84, du_lieu_template):
        import requests
        try:
            token = lay_access_token()
        except LoiZalo as exc:
            return KetQuaGui(False, str(exc))
        body = {"phone": sdt_84, "template_id": settings.ZALO_TEMPLATE_ID,
                "template_data": chuan_hoa_tham_so(du_lieu_template), "tracking_id": uuid.uuid4().hex}
        if settings.ZALO_ZNS_DEV:
            body["mode"] = "development"  # chỉ gửi tới SĐT quản trị viên của app, dùng khi thử nghiệm
        try:
            r = requests.post(ZNS_URL, headers={"access_token": token, "Content-Type": "application/json"},
                              json=body, timeout=15)
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
