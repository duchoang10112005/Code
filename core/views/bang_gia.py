"""Bảng giá: Admin cấu hình đơn giá / % trung tâm theo nhóm môn, gán môn vào nhóm, đặt % giảm của
gói 10/20/30 buổi theo giai đoạn. NV tuyển sinh xem để báo giá cho phụ huynh."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import GoiKhoaHocForm, NhomGiaForm
from core.models import GoiKhoaHoc, KhoaHoc, MonHoc, NhomGia
from core.permissions import ADMIN, TUYEN_SINH, vai_tro_required
from core.services import bang_gia
from core.services.nhat_ky import ghi_nhat_ky
from core.services.tien_ich import dinh_dang_phan_tram, dinh_dang_tien


@vai_tro_required(ADMIN, TUYEN_SINH)
def xem(request, form_goi=None, form_nhom=None):
    ds_nhom = list(NhomGia.objects.all())
    goi = bang_gia.goi_dang_ap_dung()
    bao_gia = bang_gia.bang_bao_gia()
    # Bảng báo giá dạng lưới: nhóm → [(gói, [giá 1h, 1,5h, 2h])]
    luoi = []
    for nhom in ds_nhom:
        hang = []
        for so in sorted(goi):
            o = [b for b in bao_gia if b["nhom_id"] == nhom.pk and b["so_buoi"] == so]
            hang.append((goi[so], o))
        luoi.append((nhom, hang))
    return render(request, "core/bang_gia.html", {
        "ds_nhom": ds_nhom,
        "forms_nhom": {n.pk: (form_nhom if form_nhom and form_nhom.instance.pk == n.pk else NhomGiaForm(instance=n, prefix=f"n{n.pk}")) for n in ds_nhom},
        "ds_mon": MonHoc.objects.select_related("nhom_gia"),
        "goi": goi, "lich_su_goi": GoiKhoaHoc.objects.select_related("tao_boi")[:30],
        "form_goi": form_goi or GoiKhoaHocForm(),
        "luoi": luoi, "khung_gio": KhoaHoc.ThoiLuong.choices,
        "gioi_han_giam": bang_gia.gioi_han_giam(),
    })


@vai_tro_required(ADMIN)
@require_POST
def sua_nhom(request, pk):
    nhom = get_object_or_404(NhomGia, pk=pk)
    cu = f"{dinh_dang_tien(nhom.don_gia_gio)}/giờ, trung tâm {dinh_dang_phan_tram(nhom.ty_le_trung_tam)}"
    form = NhomGiaForm(request.POST, instance=nhom, prefix=f"n{pk}")
    if not form.is_valid():
        return xem(request, form_nhom=form)
    form.save()
    ghi_nhat_ky(request.user, "Sửa nhóm giá", nhom.ten,
                f"{cu} → {dinh_dang_tien(nhom.don_gia_gio)}/giờ, trung tâm {dinh_dang_phan_tram(nhom.ty_le_trung_tam)}")
    messages.success(request, f"Đã cập nhật nhóm giá {nhom.ten}. Khóa học đã tạo trước đó giữ nguyên giá cũ.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def gan_mon(request):
    doi = []
    nhom_theo_id = {str(n.pk): n for n in NhomGia.objects.all()}
    for mon in MonHoc.objects.all():
        nhom = nhom_theo_id.get(request.POST.get(f"mon_{mon.pk}", ""))
        if nhom and mon.nhom_gia_id != nhom.pk:
            mon.nhom_gia = nhom
            mon.save(update_fields=["nhom_gia"])
            doi.append(f"{mon} → {nhom}")
    if doi:
        ghi_nhat_ky(request.user, "Gán môn vào nhóm giá", "", "; ".join(doi))
        messages.success(request, "Đã cập nhật nhóm giá cho " + ", ".join(doi) + ".")
    else:
        messages.info(request, "Không có thay đổi.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def sua_quyen_loi(request, pk):
    goi = get_object_or_404(GoiKhoaHoc, pk=pk)
    goi.quyen_loi = request.POST.get("quyen_loi", "").strip()[:2000]
    goi.save(update_fields=["quyen_loi"])
    ghi_nhat_ky(request.user, "Sửa quyền lợi gói", goi.get_so_buoi_display(), "; ".join(goi.ds_quyen_loi))
    messages.success(request, f"Đã cập nhật quyền lợi {goi.get_so_buoi_display()}. Khóa đã tạo giữ quyền lợi lúc đăng ký.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def them_goi(request):
    form = GoiKhoaHocForm(request.POST)
    if not form.is_valid():
        return xem(request, form_goi=form)
    goi = form.save(commit=False)
    goi.tao_boi = request.user
    if not goi.quyen_loi.strip():
        dang_ap_dung = bang_gia.goi_dang_ap_dung().get(goi.so_buoi)
        goi.quyen_loi = dang_ap_dung.quyen_loi if dang_ap_dung else ""
    goi.save()
    den = goi.hieu_luc_den.strftime("%d/%m/%Y") if goi.hieu_luc_den else "không thời hạn"
    ghi_nhat_ky(request.user, "Đặt giảm giá gói", goi.get_so_buoi_display(),
                f"Giảm {dinh_dang_phan_tram(goi.ty_le_giam)} từ {goi.hieu_luc_tu:%d/%m/%Y} đến {den}")
    messages.success(request, f"Đã đặt {goi} từ {goi.hieu_luc_tu:%d/%m/%Y}.")
    return redirect("bang_gia")
