"""API hồ sơ gia sư (SD-26)."""

from core.api import api, doc_du_lieu, tra_ve
from core.models import HoSoGiaSu
from core.services import gia_su as dv


@api(vai_tro=("GIA_SU",), phuong_thuc=("POST",))
def gio_ranh(request):
    ho_so, _ = HoSoGiaSu.objects.get_or_create(user=request.user)
    du_lieu = doc_du_lieu(request)
    ds = du_lieu.get("khung") if isinstance(du_lieu.get("khung"), list) else request.POST.getlist("khung")
    canh_bao = dv.dat_luoi_gio_ranh(ho_so, ds)
    n = ho_so.lich_ranh.count()
    msg = f"Đã lưu · Rảnh ({n} khung)"
    if canh_bao:
        msg += ". Lưu ý: " + "; ".join(canh_bao) + " – lịch đang dạy không đổi."
    return tra_ve(True, msg, data={"so_khung": n, "canh_bao": canh_bao})


@api(vai_tro=("GIA_SU",), phuong_thuc=("POST",))
def muc_tieu(request):
    ho_so, _ = HoSoGiaSu.objects.get_or_create(user=request.user)
    try:
        n = int(doc_du_lieu(request).get("muc_tieu"))
    except (TypeError, ValueError):
        return tra_ve(False, "Mục tiêu không hợp lệ.")
    ho_so.muc_tieu_buoi_thang = max(1, min(n, 200))
    ho_so.save(update_fields=["muc_tieu_buoi_thang"])
    return tra_ve(True, f"Mục tiêu tháng: {ho_so.muc_tieu_buoi_thang} buổi")


@api(vai_tro=("TUYEN_SINH",), phuong_thuc=("POST",))
def ma_moi(request):
    """SD-04: link mời gia sư đăng ký (dùng lại mã đang mở)."""
    from django.urls import reverse
    ma = dv.tao_ma_moi(request.user)
    url = request.build_absolute_uri(reverse("dang_ky_gia_su", args=[ma.ma]))
    return tra_ve(True, "Đã sao chép đường dẫn đăng ký. Gửi cho gia sư qua Zalo.", data={"url": url, "ma": ma.ma})
