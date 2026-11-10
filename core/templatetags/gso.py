"""Filter/tag cho giao diện mới (bộ UI Gia Sư Online)."""

from django import template
from django.utils import timezone

register = template.Library()

THU = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
THU_NGAN = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def _ngay(gt):
    if gt is None:
        return None
    if hasattr(gt, "hour") and timezone.is_aware(gt):
        gt = timezone.localtime(gt)
    return gt


@register.filter
def ngay_day_du(gt):
    """09/11/2026 → "Thứ Hai, 09/11/2026"."""
    gt = _ngay(gt)
    return f"{THU[gt.weekday()]}, {gt:%d/%m/%Y}" if gt else ""


@register.filter
def thu_ngan(gt):
    gt = _ngay(gt)
    return THU_NGAN[gt.weekday()] if gt else ""


@register.filter
def tien(so):
    """1250000 → "1.250.000đ"."""
    if so in (None, ""):
        return "—"
    return f"{int(so):,}đ".replace(",", ".")


@register.filter
def loai_toast(tags):
    return {"success": "ok", "error": "loi", "warning": "canh"}.get(tags or "", "tin")


@register.filter
def icon_toast(tags):
    return {"success": "bi-check-lg", "error": "bi-exclamation-circle", "warning": "bi-exclamation-triangle"}.get(
        tags or "", "bi-info-circle")
