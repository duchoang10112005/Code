"""Thẻ template dùng chung cho giao diện.

    {% load giao_dien %}
    {% nhan_trang_thai buoi "trang_thai" %}   → nhãn có màu + biểu tượng + chữ

Mọi trạng thái trong hệ thống được ánh xạ về 1 trong 6 sắc thái ở BANG_TRANG_THAI,
nên một trạng thái luôn hiển thị giống nhau ở mọi màn hình.
"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# giá trị trạng thái → (sắc thái, biểu tượng Bootstrap Icons)
BANG_TRANG_THAI = {
    # D2 – hồ sơ gia sư / môn dạy
    "CHO_DUYET": ("warning", "hourglass-split"),
    "DA_DUYET": ("success", "patch-check"),
    "TU_CHOI": ("danger", "x-octagon"),
    "HOAT_DONG": ("success", "check-circle"),
    "TAM_NGUNG": ("neutral", "pause-circle"),
    # D4 – yêu cầu học tập
    "MOI": ("info", "inbox"),
    "DANG_TIM": ("warning", "search"),
    "DA_PHAN_CONG": ("progress", "person-check"),
    "HOC_THU_XONG": ("progress", "flag"),
    "CHINH_THUC": ("success", "mortarboard"),
    "DONG": ("neutral", "archive"),
    # D5 – lời mời
    "CHO": ("warning", "envelope"),
    "ACCEPTED": ("success", "hand-thumbs-up"),
    "REJECTED": ("neutral", "hand-thumbs-down"),
    "VOIDED": ("neutral", "slash-circle"),
    "HET_HAN": ("neutral", "clock-history"),
    # D6 – khóa học
    "DANG_HOC": ("progress", "play-circle"),
    "HOAN_THANH": ("success", "check2-all"),
    "TAM_DUNG": ("warning", "pause-circle"),
    "HUY": ("neutral", "x-circle"),
    # D7 – buổi học
    "LOI_ZOOM": ("danger", "camera-video-off"),
    "DA_LEN_LICH": ("info", "calendar-check"),
    "HOAN_TAT": ("success", "check-circle-fill"),
    "DANG_XEM_XET": ("warning", "eye"),
    "DA_HUY": ("neutral", "x-circle"),
    # D7 – hậu kiểm, bản ghi, Zalo
    "CHUA_KIEM_TRA": ("neutral", "dash-circle"),
    "HOP_LE": ("success", "shield-check"),
    "CO_VAN_DE": ("danger", "shield-exclamation"),
    "DA_XU_LY": ("info", "check2-square"),
    "KHONG_DU_LIEU": ("neutral", "question-circle"),
    "KHONG_GHI": ("neutral", "camera-video-off"),
    "CHO_XU_LY": ("info", "hourglass"),
    "SAN_SANG": ("success", "play-btn"),
    "LOI": ("danger", "exclamation-triangle"),
    "CHUA_GUI": ("neutral", "send"),
    "DA_GUI": ("success", "send-check"),
    # D8 – thù lao
    "TAM_TINH": ("info", "calculator"),
    "TAM_GIU": ("warning", "lock"),
    "DA_DOI_SOAT": ("success", "clipboard-check"),
}


def _nhan(gia_tri, chu):
    tone, icon = BANG_TRANG_THAI.get(gia_tri, ("neutral", "circle"))
    return format_html('<span class="nhan-tt tone-{}"><i class="bi bi-{}" aria-hidden="true"></i>{}</span>', tone, icon, chu)


@register.simple_tag
def nhan_trang_thai(obj, truong="trang_thai"):
    """Nhãn cho một trường có choices của model, VD {% nhan_trang_thai yeu_cau "trang_thai" %}."""
    gia_tri = getattr(obj, truong)
    chu = getattr(obj, f"get_{truong}_display")()
    return _nhan(gia_tri, chu)


@register.simple_tag
def nhan_tuy_chinh(gia_tri, chu):
    """Nhãn từ giá trị + chữ tự đặt (dùng cho trang xem trước, hoặc trạng thái không phải choices)."""
    return _nhan(gia_tri, chu)


@register.simple_tag
def nhan_tai_khoan(user):
    if user.is_active:
        return _nhan("HOAT_DONG", "Hoạt động")
    # Chuỗi cố định, không có dữ liệu người dùng → mark_safe (Django 6 không cho format_html không tham số).
    return mark_safe('<span class="nhan-tt tone-danger"><i class="bi bi-lock-fill" aria-hidden="true"></i>Bị khóa</span>')


@register.simple_tag
def ten_thu(so):
    """0 → "Thứ 2" … 6 → "Chủ nhật"."""
    from core.models import LichRanh
    return dict(LichRanh.Thu.choices).get(so, so)


@register.filter
def con_lai(thoi_diem):
    """Thời gian còn lại đến `thoi_diem`, tiếng Việt: "23 giờ 54 phút", "12 phút", "đã quá hạn"."""
    from django.utils import timezone
    giay = int((thoi_diem - timezone.now()).total_seconds())
    if giay <= 0:
        return "đã quá hạn"
    gio, phut = divmod(giay // 60, 60)
    if gio and phut:
        return f"{gio} giờ {phut} phút"
    return f"{gio} giờ" if gio else f"{max(phut, 1)} phút"


@register.filter
def tien(so):
    """{{ khoa.hoc_phi_moi_buoi|tien }} → 200.000đ"""
    from core.services.tien_ich import dinh_dang_tien
    return dinh_dang_tien(so)



@register.filter
def da_qua(thoi_diem):
    """Thời gian đã trôi qua từ `thoi_diem`, tiếng Việt: "2 ngày", "14 giờ", "5 phút"."""
    from django.utils import timezone
    if not thoi_diem:
        return ""
    phut = max(int((timezone.now() - thoi_diem).total_seconds()) // 60, 0)
    if phut >= 1440:
        return f"{phut // 1440} ngày"
    if phut >= 60:
        return f"{phut // 60} giờ"
    return f"{max(phut, 1)} phút"
