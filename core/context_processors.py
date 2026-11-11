from django.conf import settings
from django.db.models import F
from django.utils import timezone


def thong_tin_chung(request):
    """Biến dùng chung cho mọi template (menu, huy hiệu, chuông thông báo)."""
    # Tăng PHIEN_BAN_CSS mỗi khi sửa static/css/*.css hoặc static/js/gso.js để trình duyệt tải bản mới.
    data = {"TEN_HE_THONG": "Gia Sư Online", "PHIEN_BAN_CSS": "3.7",
            "THOI_LUONG_BUOI_DEMO": settings.NGHIEP_VU.get("THOI_LUONG_BUOI_DEMO", 0),
            "GIAY_HOAN_TAC": settings.NGHIEP_VU.get("GIAY_HOAN_TAC", 6)}
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return data

    from core.models import BuoiHoc, DoiGiaSu, KhoaHoc, LoiMoi, MonGiaSu, YeuCauXuLy, YeuCauHocTap
    now = timezone.now()
    hh = {}
    if user.la_admin:
        hh["so_mon_cho_duyet"] = MonGiaSu.objects.filter(
            trang_thai=MonGiaSu.TrangThai.CHO_DUYET, ho_so__user__vai_tro="GIA_SU").count()
        from core.services.xem_xet import tat_ca
        hh["so_can_xem_xet"] = len(tat_ca())
    elif user.la_tuyen_sinh:
        YC = YeuCauHocTap.TrangThai
        hh["so_yeu_cau_can_xu_ly"] = (
            YeuCauHocTap.objects.filter(trang_thai=YC.MOI).count()
            + YeuCauHocTap.objects.filter(trang_thai=YC.DANG_TIM).exclude(
                loi_moi__trang_thai=LoiMoi.TrangThai.CHO).count())
        from core.services.hau_kiem import so_cho
        hh["so_hau_kiem_cho"] = so_cho(user)
        hh["so_khoa_sap_het"] = KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).annotate(
            con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung")).filter(
            con_lai__lte=settings.NGHIEP_VU.get("NGUONG_SAP_HET_BUOI", 2)).count()
    elif user.la_gia_su:
        hh["so_loi_moi_cho"] = user.loi_moi.filter(trang_thai="CHO", het_han_luc__gt=now).count()
        hh["so_buoi_cho_xac_nhan"] = user.buoi_hoc.filter(
            trang_thai="DA_LEN_LICH", ket_thuc_luc__lte=now, han_xac_nhan__gte=now).count()
    data.update(hh)  # giữ tên biến cũ cho các trang chưa chuyển giao diện

    from core.menu import THONG_TIN_VAI_TRO, chu_viet_tat, lenh_cho, menu_cho
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    data.update({
        "MENU": menu_cho(user, url_name, hh),
        "LENH_NHANH": lenh_cho(user),
        "VAI_TRO": THONG_TIN_VAI_TRO.get(user.vai_tro, THONG_TIN_VAI_TRO["ADMIN"]),
        "CHU_VIET_TAT": chu_viet_tat(user.ho_ten),
        "SO_THONG_BAO": user.thong_bao.filter(da_doc=False).count(),
        "HOM_NAY": timezone.localdate(),
    })
    return data
