"""Tuyển sinh › Hậu kiểm buổi học (SD-21). QTV chỉ xem."""

from django.shortcuts import render

from core.models import HauKiemBuoi
from core.permissions import ADMIN, TUYEN_SINH, vai_tro_required
from core.services import hau_kiem as dv


@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    ds = sorted(dv.pham_vi(request.user), key=lambda h: h.buoi_hoc.bat_dau, reverse=True)
    for h in ds:
        h.so_cb = dv.so_canh_bao(h)
    tab = request.GET.get("tab", "can_kiem")
    tab = tab if tab in dict(dv.TAB) else "can_kiem"
    q = request.GET.get("q", "").strip().lower()
    loc = [h for h in ds if dv.thuoc_tab(h, tab, h.so_cb)]
    if q:
        loc = [h for h in loc if q in h.buoi_hoc.ma.lower() or q in h.buoi_hoc.hoc_vien.ho_ten.lower()
               or q in h.buoi_hoc.gia_su.ho_ten.lower() or q in str(h.buoi_hoc.yeu_cau.mon_hoc).lower()]
    chon_pk = request.GET.get("chon", "")
    chon = next((h for h in loc if str(h.buoi_hoc_id) == chon_pk), None) or next(
        (h for h in ds if str(h.buoi_hoc_id) == chon_pk), None) or (loc[0] if loc else None)
    tc = dv.tieu_chi(chon) if chon else []
    co_quyen = bool(chon and request.user.la_tuyen_sinh and (not chon.nguoi_phu_trach_id
                                                              or chon.nguoi_phu_trach_id == request.user.pk))
    return render(request, "core/hau_kiem/danh_sach.html", {
        "ds": loc, "tab": tab, "q": request.GET.get("q", ""), "chon": chon, "tieu_chi": tc,
        "so_dat": sum(1 for t in tc if t["dat"]), "co_quyen": co_quyen,
        "ds_tab": [(k, n, sum(1 for h in ds if dv.thuoc_tab(h, k, h.so_cb))) for k, n in dv.TAB],
        "tk": dv.thong_ke(request.user, ds), "the_gs": dv.the_gia_su(request.user, ds),
        "so_sach": sum(1 for h in loc if h.ket_luan == HauKiemBuoi.KetLuan.CHUA_KIEM_TRA and h.so_cb == 0),
        "so_chua": sum(1 for h in loc if h.ket_luan == HauKiemBuoi.KetLuan.CHUA_KIEM_TRA),
        "ly_do": HauKiemBuoi.LyDo.choices,
    })
