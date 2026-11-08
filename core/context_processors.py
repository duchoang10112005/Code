from django.utils import timezone


def thong_tin_chung(request):
    """Biến dùng chung cho mọi template (menu, huy hiệu thông báo)."""
    # Tăng PHIEN_BAN_CSS mỗi khi sửa static/css/app.css để trình duyệt tải bản mới.
    data = {"TEN_HE_THONG": "Trung tâm Gia sư Trực tuyến", "PHIEN_BAN_CSS": "2.2"}
    user = getattr(request, "user", None)
    if user and user.is_authenticated and user.la_admin:
        from core.models import MonGiaSu
        data["so_mon_cho_duyet"] = MonGiaSu.objects.filter(
            trang_thai=MonGiaSu.TrangThai.CHO_DUYET, ho_so__user__vai_tro="GIA_SU"
        ).count()
    if user and user.is_authenticated and user.la_gia_su:
        # Tính động, không cần kho "thông báo" riêng.
        data["so_loi_moi_cho"] = user.loi_moi.filter(
            trang_thai="CHO", het_han_luc__gt=timezone.now()
        ).count()
        # Buổi đã qua giờ kết thúc, chưa xác nhận, còn hạn.
        now = timezone.now()
        data["so_buoi_cho_xac_nhan"] = sum(
            1 for b in user.buoi_hoc.filter(trang_thai="DA_LEN_LICH", bat_dau__lte=now, han_xac_nhan__gte=now)
            if b.ket_thuc <= now)
    return data
