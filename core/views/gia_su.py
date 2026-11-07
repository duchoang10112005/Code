"""Phần 2 – Hồ sơ gia sư (tiến trình 2.0 trên DFD; PB-04, PB-19, PB-24)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import DangKyMonForm, HoSoGiaSuForm, LichRanhForm, LocGiaSuForm
from core.models import HoSoGiaSu, LichRanh, MonGiaSu, User
from core.permissions import ADMIN, GIA_SU, TUYEN_SINH, vai_tro_required
from core.services import gia_su as dv
from core.services.tien_ich import thong_diep_loi as _loi


# =============================================================================
# Gia sư – Hồ sơ của tôi
# =============================================================================
def _ho_so_cua(user):
    ho_so, _ = HoSoGiaSu.objects.get_or_create(user=user)
    return ho_so


def _trang_ho_so(request, ho_so, form_ho_so=None, form_mon=None, form_lich=None):
    return render(request, "core/gia_su/ho_so_cua_toi.html", {
        "ho_so": ho_so,
        "ds_mon": ho_so.mon_day.select_related("mon_hoc").order_by("trang_thai", "mon_hoc__ten"),
        "ds_lich": ho_so.lich_ranh.all(),
        "form_ho_so": form_ho_so or HoSoGiaSuForm(instance=ho_so),
        "form_mon": form_mon or DangKyMonForm(ho_so=ho_so),
        "form_lich": form_lich or LichRanhForm(),
    })


@vai_tro_required(GIA_SU)
def ho_so_cua_toi(request):
    return _trang_ho_so(request, _ho_so_cua(request.user))


@vai_tro_required(GIA_SU)
@require_POST
def cap_nhat_ho_so(request):
    ho_so = _ho_so_cua(request.user)
    form = HoSoGiaSuForm(request.POST, instance=ho_so)
    if form.is_valid():
        form.save()
        messages.success(request, "Đã lưu thông tin hồ sơ.")
        return redirect("ho_so_cua_toi")
    return _trang_ho_so(request, ho_so, form_ho_so=form)


@vai_tro_required(GIA_SU)
@require_POST
def dang_ky_mon(request):
    ho_so = _ho_so_cua(request.user)
    form = DangKyMonForm(request.POST, ho_so=ho_so)
    if form.is_valid():
        try:
            mg = dv.dang_ky_mon(ho_so, form.cleaned_data["mon_hoc"], form.cleaned_data["cap_do"])
            messages.success(request, f"Đã gửi đăng ký môn {mg.mon_hoc}. Môn sẽ dùng được sau khi Admin duyệt.")
            return redirect("ho_so_cua_toi")
        except ValidationError as e:
            form.add_error(None, _loi(e))
    return _trang_ho_so(request, ho_so, form_mon=form)


@vai_tro_required(GIA_SU)
@require_POST
def rut_mon(request, pk):
    ho_so = _ho_so_cua(request.user)
    mg = get_object_or_404(MonGiaSu, pk=pk, ho_so=ho_so)
    try:
        dv.rut_mon(ho_so, mg)
        messages.success(request, f"Đã rút đăng ký môn {mg.mon_hoc}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("ho_so_cua_toi")


@vai_tro_required(GIA_SU)
@require_POST
def them_lich(request):
    ho_so = _ho_so_cua(request.user)
    form = LichRanhForm(request.POST)
    if form.is_valid():
        try:
            dv.them_lich_ranh(ho_so, **form.cleaned_data)
            messages.success(request, "Đã thêm khung giờ rảnh.")
            return redirect("ho_so_cua_toi")
        except ValidationError as e:
            form.add_error(None, _loi(e))
    return _trang_ho_so(request, ho_so, form_lich=form)


@vai_tro_required(GIA_SU)
@require_POST
def xoa_lich(request, pk):
    lich = get_object_or_404(LichRanh, pk=pk, ho_so__user=request.user)
    lich.delete()
    messages.success(request, f"Đã xóa khung giờ {lich}.")
    return redirect("ho_so_cua_toi")


# =============================================================================
# Admin / NV tuyển sinh – Danh sách và chi tiết gia sư
# =============================================================================
@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    form = LocGiaSuForm(request.GET or None)
    # Đếm môn chờ duyệt bằng subquery riêng, và lọc theo môn / ngày rảnh bằng pk__in, để các
    # bộ lọc trên quan hệ nhiều-nhiều không làm nhân bản dòng và đếm sai.
    dem_cho_duyet = (MonGiaSu.objects.filter(ho_so=OuterRef("pk"), trang_thai=MonGiaSu.TrangThai.CHO_DUYET)
                     .order_by().values("ho_so").annotate(c=Count("pk")).values("c"))
    # Chỉ tài khoản hiện đang là Gia sư (hồ sơ của người đã đổi vai trò được giữ lại nhưng ẩn đi).
    qs = (HoSoGiaSu.objects.select_related("user").filter(user__vai_tro=User.VaiTro.GIA_SU)
          .annotate(so_cho_duyet=Coalesce(Subquery(dem_cho_duyet), 0))
          .prefetch_related("mon_day__mon_hoc")
          .order_by("-so_cho_duyet", "user__ho_ten"))
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            qs = qs.filter(Q(user__ho_ten__icontains=d["q"]) | Q(user__email__icontains=d["q"]))
        if d["mon"]:
            qs = qs.filter(pk__in=MonGiaSu.objects.filter(
                mon_hoc=d["mon"], trang_thai=MonGiaSu.TrangThai.DA_DUYET).values("ho_so"))
        if d["trang_thai"]:
            qs = qs.filter(trang_thai=d["trang_thai"])
        if d["thu"] != "" and d["thu"] is not None:
            qs = qs.filter(pk__in=LichRanh.objects.filter(thu=int(d["thu"])).values("ho_so"))
        if d["cho_duyet"]:
            qs = qs.filter(so_cho_duyet__gt=0)
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "core/gia_su/danh_sach.html", {"trang": trang, "form": form})


@vai_tro_required(ADMIN, TUYEN_SINH)
def chi_tiet(request, pk):
    ho_so = get_object_or_404(HoSoGiaSu.objects.select_related("user"), pk=pk, user__vai_tro=User.VaiTro.GIA_SU)
    return render(request, "core/gia_su/chi_tiet.html", {
        "ho_so": ho_so,
        "ds_mon": ho_so.mon_day.select_related("mon_hoc", "duyet_boi").order_by("trang_thai", "mon_hoc__ten"),
        "ds_lich": ho_so.lich_ranh.all(),
        "TrangThai": HoSoGiaSu.TrangThai,
    })


@vai_tro_required(ADMIN)
@require_POST
def xu_ly_mon(request, pk):
    mg = get_object_or_404(MonGiaSu.objects.select_related("ho_so__user", "mon_hoc"), pk=pk)
    hanh_dong = request.POST.get("hanh_dong")
    ly_do = request.POST.get("ly_do", "").strip()
    try:
        if hanh_dong == "duyet":
            dv.duyet_mon(request.user, mg, ly_do)
            messages.success(request, f"Đã duyệt môn {mg.mon_hoc} cho {mg.ho_so.user.ho_ten}. Đã gửi email báo gia sư.")
        elif hanh_dong in ("tu_choi", "thu_hoi"):
            dv.tu_choi_mon(request.user, mg, ly_do)
            chu = "thu hồi" if hanh_dong == "thu_hoi" else "từ chối"
            messages.success(request, f"Đã {chu} môn {mg.mon_hoc}. Đã gửi email kèm lý do cho gia sư.")
        else:
            messages.error(request, "Thao tác không hợp lệ.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("gia_su_chi_tiet", pk=mg.ho_so_id)


@vai_tro_required(ADMIN)
@require_POST
def doi_trang_thai(request, pk):
    ho_so = get_object_or_404(HoSoGiaSu, pk=pk)
    moi = request.POST.get("trang_thai")
    if moi not in HoSoGiaSu.TrangThai.values:
        messages.error(request, "Trạng thái không hợp lệ.")
    else:
        try:
            dv.doi_trang_thai_ho_so(request.user, ho_so, moi)
            messages.success(request, f"Hồ sơ {ho_so.user.ho_ten}: {ho_so.get_trang_thai_display()}.")
        except ValidationError as e:
            messages.error(request, _loi(e))
    return redirect("gia_su_chi_tiet", pk=pk)
