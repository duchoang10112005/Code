"""Phần 5 – Buổi học của gia sư (DFD 5.0): tạo buổi + Zoom, hủy / dời lịch, xác nhận hoàn tất.

Quyền: chỉ gia sư, và chỉ buổi học của chính mình (buổi của người khác → 404).
"""

from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import DoiLichForm, HuyBuoiForm, LocBuoiForm, TaoBuoiForm, XacNhanBuoiForm
from core.models import BuoiHoc, KhoaHoc, YeuCauHocTap
from core.permissions import GIA_SU, vai_tro_required
from core.services import buoi_hoc as dv
from core.services.tien_ich import thong_diep_loi as _loi

TT = BuoiHoc.TrangThai


def _buoi_cua_toi(request, pk):
    return get_object_or_404(
        BuoiHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc", "gia_su"),
        pk=pk, gia_su=request.user)


@vai_tro_required(GIA_SU)
def danh_sach(request):
    dv.quet_han()
    u = request.user
    form = LocBuoiForm(request.GET or None)
    thang = timezone.localdate().replace(day=1)
    trang_thai = ""
    if form.is_valid():
        thang = form.cleaned_data["thang"] or thang
        trang_thai = form.cleaned_data["trang_thai"]
    elif not request.GET:
        form = LocBuoiForm(initial={"thang": thang})
    den = date(thang.year + (thang.month == 12), thang.month % 12 + 1, 1)
    goc = BuoiHoc.objects.filter(gia_su=u).select_related("hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc")
    trong_thang = goc.filter(bat_dau__date__gte=thang, bat_dau__date__lt=den).order_by("bat_dau")
    if trang_thai:
        trong_thang = trong_thang.filter(trang_thai=trang_thai)
    now = timezone.now()
    cho_xac_nhan = [b for b in goc.filter(trang_thai=TT.DA_LEN_LICH, bat_dau__lte=now).order_by("bat_dau")
                    if b.cho_xac_nhan]
    return render(request, "core/buoi_hoc/danh_sach.html", {
        "form": form, "thang": thang, "ds": trong_thang,
        "cho_xac_nhan": cho_xac_nhan,
        "sap_toi": goc.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=now).order_by("bat_dau")[:10],
        "co_lop": bool(dv.khoa_co_the_xep(u) or dv.yeu_cau_co_the_hoc_thu(u)),
    })


@vai_tro_required(GIA_SU)
def tao(request):
    u = request.user
    ds_khoa, ds_thu = dv.khoa_co_the_xep(u), dv.yeu_cau_co_the_hoc_thu(u)
    ban_dau = {}
    if request.GET.get("khoa"):
        ban_dau["lop"] = f"k-{request.GET['khoa']}"
    elif request.GET.get("yc"):
        ban_dau["lop"] = f"t-{request.GET['yc']}"
    form = TaoBuoiForm(request.POST or None, initial=ban_dau, ds_khoa=ds_khoa, ds_thu=ds_thu)
    if request.method == "POST" and form.is_valid():
        loai, _, pk = form.cleaned_data["lop"].partition("-")
        try:
            if loai == "k":
                khoa = get_object_or_404(KhoaHoc, pk=pk, gia_su=u)
                buoi = dv.tao_buoi_chinh_thuc(u, khoa, form.cleaned_data["bat_dau"])
            else:
                yc = get_object_or_404(YeuCauHocTap, pk=pk, gia_su=u)
                buoi = dv.tao_buoi_hoc_thu(u, yc, form.cleaned_data["bat_dau"], form.cleaned_data["thoi_luong"] or 60)
        except ValidationError as e:
            form.add_error("bat_dau" if "giờ" in _loi(e).lower() else None, _loi(e))
        else:
            if buoi.trang_thai == TT.DA_LEN_LICH:
                messages.success(request, "Đã tạo buổi học và phòng Zoom. Sao chép link gửi học viên qua Zalo.")
            else:
                messages.error(request, "Đã lưu buổi học nhưng chưa tạo được phòng Zoom. Bấm Thử lại.")
            return redirect("buoi_chi_tiet", pk=buoi.pk)
    return render(request, "core/buoi_hoc/tao.html", {"form": form, "khong_co_lop": not (ds_khoa or ds_thu)})


@vai_tro_required(GIA_SU)
def chi_tiet(request, pk):
    dv.quet_han()
    buoi = _buoi_cua_toi(request, pk)
    return render(request, "core/buoi_hoc/chi_tiet.html", {
        "buoi": buoi, "TT": TT,
        "form_xac_nhan": XacNhanBuoiForm() if buoi.cho_xac_nhan else None,
        "form_huy": HuyBuoiForm(), "form_doi_lich": DoiLichForm(),
        "co_the_doi": buoi.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO and buoi.bat_dau > timezone.now(),
        "noi_dung_phu_huynh": dv.noi_dung_gui_phu_huynh(buoi) if buoi.xac_nhan_luc else "",
    })


@vai_tro_required(GIA_SU)
def mo_phong(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    try:
        return redirect(dv.lay_link_mo_phong(request.user, buoi))
    except ValidationError as e:
        messages.error(request, _loi(e))
        return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def thu_lai_zoom(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    try:
        if dv.thu_lai_zoom(request.user, buoi):
            messages.success(request, "Đã tạo phòng Zoom.")
        else:
            messages.error(request, "Zoom vẫn chưa phản hồi. Thử lại sau ít phút.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def huy(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = HuyBuoiForm(request.POST)
    if form.is_valid():
        try:
            dv.huy_buoi(request.user, buoi, form.cleaned_data["ly_do_huy"], form.cleaned_data["ghi_chu"])
            messages.success(request, "Đã hủy buổi học và xóa phòng Zoom. Nhớ báo phụ huynh qua Zalo.")
        except ValidationError as e:
            messages.error(request, _loi(e))
    else:
        messages.error(request, "Vui lòng chọn lý do hủy.")
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def doi_lich(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = DoiLichForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Giờ mới không hợp lệ.")
        return redirect("buoi_chi_tiet", pk=pk)
    try:
        moi = dv.doi_lich(request.user, buoi, form.cleaned_data["bat_dau"])
    except ValidationError as e:
        messages.error(request, _loi(e))
        return redirect("buoi_chi_tiet", pk=pk)
    messages.success(request, "Đã dời lịch: buổi cũ đã hủy, buổi mới có phòng Zoom mới. Gửi lại link cho học viên.")
    return redirect("buoi_chi_tiet", pk=moi.pk)


@vai_tro_required(GIA_SU)
@require_POST
def xac_nhan(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = XacNhanBuoiForm(request.POST)
    if form.is_valid():
        try:
            buoi = dv.xac_nhan_hoan_tat(request.user, buoi, form.cleaned_data)
        except ValidationError as e:
            messages.error(request, _loi(e))
            return redirect("buoi_chi_tiet", pk=pk)
        if buoi.zalo_trang_thai == BuoiHoc.GuiZalo.DA_GUI:
            messages.success(request, "Đã xác nhận hoàn tất. Đánh giá đã được gửi cho phụ huynh qua Zalo.")
        else:
            messages.warning(request, "Đã xác nhận hoàn tất, nhưng chưa gửi được Zalo. "
                                      "Hãy sao chép nội dung bên dưới gửi phụ huynh.")
        return redirect("buoi_chi_tiet", pk=pk)
    # Form lỗi: hiển thị lại trang với lỗi tại từng ô.
    return render(request, "core/buoi_hoc/chi_tiet.html", {
        "buoi": buoi, "TT": TT, "form_xac_nhan": form, "form_huy": HuyBuoiForm(), "form_doi_lich": DoiLichForm(),
        "co_the_doi": False, "noi_dung_phu_huynh": "",
    }, status=400)
