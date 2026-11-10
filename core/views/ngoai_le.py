"""Phần 5b – Xử lý ngoại lệ: Admin xem xét buổi học, sửa số buổi, gán thẳng gia sư; NVTS đổi gia sư."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import BuoiHoc, DoiGiaSu, KhoaHoc, User, YeuCauHocTap
from core.permissions import ADMIN, TUYEN_SINH, vai_tro_required
from core.services import ngoai_le as dv
from core.services.buoi_hoc import quet_han
from core.services.tien_ich import thong_diep_loi as _loi


@vai_tro_required(ADMIN)
def xem_xet(request):
    quet_han()
    return render(request, "core/ngoai_le/xem_xet.html", {
        "ds_buoi": dv.ds_can_xem_xet(),
        "ds_doi": DoiGiaSu.objects.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET)
                  .select_related("khoa_hoc__hoc_vien", "khoa_hoc__yeu_cau__mon_hoc", "gia_su_cu", "tao_boi"),
        "ds_cho_lau": dv.ds_cho_lau(),
    })


@vai_tro_required(ADMIN)
@require_POST
def xu_ly_buoi(request, pk, hanh_dong):
    buoi = get_object_or_404(BuoiHoc.objects.select_related("gia_su", "yeu_cau__mon_hoc"), pk=pk)
    ham = {"hop_le": dv.xac_nhan_hop_le, "huy": dv.huy_sau_xem_xet, "mo_lai": dv.mo_lai}.get(hanh_dong)
    if not ham:
        messages.error(request, "Thao tác không hợp lệ.")
        return redirect("xem_xet")
    try:
        ham(request.user, buoi, request.POST.get("ly_do", ""))
        messages.success(request, {"hop_le": f"Đã công nhận {buoi.ma}.", "huy": f"Đã hủy {buoi.ma} và trả lại buổi cho khóa.",
                                   "mo_lai": f"Đã mở lại {buoi.ma}; gia sư đã được báo qua email."}[hanh_dong])
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("xem_xet")


@vai_tro_required(ADMIN)
@require_POST
def duyet_doi_gia_su(request, pk):
    dn = get_object_or_404(DoiGiaSu, pk=pk)
    dong_y = request.POST.get("dong_y") == "1"
    try:
        dv.duyet_doi_gia_su(request.user, dn, dong_y, request.POST.get("ghi_chu", ""))
        messages.success(request, "Đã duyệt: khóa chuyển sang tìm gia sư mới." if dong_y else "Đã từ chối đề nghị.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("xem_xet")


@vai_tro_required(ADMIN, TUYEN_SINH)
@require_POST
def doi_gia_su(request, pk):
    khoa = get_object_or_404(KhoaHoc.objects.select_related("gia_su", "yeu_cau"), pk=pk)
    from core.models import User
    gs_moi = None
    if request.POST.get("gia_su_moi"):
        gs_moi = User.objects.filter(pk=request.POST["gia_su_moi"], vai_tro=User.VaiTro.GIA_SU, is_active=True).first()
        if not gs_moi:
            messages.error(request, "Gia sư mới không hợp lệ.")
            return redirect(f"{reverse('khoa_hoc_chi_tiet', args=[pk])}?mo=doi-gs")
    try:
        dn = dv.de_nghi_doi_gia_su(request.user, khoa, request.POST.get("ly_do", ""), request.POST.get("ghi_chu", ""),
                                   gia_su_moi=gs_moi, thu_lao_moi=request.POST.get("thu_lao_moi") or None,
                                   da_dong_y=bool(request.POST.get("da_dong_y")))
    except (ValidationError, ValueError) as e:
        messages.error(request, _loi(e) if isinstance(e, ValidationError) else "Thù lao không hợp lệ.")
        return redirect(f"{reverse('khoa_hoc_chi_tiet', args=[pk])}?mo=doi-gs")
    if dn.trang_thai == DoiGiaSu.TrangThai.CHO_DUYET:
        messages.success(request, "Đã gửi đề xuất đổi gia sư, chờ Quản trị viên duyệt. Trong lúc chờ, các buổi vẫn do "
                                  f"{khoa.gia_su.ho_ten} dạy.")
        return redirect("khoa_hoc_chi_tiet", pk=pk)
    if gs_moi:
        dn.refresh_from_db()
        messages.success(request, f"Đã đổi gia sư sang {gs_moi.ho_ten}, chuyển {dn.so_buoi_chuyen} buổi đã xếp. "
                                  "Nhớ báo phụ huynh và đổi nhóm Zalo lớp.")
        return redirect("khoa_hoc_chi_tiet", pk=pk)
    messages.success(request, "Đã đổi gia sư: khóa tạm dừng, chọn gia sư mới và gửi lời mời bên dưới. "
                              "Khi có người nhận, khóa tự học tiếp với số buổi còn lại.")
    return redirect("yeu_cau_chi_tiet", pk=khoa.yeu_cau_id)


@vai_tro_required(ADMIN)
@require_POST
def sua_so_buoi(request, pk):
    khoa = get_object_or_404(KhoaHoc, pk=pk)
    try:
        so = int(request.POST.get("so_buoi", ""))
        dv.sua_so_buoi(request.user, khoa, so, request.POST.get("ly_do", ""))
        messages.success(request, f"Đã cập nhật số buổi đăng ký thành {so}.")
    except ValueError:
        messages.error(request, "Số buổi không hợp lệ.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("khoa_hoc_chi_tiet", pk=pk)


@vai_tro_required(ADMIN)
@require_POST
def gan_thang(request, pk):
    yc = get_object_or_404(YeuCauHocTap.objects.select_related("mon_hoc", "hoc_vien"), pk=pk)
    gs = get_object_or_404(User, pk=request.POST.get("gia_su") or 0, vai_tro=User.VaiTro.GIA_SU)
    try:
        dv.gan_thang(request.user, yc, gs, request.POST.get("ly_do", ""))
        messages.success(request, f"Đã phân công {gs.ho_ten} cho {yc.ma}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)
