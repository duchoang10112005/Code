"""Phần 4 – Khóa học (DFD 4.1–4.3; PB-07..PB-10, PB-24).

Quyền: NV tuyển sinh thao tác; Admin chỉ xem; Gia sư chỉ xem khóa của chính mình (không thấy học phí, SĐT phụ huynh).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import KetQuaHocThuForm, KhoaHocForm, LocKhoaHocForm
from core.models import BuoiHoc, KhoaHoc, YeuCauHocTap
from core.permissions import ADMIN, GIA_SU, TUYEN_SINH, vai_tro_required
from core.services import khoa_hoc as dv
from core.services.tien_ich import thong_diep_loi as _loi

YC = YeuCauHocTap.TrangThai
KH = KhoaHoc.TrangThai
SO_BUOI_SAP_HET = 2


# =============================================================================
# 4.1 – 4.2: từ yêu cầu đã phân công → kết quả học thử → khóa học
# =============================================================================
@vai_tro_required(TUYEN_SINH)
@require_POST
def ghi_ket_qua_hoc_thu(request, pk):
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    form = KetQuaHocThuForm(request.POST)
    if not form.is_valid():
        for ten, loi in form.errors.items():
            nhan = form.fields[ten].label if ten in form.fields else ""
            messages.error(request, f"{nhan}: {' '.join(loi)}" if nhan else " ".join(loi))
        return redirect("yeu_cau_chi_tiet", pk=pk)
    try:
        yc = dv.ghi_ket_qua_hoc_thu(request.user, yc, form.cleaned_data["ket_qua"], form.cleaned_data["ghi_chu"])
        if yc.trang_thai == YC.HOC_THU_XONG:
            messages.success(request, "Đã ghi kết quả: tiếp tục học. Điền thông tin để tạo khóa chính thức.")
            return redirect("khoa_hoc_tao", pk=pk)
        if yc.trang_thai == YC.DANG_TIM:
            messages.success(request, "Đã ghi kết quả. Yêu cầu quay về Đang mời gia sư — chọn gia sư khác bên dưới.")
        else:
            messages.success(request, "Đã ghi kết quả. Yêu cầu đã đóng.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)


@vai_tro_required(TUYEN_SINH)
def tao(request, pk):
    yc = get_object_or_404(YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su"), pk=pk)
    if not dv.co_the_tao_khoa(yc):
        messages.error(request, "Yêu cầu này chưa đủ điều kiện tạo khóa (đã học thử thì cần kết quả Đồng ý đăng ký).")
        return redirect("yeu_cau_chi_tiet", pk=pk)
    form = KhoaHocForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            khoa = dv.tao_khoa_hoc(request.user, yc, form.cleaned_data)
            messages.success(request, f"Đã mở {khoa}. Gia sư được báo qua email để bắt đầu tạo buổi học.")
            return redirect("khoa_hoc_chi_tiet", pk=khoa.pk)
        except ValidationError as e:
            form.add_error(None, _loi(e))
    return render(request, "core/khoa_hoc/tao.html", {
        "yc": yc, "form": form, "nhanh_a": yc.trang_thai == YC.DA_PHAN_CONG,
    })


# =============================================================================
# 4.3: theo dõi khóa học
# =============================================================================
@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    form = LocKhoaHocForm(request.GET or None)
    qs = (KhoaHoc.objects.select_related("hoc_vien", "gia_su", "yeu_cau__mon_hoc")
          .annotate(con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung")))
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            q = d["q"].strip()
            dieu_kien = Q(hoc_vien__ho_ten__icontains=q)
            so = q.upper().removeprefix("KH-").lstrip("0")
            if so.isdigit():
                dieu_kien |= Q(pk=int(so))
            qs = qs.filter(dieu_kien)
        if d["trang_thai"]:
            qs = qs.filter(trang_thai=d["trang_thai"])
        if d["gia_su"]:
            qs = qs.filter(gia_su=d["gia_su"])
        if d["mon"]:
            qs = qs.filter(yeu_cau__mon_hoc=d["mon"])
        if d["sap_het"]:
            qs = qs.filter(trang_thai=KH.DANG_HOC, con_lai__lte=SO_BUOI_SAP_HET)
    trang = Paginator(qs.order_by("-tao_luc"), 20).get_page(request.GET.get("page"))
    return render(request, "core/khoa_hoc/danh_sach.html", {"trang": trang, "form": form, "sap_het": SO_BUOI_SAP_HET})


def _trang_chi_tiet(request, khoa, la_gia_su):
    from core.models import DoiGiaSu
    lich_su = khoa.lich_su_doi_gia_su.select_related("gia_su_cu", "gia_su_moi")
    return render(request, "core/khoa_hoc/chi_tiet.html", {
        "khoa": khoa, "la_gia_su": la_gia_su,
        "ds_buoi": khoa.buoi_hoc.select_related("gia_su").order_by("-bat_dau"),
        "lich_su_doi": lich_su if not la_gia_su else [],
        "co_the_doi_gia_su": (not la_gia_su and (request.user.la_tuyen_sinh or request.user.la_admin)
                              and khoa.trang_thai in (KH.DANG_HOC, KH.TAM_DUNG)
                              and khoa.yeu_cau.trang_thai == YC.CHINH_THUC),
        "de_nghi_cho_duyet": lich_su.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET).first(),
        "so_lan_doi": lich_su.filter(trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN).count(),
        "ly_do_doi": DoiGiaSu.LyDo.choices,
        "sap_het": khoa.trang_thai == KH.DANG_HOC and khoa.so_buoi_con_lai <= SO_BUOI_SAP_HET,
        "co_the_doi_trang_thai": khoa.trang_thai in (KH.DANG_HOC, KH.TAM_DUNG),
        "KH": KH,
    })


@vai_tro_required(ADMIN, TUYEN_SINH)
def chi_tiet(request, pk):
    khoa = get_object_or_404(KhoaHoc.objects.select_related("hoc_vien", "gia_su", "yeu_cau__mon_hoc", "tao_boi"), pk=pk)
    return _trang_chi_tiet(request, khoa, la_gia_su=False)


@vai_tro_required(TUYEN_SINH)
@require_POST
def doi_trang_thai(request, pk):
    khoa = get_object_or_404(KhoaHoc, pk=pk)
    try:
        dv.doi_trang_thai_khoa(request.user, khoa, request.POST.get("trang_thai"), request.POST.get("ly_do", ""))
        messages.success(request, f"{khoa}: {khoa.get_trang_thai_display()}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("khoa_hoc_chi_tiet", pk=pk)


# =============================================================================
# Gia sư – Lớp của tôi
# =============================================================================
@vai_tro_required(GIA_SU)
def lop_cua_toi(request):
    u = request.user
    buoi_thu = (BuoiHoc.objects.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=u)
                .exclude(trang_thai=BuoiHoc.TrangThai.DA_HUY).order_by("-bat_dau"))
    cho_chot = (YeuCauHocTap.objects.filter(gia_su=u, trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG])
                .select_related("hoc_vien", "mon_hoc").order_by("-phan_cong_luc")
                .prefetch_related(Prefetch("buoi_hoc", queryset=buoi_thu, to_attr="ds_buoi_thu")))
    ds_khoa = (KhoaHoc.objects.filter(gia_su=u).select_related("hoc_vien", "yeu_cau__mon_hoc")
               .order_by("trang_thai", "-tao_luc"))
    return render(request, "core/khoa_hoc/lop_cua_toi.html", {
        "cho_chot": [(yc, yc.ds_buoi_thu[0] if yc.ds_buoi_thu else None) for yc in cho_chot],
        "ds_khoa": ds_khoa,
    })


@vai_tro_required(GIA_SU)
def khoa_cua_toi(request, pk):
    khoa = get_object_or_404(KhoaHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc"), pk=pk, gia_su=request.user)
    return _trang_chi_tiet(request, khoa, la_gia_su=True)
