"""Bảng giá – chỉ Admin.

Giá gắn với CẤP ĐỘ HỌC trong từng LOẠI MÔN (VD: Phổ thông – Cơ bản / Nâng cao; IELTS – Nền tảng / Chuyên sâu).
Admin: sửa / thêm cấp độ (đơn giá giờ, % trung tâm), thêm loại môn, gán môn vào loại môn,
quyền lợi gói và khuyến mãi theo giai đoạn. NV tuyển sinh không cần trang này: form tạo khóa tự báo giá.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import CapDoForm, GoiKhoaHocForm, LoaiMonForm
from core.models import CapDo, GoiKhoaHoc, KhoaHoc, LoaiMon, MonHoc
from core.permissions import ADMIN, vai_tro_required
from core.services import bang_gia
from core.services.nhat_ky import ghi_nhat_ky
from core.services.tien_ich import dinh_dang_phan_tram, dinh_dang_tien


def _mo_ta_gia(cd):
    return f"{dinh_dang_tien(cd.don_gia_gio)}/giờ, trung tâm {dinh_dang_phan_tram(cd.ty_le_trung_tam)}"


@vai_tro_required(ADMIN)
def xem(request, form_goi=None, form_cap_do=None, form_them_cap_do=None, form_loai=None):
    goi = bang_gia.goi_dang_ap_dung()
    khung = KhoaHoc.ThoiLuong.choices
    ds_loai = []
    for loai in LoaiMon.objects.prefetch_related("cap_do", "mon_hoc"):
        hang = []
        for cd in loai.cap_do.all():
            o = []
            for phut, _ in khung:
                goc, thu_lao = bang_gia.gia_mot_buoi(cd, phut)
                o.append({"hoc_phi": goc, "thu_lao": thu_lao, "trung_tam": goc - thu_lao})
            f = form_cap_do if form_cap_do is not None and form_cap_do.instance.pk == cd.pk \
                else CapDoForm(instance=cd, prefix=f"cd{cd.pk}")
            hang.append((cd, o, f))
        ds_loai.append((loai, hang))
    return render(request, "core/bang_gia.html", {
        "ds_loai": ds_loai, "khung_gio": khung,
        "ds_mon": MonHoc.objects.select_related("loai_mon"), "ds_loai_mon": LoaiMon.objects.all(),
        "goi": goi, "lich_su_goi": GoiKhoaHoc.objects.select_related("tao_boi")[:30],
        "co_khuyen_mai": any(g.ty_le_giam for g in goi.values()),
        "form_goi": form_goi or GoiKhoaHocForm(),
        "form_them_cap_do": form_them_cap_do or CapDoForm(prefix="moi"),
        "form_loai": form_loai or LoaiMonForm(prefix="loai"),
        "gioi_han_giam": bang_gia.gioi_han_giam(),
    })


@vai_tro_required(ADMIN)
@require_POST
def sua_cap_do(request, pk):
    cd = get_object_or_404(CapDo, pk=pk)
    cu = _mo_ta_gia(cd)
    form = CapDoForm(request.POST, instance=cd, prefix=f"cd{pk}")
    if not form.is_valid():
        return xem(request, form_cap_do=form)
    form.save()
    ghi_nhat_ky(request.user, "Sửa giá cấp độ", str(cd), f"{cu} → {_mo_ta_gia(cd)}")
    messages.success(request, f"Đã cập nhật {cd}. Khóa học đã tạo trước đó giữ nguyên giá cũ.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def them_cap_do(request):
    form = CapDoForm(request.POST, prefix="moi")
    if not form.is_valid():
        return xem(request, form_them_cap_do=form)
    cd = form.save()
    ghi_nhat_ky(request.user, "Thêm cấp độ học", str(cd), _mo_ta_gia(cd))
    messages.success(request, f"Đã thêm cấp độ {cd}.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def them_loai_mon(request):
    form = LoaiMonForm(request.POST, prefix="loai")
    if not form.is_valid():
        return xem(request, form_loai=form)
    loai = form.save()
    ghi_nhat_ky(request.user, "Thêm loại môn", loai.ten)
    messages.success(request, f"Đã thêm loại môn {loai}. Hãy thêm cấp độ (giá) cho loại môn này.")
    return redirect("bang_gia")


@vai_tro_required(ADMIN)
@require_POST
def gan_mon(request):
    doi = []
    loai_theo_id = {str(x.pk): x for x in LoaiMon.objects.all()}
    for mon in MonHoc.objects.all():
        loai = loai_theo_id.get(request.POST.get(f"mon_{mon.pk}", ""))
        if loai and mon.loai_mon_id != loai.pk:
            mon.loai_mon = loai
            mon.save(update_fields=["loai_mon"])
            doi.append(f"{mon} → {loai}")
    if doi:
        ghi_nhat_ky(request.user, "Gán môn vào loại môn", "", "; ".join(doi))
        messages.success(request, "Đã cập nhật: " + ", ".join(doi) + ".")
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
    ghi_nhat_ky(request.user, "Đặt khuyến mãi gói", goi.get_so_buoi_display(),
                f"Giảm {dinh_dang_phan_tram(goi.ty_le_giam)} từ {goi.hieu_luc_tu:%d/%m/%Y} đến {den}")
    messages.success(request, f"Đã đặt {goi} từ {goi.hieu_luc_tu:%d/%m/%Y}.")
    return redirect("bang_gia")
