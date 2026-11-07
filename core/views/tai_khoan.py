"""Quản lý tài khoản – chỉ Admin (PB-01, PB-23, PB-24)."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import SuaTaiKhoanForm, TaoTaiKhoanForm
from core.models import HoSoGiaSu, NhatKy, User
from core.permissions import ADMIN, vai_tro_required
from core.services.nhat_ky import ghi_nhat_ky


def _dam_bao_ho_so_gia_su(user):
    if user.la_gia_su:
        HoSoGiaSu.objects.get_or_create(user=user)


@vai_tro_required(ADMIN)
def danh_sach(request):
    qs = User.objects.order_by("vai_tro", "ho_ten")
    vai_tro = request.GET.get("vai_tro", "")
    tim = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "")
    if vai_tro:
        qs = qs.filter(vai_tro=vai_tro)
    if tim:
        qs = qs.filter(Q(username__icontains=tim) | Q(ho_ten__icontains=tim) | Q(email__icontains=tim))
    if trang_thai == "khoa":
        qs = qs.filter(is_active=False)
    elif trang_thai == "hoat_dong":
        qs = qs.filter(is_active=True)
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "core/tai_khoan/danh_sach.html", {
        "trang": trang, "VaiTro": User.VaiTro,
        "loc": {"vai_tro": vai_tro, "q": tim, "trang_thai": trang_thai},
    })


@vai_tro_required(ADMIN)
def tao(request):
    form = TaoTaiKhoanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            _dam_bao_ho_so_gia_su(user)
            ghi_nhat_ky(request.user, "Tạo tài khoản", user.username, f"Vai trò: {user.get_vai_tro_display()}")
        messages.success(request, f"Đã tạo tài khoản {user.username}.")
        return redirect("tai_khoan_danh_sach")
    return render(request, "core/tai_khoan/form.html", {"form": form, "tieu_de": "Tạo tài khoản"})


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
    """Khóa / mở khóa tài khoản."""
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Không thể tự khóa tài khoản của chính mình.")
        return redirect("tai_khoan_danh_sach")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    hanh_dong = "Mở khóa tài khoản" if user.is_active else "Khóa tài khoản"
    ghi_nhat_ky(request.user, hanh_dong, user.username)
    messages.success(request, f"{hanh_dong}: {user.username}.")
    return redirect(request.POST.get("next") or "tai_khoan_danh_sach")


@vai_tro_required(ADMIN)
def nhat_ky(request):
    qs = NhatKy.objects.select_related("nguoi_thuc_hien")
    tim = request.GET.get("q", "").strip()
    if tim:
        qs = qs.filter(Q(hanh_dong__icontains=tim) | Q(doi_tuong__icontains=tim) | Q(chi_tiet__icontains=tim))
    trang = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "core/nhat_ky.html", {"trang": trang, "q": tim})
