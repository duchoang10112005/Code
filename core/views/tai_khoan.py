"""Quản lý tài khoản – chỉ Admin (PB-01, PB-23, PB-24)."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.forms import SuaTaiKhoanForm, TaoTaiKhoanForm
from core.models import HoSoGiaSu, NhatKy, User
from core.permissions import ADMIN, vai_tro_required
from core.services.nhat_ky import ghi_nhat_ky
from core.services.yeu_cau import huy_loi_moi_cua_gia_su


def _dam_bao_ho_so_gia_su(user):
    if user.la_gia_su:
        HoSoGiaSu.objects.get_or_create(user=user)


VAI_TRO_TAB = [("", "Tất cả"), ("ADMIN", "Quản trị viên"), ("TUYEN_SINH", "Tuyển sinh"), ("GIA_SU", "Gia sư")]


def _trang_danh_sach(request, form=None):
    from django.utils import timezone
    goc = User.objects.order_by("vai_tro", "ho_ten")
    vai_tro = request.GET.get("vai_tro", "")
    tim = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "")
    qs = goc
    if tim:
        from core.services.tien_ich import chuan_hoa_sdt
        dk = Q(username__icontains=tim) | Q(ho_ten__icontains=tim) | Q(email__icontains=tim)
        sdt = chuan_hoa_sdt(tim)
        if sdt:
            dk |= Q(so_dien_thoai__icontains=sdt) | Q(so_dien_thoai__icontains=tim)
        qs = qs.filter(dk)
    if trang_thai == "khoa":
        qs = qs.filter(is_active=False)
    elif trang_thai == "hoat_dong":
        qs = qs.filter(is_active=True, last_login__isnull=False)
    elif trang_thai == "chua_dang_nhap":
        qs = qs.filter(is_active=True, last_login__isnull=True)
    dem = {k: (qs.filter(vai_tro=k) if k else qs).count() for k, _ in VAI_TRO_TAB}
    if vai_tro:
        qs = qs.filter(vai_tro=vai_tro)
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    mk = request.session.pop("mk_tam", None)
    return render(request, "core/tai_khoan/danh_sach.html", {
        "trang": trang, "VaiTro": User.VaiTro, "ds_tab": [(k, n, dem[k]) for k, n in VAI_TRO_TAB],
        "loc": {"vai_tro": vai_tro, "q": tim, "trang_thai": trang_thai},
        "kpi": {"tong": goc.count(), "hoat_dong": goc.filter(is_active=True, last_login__isnull=False).count(),
                "chua": goc.filter(is_active=True, last_login__isnull=True).count(),
                "khoa": goc.filter(is_active=False).count()},
        "form": form or TaoTaiKhoanForm(), "mo_tao": form is not None, "mk_tam": mk, "now": timezone.now(),
    }, status=200)


@vai_tro_required(ADMIN)
def danh_sach(request):
    return _trang_danh_sach(request)


@vai_tro_required(ADMIN)
def tao(request):
    from core.services import tai_khoan as dv_tk
    if request.method != "POST":
        return redirect(reverse("tai_khoan_danh_sach") + "?tao=1")
    form = TaoTaiKhoanForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            user = form.save()
            dv_tk.dam_bao_ho_so(user)
            if user.la_gia_su:
                dv_tk.tao_gia_su(request.user, user, form.cleaned_data["tuyen_sinh_phu_trach"],
                                 list(form.cleaned_data["mon_day"]))
            ghi_nhat_ky(request.user, "Tạo tài khoản", user.username, f"Vai trò: {user.get_vai_tro_display()}")
        if form.mat_khau_tam:
            if form.cleaned_data.get("gui_email") and user.email:
                dv_tk.gui_mat_khau(user, form.mat_khau_tam)
            request.session["mk_tam"] = {"ten": user.ho_ten, "username": user.username, "mk": form.mat_khau_tam,
                                         "da_gui": bool(form.cleaned_data.get("gui_email") and user.email)}
        messages.success(request, f"Đã tạo tài khoản {user.username}.")
        return redirect("tai_khoan_danh_sach")
    return _trang_danh_sach(request, form)


@vai_tro_required(ADMIN)
def sua(request, pk):
    user = get_object_or_404(User, pk=pk)
    vai_tro_cu = user.vai_tro
    form = SuaTaiKhoanForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if user == request.user and form.cleaned_data["vai_tro"] != User.VaiTro.ADMIN:
            form.add_error("vai_tro", "Không thể tự bỏ quyền Admin của chính mình.")
        else:
            with transaction.atomic():
                user = form.save(commit=False)
                mk = form.cleaned_data.get("mat_khau_moi")
                if mk:
                    user.set_password(mk)
                user.save()
                _dam_bao_ho_so_gia_su(user)
                chi_tiet = []
                if vai_tro_cu != user.vai_tro:
                    chi_tiet.append(f"Đổi vai trò: {User.VaiTro(vai_tro_cu).label} → {user.get_vai_tro_display()}")
                    if vai_tro_cu == User.VaiTro.GIA_SU:
                        huy_loi_moi_cua_gia_su(user, "Tài khoản không còn là gia sư")
                if mk:
                    chi_tiet.append("Đặt lại mật khẩu")
                ghi_nhat_ky(request.user, "Sửa tài khoản", user.username, "; ".join(chi_tiet) or "Cập nhật thông tin")
            messages.success(request, f"Đã cập nhật tài khoản {user.username}.")
            return redirect("tai_khoan_danh_sach")
    return render(request, "core/tai_khoan/form.html", {
        "form": form, "tieu_de": f"Sửa tài khoản: {user.username}", "doi_tuong": user,
    })


@vai_tro_required(ADMIN)
@require_POST
def doi_trang_thai(request, pk):
    """Khóa (kèm lý do) / mở khóa tài khoản."""
    from django.core.exceptions import ValidationError
    from core.services import tai_khoan as dv_tk
    user = get_object_or_404(User, pk=pk)
    try:
        if user.is_active:
            dv_tk.khoa(request.user, user, request.POST.get("ly_do", ""))
            messages.success(request, f"Đã khóa tài khoản {user.username}.")
        else:
            dv_tk.mo_khoa(request.user, user)
            messages.success(request, f"Đã mở khóa tài khoản {user.username}.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    # Chỉ quay lại địa chỉ nội bộ (chặn chuyển hướng ra trang ngoài qua tham số next).
    tiep = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(tiep, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        tiep = "tai_khoan_danh_sach"
    return redirect(tiep)


@vai_tro_required(ADMIN)
@require_POST
def dat_lai_mat_khau(request, pk):
    from core.services import tai_khoan as dv_tk
    user = get_object_or_404(User, pk=pk)
    mk = dv_tk.dat_lai_mat_khau(request.user, user)
    request.session["mk_tam"] = {"ten": user.ho_ten, "username": user.username, "mk": mk, "da_gui": bool(user.email),
                                 "dat_lai": True}
    return redirect("tai_khoan_danh_sach")


def _loc_nhat_ky(request):
    from datetime import timedelta
    from django.utils import timezone
    qs = NhatKy.objects.select_related("nguoi_thuc_hien")
    khoang = request.GET.get("khoang", "7")
    if khoang in ("1", "7", "30"):
        tu = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=int(khoang) - 1)
        qs = qs.filter(thoi_diem__gte=tu)
    nguoi = request.GET.get("nguoi", "")
    if nguoi == "he_thong":
        qs = qs.filter(nguoi_thuc_hien__isnull=True)
    elif nguoi.isdigit():
        qs = qs.filter(nguoi_thuc_hien_id=int(nguoi))
    loai = request.GET.get("loai", "")
    if loai:
        qs = qs.filter(loai_doi_tuong=loai)
    tim = request.GET.get("q", "").strip()
    if tim:
        import re
        m = re.match(r"^(bh|kh|yc)[-\s]*0*(\d+)$", tim.lower())
        if m:
            ma = f"{m.group(1).upper()}-{int(m.group(2)):0{5 if m.group(1) == 'bh' else 4}d}"
            qs = qs.filter(Q(ma_doi_tuong=ma) | Q(doi_tuong__icontains=ma) | Q(chi_tiet__icontains=ma))
        else:
            qs = qs.filter(Q(hanh_dong__icontains=tim) | Q(doi_tuong__icontains=tim) | Q(chi_tiet__icontains=tim)
                           | Q(nguoi_thuc_hien__ho_ten__icontains=tim))
    return qs, {"khoang": khoang, "nguoi": nguoi, "loai": loai, "q": tim}


@vai_tro_required(ADMIN)
def nhat_ky(request):
    """QTV › Nhật ký thao tác (SD-35): chỉ xem; lọc khoảng ngày, người, loại đối tượng, mã; gom theo ngày."""
    from itertools import groupby
    from django.urls import NoReverseMatch
    from django.utils import timezone
    qs, loc = _loc_nhat_ky(request)
    trang = Paginator(qs, 100).get_page(request.GET.get("page"))
    hom_nay = timezone.localdate()
    for g in trang:
        g.url_ma = ""
        try:
            if g.ma_doi_tuong.startswith("YC-"):
                g.url_ma = reverse("yeu_cau_chi_tiet", args=[int(g.ma_doi_tuong[3:])])
            elif g.ma_doi_tuong.startswith("KH-"):
                g.url_ma = reverse("khoa_hoc_chi_tiet", args=[int(g.ma_doi_tuong[3:])])
            elif g.ma_doi_tuong.startswith("BH-"):
                g.url_ma = reverse("xem_xet") + f"?q={g.ma_doi_tuong}"
        except (ValueError, NoReverseMatch):
            pass
    nhom = []
    for ngay, ds in groupby(trang, key=lambda g: timezone.localtime(g.thoi_diem).date()):
        ds = list(ds)
        nhan = ("Hôm nay · " if ngay == hom_nay else "Hôm qua · " if (hom_nay - ngay).days == 1 else "")
        nhom.append({"ngay": ngay, "nhan": nhan, "ds": ds})
    qs_loc = request.GET.copy()
    qs_loc.pop("page", None)
    return render(request, "core/nhat_ky.html", {
        "trang": trang, "nhom": nhom, "loc": loc, "q": loc["q"], "loc_qs": qs_loc.urlencode(),
        "ds_nguoi": User.objects.exclude(vai_tro=User.VaiTro.GIA_SU).order_by("ho_ten"),
        "ds_loai": NhatKy.LoaiDoiTuong.choices,
    })


@vai_tro_required(ADMIN)
def nhat_ky_csv(request):
    import csv
    from django.http import HttpResponse
    from django.utils import timezone
    qs, _ = _loc_nhat_ky(request)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="nhat-ky.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp)
    w.writerow(["Thời điểm", "Người thực hiện", "Hành động", "Mã", "Đối tượng", "Chi tiết", "Trước", "Sau"])
    for g in qs[:5000]:
        w.writerow([f"{timezone.localtime(g.thoi_diem):%d/%m/%Y %H:%M}",
                    g.nguoi_thuc_hien.ho_ten if g.nguoi_thuc_hien else "Hệ thống", g.hanh_dong, g.ma_doi_tuong,
                    g.doi_tuong, g.chi_tiet, g.gia_tri_cu or "", g.gia_tri_moi or ""])
    return resp
