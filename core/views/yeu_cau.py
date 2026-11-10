"""Phần 3 – Tiếp nhận yêu cầu, đề xuất gia sư, lời mời nhận lớp (DFD 3.1–3.4).

Quyền: NV tuyển sinh thao tác; Admin chỉ xem (giám sát); Gia sư chỉ thấy lời mời của chính mình.
"""

from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import ChonHocVienForm, HocVienForm, KetQuaHocThuForm, LocYeuCauForm, YeuCauForm
from core.models import HocVien, LoiMoi, YeuCauHocTap
from core.permissions import ADMIN, GIA_SU, TUYEN_SINH, vai_tro_required
from core.services import khoa_hoc as dv_kh
from core.services import yeu_cau as dv
from core.services.nhat_ky import ghi_nhat_ky
from core.services.tien_ich import thong_diep_loi as _loi

YC = YeuCauHocTap.TrangThai
LM = LoiMoi.TrangThai


def _co_the_sua(yc):
    return yc.trang_thai in (YC.MOI, YC.DANG_TIM)


# =============================================================================
# NV tuyển sinh – Yêu cầu học tập
# =============================================================================
@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    dv.quet_loi_moi_het_han()
    form = LocYeuCauForm(request.GET or None)
    qs = (YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su")
          .annotate(so_cho=Count("loi_moi", filter=Q(loi_moi__trang_thai=LM.CHO)),
                    so_tu_choi=Count("loi_moi", filter=Q(loi_moi__trang_thai=LM.REJECTED)),
                    so_het_han=Count("loi_moi", filter=Q(loi_moi__trang_thai=LM.HET_HAN))))
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            q = d["q"].strip()
            dieu_kien = (Q(hoc_vien__ho_ten__icontains=q) | Q(hoc_vien__ten_phu_huynh__icontains=q)
                         | Q(hoc_vien__sdt_phu_huynh__icontains=q))
            so = q.upper().removeprefix("YC-").lstrip("0")
            if so.isdigit():
                dieu_kien |= Q(pk=int(so))
            qs = qs.filter(dieu_kien)
        if d["trang_thai"]:
            qs = qs.filter(trang_thai=d["trang_thai"])
        if d["mon"]:
            qs = qs.filter(mon_hoc=d["mon"])
        if d["cho_chot"]:
            qs = qs.filter(trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG])
        if d["can_moi_them"]:
            qs = qs.filter(trang_thai=YC.DANG_TIM, so_cho=0)
    qs = qs.order_by("-tao_luc")
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "core/yeu_cau/danh_sach.html", {"trang": trang, "form": form})


@vai_tro_required(TUYEN_SINH)
def tao(request):
    chon = ChonHocVienForm(request.POST or None, initial={"hoc_vien": request.GET.get("hoc_vien")})
    form_hv = HocVienForm(request.POST or None, prefix="hv")
    form_yc = YeuCauForm(request.POST or None)
    if request.method == "POST":
        hv_co_san = chon.cleaned_data.get("hoc_vien") if chon.is_valid() else None
        hv_hop_le = bool(hv_co_san) or form_hv.is_valid()
        if form_yc.is_valid() and hv_hop_le:
            with transaction.atomic():
                hoc_vien = hv_co_san
                if not hoc_vien:
                    hoc_vien = form_hv.save(commit=False)
                    hoc_vien.tao_boi = request.user
                    hoc_vien.save()
                    ghi_nhat_ky(request.user, "Thêm học viên", hoc_vien.ho_ten)
                yc = dv.tao_yeu_cau(request.user, hoc_vien, form_yc.cleaned_data)
            messages.success(request, f"Đã tiếp nhận {yc.ma}. Chọn gia sư bên dưới để gửi lời mời.")
            return redirect("yeu_cau_chi_tiet", pk=yc.pk)
    return render(request, "core/yeu_cau/tao.html", {"chon": chon, "form_hv": form_hv, "form_yc": form_yc})


@vai_tro_required(ADMIN, TUYEN_SINH)
def chi_tiet(request, pk):
    dv.quet_loi_moi_het_han()
    yc = get_object_or_404(YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su", "tao_boi"), pk=pk)
    de_xuat = dv.de_xuat_gia_su(yc) if _co_the_sua(yc) else []
    ctx = {
        "yc": yc,
        "ds_loi_moi": yc.loi_moi.select_related("gia_su").order_by("-gui_luc"),
        "de_xuat": de_xuat,
        "co_the_sua": _co_the_sua(yc),
        "thu_can": set(yc.thu_mong_muon or []),
    }
    # Phần 4 – "Bước tiếp theo" sau khi đã có gia sư nhận lớp
    if yc.trang_thai in (YC.DA_PHAN_CONG, YC.HOC_THU_XONG):
        ctx.update(
            buoi_thu=dv_kh.buoi_hoc_thu_gan_nhat(yc),
            buoi_thu_hoan_tat=dv_kh.buoi_hoc_thu_hoan_tat(yc),
            co_the_tao_khoa=dv_kh.co_the_tao_khoa(yc),
            form_kq=KetQuaHocThuForm(),
        )
    if yc.trang_thai == YC.CHINH_THUC:
        ctx["khoa"] = getattr(yc, "khoa_hoc", None)
    return render(request, "core/yeu_cau/chi_tiet.html", ctx)


@vai_tro_required(ADMIN, TUYEN_SINH)
def sua(request, pk):
    """NVTS sửa khi yêu cầu còn Mới/Đang tìm. Admin sửa được cả yêu cầu đã khóa (trừ đã đóng), bắt buộc lý do."""
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    admin_sua_da_khoa = request.user.la_admin and not _co_the_sua(yc) and yc.trang_thai != YC.DONG
    if not _co_the_sua(yc) and not admin_sua_da_khoa:
        messages.error(request, "Yêu cầu đã được phân công hoặc đã đóng, không sửa được nữa.")
        return redirect("yeu_cau_chi_tiet", pk=pk)
    if request.user.la_admin and not admin_sua_da_khoa and not request.user.la_tuyen_sinh:
        admin_sua_da_khoa = True  # Admin sửa yêu cầu đang mở cũng phải ghi lý do
    form = YeuCauForm(request.POST or None, instance=yc,
                      khoa_mon=yc.loi_moi.exists() or hasattr(yc, "khoa_hoc"))
    ly_do = (request.POST.get("ly_do") or "").strip()[:300]
    loi_ly_do = request.method == "POST" and admin_sua_da_khoa and not ly_do
    if request.method == "POST" and form.is_valid() and not loi_ly_do:
        form.save()
        ghi_nhat_ky(request.user, "Admin sửa yêu cầu học tập" if admin_sua_da_khoa else "Sửa yêu cầu học tập",
                    yc.ma, ", ".join(form.changed_data) + (f". Lý do: {ly_do}" if ly_do else ""))
        messages.success(request, f"Đã cập nhật {yc.ma}.")
        return redirect("yeu_cau_chi_tiet", pk=pk)
    return render(request, "core/yeu_cau/sua.html", {"yc": yc, "form": form, "can_ly_do": admin_sua_da_khoa,
                                                     "ly_do": ly_do, "loi_ly_do": loi_ly_do})


@vai_tro_required(TUYEN_SINH)
@require_POST
def gui_loi_moi(request, pk):
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    ids = [int(x) for x in request.POST.getlist("gia_su") if x.isdigit()]
    try:
        moi, bo_qua = dv.gui_loi_moi(request.user, yc, ids)
        if moi:
            messages.success(request, f"Đã gửi {len(moi)} lời mời (hiệu lực 24 giờ). Gia sư được báo qua email.")
        if bo_qua:
            messages.warning(request, f"Bỏ qua {bo_qua} gia sư: đang có lời mời chờ hoặc không còn đủ điều kiện.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)


@vai_tro_required(TUYEN_SINH)
@require_POST
def dong(request, pk):
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    try:
        dv.dong_yeu_cau(request.user, yc, request.POST.get("ly_do", ""))
        messages.success(request, f"Đã đóng {yc.ma}. Các lời mời đang chờ đã bị hủy.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)


# =============================================================================
# NV tuyển sinh – Học viên
# =============================================================================
@vai_tro_required(ADMIN, TUYEN_SINH)
def hoc_vien_danh_sach(request):
    q = request.GET.get("q", "").strip()
    qs = HocVien.objects.annotate(so_yeu_cau=Count("yeu_cau")).order_by("ho_ten")
    if q:
        qs = qs.filter(Q(ho_ten__icontains=q) | Q(ten_phu_huynh__icontains=q) | Q(sdt_phu_huynh__icontains=q))
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "core/hoc_vien/danh_sach.html", {"trang": trang, "q": q})


@vai_tro_required(ADMIN, TUYEN_SINH)
def hoc_vien_chi_tiet(request, pk):
    hv = get_object_or_404(HocVien, pk=pk)
    form = None
    if request.user.la_tuyen_sinh:
        form = HocVienForm(request.POST or None, instance=hv, prefix="hv")
        if request.method == "POST" and form.is_valid():
            form.save()
            ghi_nhat_ky(request.user, "Sửa thông tin học viên", hv.ho_ten, ", ".join(form.changed_data))
            messages.success(request, "Đã lưu thông tin học viên.")
            return redirect("hoc_vien_chi_tiet", pk=pk)
    return render(request, "core/hoc_vien/chi_tiet.html", {
        "hv": hv, "form": form,
        "ds_yeu_cau": hv.yeu_cau.select_related("mon_hoc", "gia_su").order_by("-tao_luc"),
    })


# =============================================================================
# Gia sư – Lời mời nhận lớp
# =============================================================================
@vai_tro_required(GIA_SU)
def loi_moi_cua_toi(request):
    """Gia sư – Lời mời nhận lớp (SD-08): danh sách bên trái, chi tiết + lưới khớp giờ bên phải."""
    from core.services.thong_bao import danh_dau_da_doc
    dv.quet_loi_moi_het_han()
    danh_dau_da_doc(request.user, list(request.user.thong_bao.filter(loai="LOI_MOI", da_doc=False)
                                       .values_list("pk", flat=True)))
    tab = request.GET.get("tab", "cho")
    qs = LoiMoi.objects.filter(gia_su=request.user).select_related(
        "yeu_cau__hoc_vien", "yeu_cau__mon_hoc", "yeu_cau__cap_do", "gui_boi")
    nhom = {
        "cho": qs.filter(trang_thai=LM.CHO).order_by("het_han_luc"),
        "da-nhan": qs.filter(trang_thai=LM.ACCEPTED).order_by("-phan_hoi_luc"),
        "da-dong": qs.filter(trang_thai__in=[LM.REJECTED, LM.VOIDED, LM.HET_HAN]).order_by("-phan_hoi_luc", "-gui_luc"),
    }
    if tab not in nhom:
        tab = "cho"
    ho_so = getattr(request.user, "ho_so_gia_su", None)
    ds = []
    for lm in nhom[tab][:50]:
        _, khop, can, _ = dv.luoi_khop(ho_so, lm.yeu_cau.khung_mong_muon)
        ds.append({"lm": lm, "khop": khop, "can": can, "vach": [i < khop for i in range(can)]})
    chon = None
    try:
        chon_pk = int(request.GET.get("chon", 0))
    except ValueError:
        chon_pk = 0
    chon = next((x for x in ds if x["lm"].pk == chon_pk), ds[0] if ds else None)
    chi_tiet = {}
    if chon:
        lm, yc = chon["lm"], chon["lm"].yeu_cau
        hang, khop, can, thieu = dv.luoi_khop(ho_so, yc.khung_mong_muon)
        so_moi = LoiMoi.objects.filter(yeu_cau=yc, gui_luc__gte=lm.gui_luc - timedelta(minutes=5)).count()
        chi_tiet = {"hang": hang, "khop": khop, "can": can, "thieu": thieu, "so_moi_cung_luc": so_moi,
                    "so_buoi_tuan": len({k.split("-")[0] for k in yc.khung_mong_muon or []}) or len(yc.thu_mong_muon or []),
                    "so_lop_dang_day": request.user.khoa_hoc_phu_trach.filter(trang_thai="DANG_HOC").count(),
                    "so_lop_toi_da": getattr(ho_so, "so_lop_toi_da", 4)}
    return render(request, "core/loi_moi/danh_sach.html", {
        "tab": tab, "ds": ds, "chon": chon, "ct": chi_tiet,
        "dem": {k.replace("-", "_"): v.count() for k, v in nhom.items()}, "ly_do_tu_choi": LoiMoi.LY_DO_TU_CHOI_GOI_Y,
    })


@vai_tro_required(GIA_SU)
@require_POST
def nhan_lop(request, pk):
    lm = get_object_or_404(LoiMoi.objects.select_related("yeu_cau"), pk=pk, gia_su=request.user)
    if not request.POST.get("cam_ket"):
        messages.error(request, "Đánh dấu xác nhận dạy đúng các khung giờ đã khớp để nhận lớp.")
        return redirect(f"{reverse('loi_moi_cua_toi')}?chon={pk}")
    try:
        yc = dv.chap_nhan(request.user, lm, cam_ket=True, ghi_chu=request.POST.get("ghi_chu_gia_su", ""))
        messages.success(request, f"Bạn đã nhận lớp {yc.mon_hoc} – {yc.hoc_vien}. "
                                  "Bước tiếp: Tuyển sinh chốt lớp và xếp buổi học thử với phụ huynh.")
        return redirect(f"{reverse('loi_moi_cua_toi')}?tab=da-nhan&chon={pk}")
    except ValidationError as e:
        messages.warning(request, _loi(e))
    return redirect(f"{reverse('loi_moi_cua_toi')}?chon={pk}")


@vai_tro_required(GIA_SU)
@require_POST
def tu_choi_loi_moi(request, pk):
    lm = get_object_or_404(LoiMoi, pk=pk, gia_su=request.user)
    ly_do = request.POST.get("ly_do", "").strip()
    if not ly_do:
        messages.error(request, "Vui lòng chọn lý do từ chối.")
        return redirect(f"{reverse('loi_moi_cua_toi')}?chon={pk}")
    ghi_chu = request.POST.get("ghi_chu", "").strip()
    try:
        dv.tu_choi(request.user, lm, f"{ly_do}: {ghi_chu}" if ghi_chu else ly_do)
        messages.success(request, "Đã từ chối lời mời. Trung tâm sẽ mời gia sư khác.")
    except ValidationError as e:
        messages.warning(request, _loi(e))
    return redirect("loi_moi_cua_toi")
