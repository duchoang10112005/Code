"""API hậu kiểm buổi học (SD-21, SD-22) – chỉ Tuyển sinh phụ trách."""

from django.shortcuts import get_object_or_404

from core.api import api, doc_du_lieu, tra_ve
from core.models import HauKiemBuoi
from core.services import hau_kiem as dv


def _lay(request, pk):
    return get_object_or_404(dv.pham_vi(request.user), buoi_hoc_id=pk)


@api(vai_tro=("TUYEN_SINH",), phuong_thuc=("POST",))
def ket_luan(request, pk):
    hk = _lay(request, pk)
    d = doc_du_lieu(request)
    hk = dv.ket_luan(request.user, hk, d.get("ket_luan", ""), d.get("ly_do", ""), d.get("ghi_chu", ""))
    msg = (f"{hk.buoi_hoc.ma}: Hợp lệ" if hk.ket_luan == HauKiemBuoi.KetLuan.HOP_LE
           else f"{hk.buoi_hoc.ma}: Có vấn đề · thù lao chuyển Tạm giữ, đã email gia sư")
    return tra_ve(True, msg, data={"ket_luan": hk.ket_luan})


@api(vai_tro=("TUYEN_SINH",), phuong_thuc=("POST",))
def hang_loat(request):
    d = doc_du_lieu(request)
    ids = d.get("ids") if isinstance(d.get("ids"), list) else request.POST.getlist("ids")
    chi_sach = str(d.get("chi_buoi_sach", "")).lower() in ("1", "true", "on")
    da, bo = dv.duyet_hang_loat(request.user, ids or [], chi_sach)
    msg = f"Đã duyệt {da} buổi" + (f" · bỏ qua {bo} (có cảnh báo / đã kiểm tra)" if bo else "")
    return tra_ve(True, msg, data={"da_duyet": da, "bo_qua": bo})


@api(vai_tro=("TUYEN_SINH",), phuong_thuc=("POST",))
def xu_ly(request, pk):
    hk = _lay(request, pk)
    d = doc_du_lieu(request)
    tinh = str(d.get("tinh", "")).lower() in ("1", "true", "on")
    hk = dv.xu_ly(request.user, hk, tinh, d.get("ly_do", ""))
    return tra_ve(True, f"{hk.buoi_hoc.ma}: " + ("vẫn tính thù lao" if tinh else "không tính, đã trả buổi cho khóa"),
                  data={"ket_luan": hk.ket_luan})
