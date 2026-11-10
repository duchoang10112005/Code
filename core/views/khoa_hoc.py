"""Phần 4 – Khóa học (DFD 4.1–4.3; PB-07..PB-10, PB-24).

Quyền: NV tuyển sinh thao tác; Admin chỉ xem; Gia sư chỉ xem khóa của chính mình (không thấy học phí, SĐT phụ huynh).
"""

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q
from django.urls import reverse
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
            messages.success(request, "Đã ghi: phụ huynh đồng ý đăng ký. Bước tiếp theo: Mở khóa học.")
            return redirect(reverse("yeu_cau_chi_tiet", args=[pk]) + "?mo=khoa")
        if yc.ket_qua_hoc_thu == "CAN_THEM_THOI_GIAN":
            messages.success(request, "Đã ghi: cần thêm thời gian. Hệ thống nhắc bạn gọi lại phụ huynh sau 2 ngày.")
        elif yc.trang_thai == YC.DANG_TIM:
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
    if request.method != "POST":
        return redirect(reverse("yeu_cau_chi_tiet", args=[pk]) + "?mo=khoa")
    form = KhoaHocForm(request.POST)
    if form.is_valid():
        try:
            khoa = dv.tao_khoa_hoc(request.user, yc, form.du_lieu_khoa())
            messages.success(request, f"Đã mở {khoa.ma}. Gia sư được báo để bắt đầu tạo buổi học.")
            return redirect("khoa_hoc_chi_tiet", pk=khoa.pk)
        except ValidationError as e:
            form.add_error(None, _loi(e))
    from core.views.yeu_cau import trang_chi_tiet_yc
    return trang_chi_tiet_yc(request, yc, form_khoa=form)


# =============================================================================
# 4.3: theo dõi khóa học
# =============================================================================
TAB_KH = [("", "Tất cả"), ("DANG_HOC", "Đang học"), ("sap_het", "Sắp hết buổi"), ("TAM_DUNG", "Tạm dừng"),
          ("HOAN_THANH", "Hoàn thành"), ("HUY", "Đã hủy")]


@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    """Tuyển sinh › Khóa học: tab trạng thái (+ Sắp hết buổi), tìm, lọc môn / Tôi phụ trách, tiến độ đã học / đã xếp."""
    from datetime import date
    from django.db.models import Count, Exists, OuterRef
    from core.models import DoiGiaSu, MonHoc
    from core.services.khoa_hoc import yc_cho_mo_khoa
    NV_SAP_HET = settings.NGHIEP_VU.get("NGUONG_SAP_HET_BUOI", SO_BUOI_SAP_HET)
    goc = (KhoaHoc.objects.select_related("hoc_vien", "gia_su", "yeu_cau__mon_hoc", "yeu_cau__cap_do")
           .annotate(con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung"),
                     da_xep=Count("buoi_hoc", filter=Q(buoi_hoc__trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO)),
                     cho_doi=Exists(DoiGiaSu.objects.filter(khoa_hoc=OuterRef("pk"),
                                                            trang_thai=DoiGiaSu.TrangThai.CHO_DUYET))))
    q = request.GET.get("q", "").strip()
    if q:
        dk = Q(hoc_vien__ho_ten__icontains=q) | Q(gia_su__ho_ten__icontains=q) | Q(ma_lop__iexact=q)
        so = q.upper().removeprefix("KH-").lstrip("0")
        if so.isdigit():
            dk |= Q(pk=int(so))
        goc = goc.filter(dk)
    mon = request.GET.get("mon", "")
    mon = int(mon) if mon.isdigit() else None
    if mon:
        goc = goc.filter(yeu_cau__mon_hoc=mon)
    toi = request.GET.get("toi") == "1"
    if toi:
        goc = goc.filter(tuyen_sinh_phu_trach=request.user)
    sap_het = Q(trang_thai=KH.DANG_HOC, con_lai__lte=NV_SAP_HET)
    nhom = {"": goc, "sap_het": goc.filter(sap_het)}
    for k in (KH.DANG_HOC, KH.TAM_DUNG, KH.HOAN_THANH, KH.HUY):
        nhom[k] = goc.filter(trang_thai=k)
    nhom[KH.DANG_HOC] = nhom[KH.DANG_HOC].exclude(sap_het)
    tab = "sap_het" if request.GET.get("sap_het") else request.GET.get("tinh_trang", "")
    tab = tab if tab in nhom else ""
    dem = {k: v.count() for k, v in nhom.items()}
    trang = Paginator(nhom[tab].order_by("-tao_luc"), 20).get_page(request.GET.get("page"))
    for k in trang:
        k.sap_het_k = k.trang_thai == KH.DANG_HOC and k.con_lai <= NV_SAP_HET
        k.pt_xep = min(100 - k.phan_tram, round(k.da_xep * 100 / k.so_buoi_dang_ky) if k.so_buoi_dang_ky else 0)
    dau_thang = date.today().replace(day=1)
    tat_ca = KhoaHoc.objects.annotate(con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung"))
    qs_loc = request.GET.copy()
    for k in ("page", "sap_het"):
        qs_loc.pop(k, None)
    return render(request, "core/khoa_hoc/danh_sach.html", {
        "trang": trang, "tab": tab, "q": q, "mon": mon, "toi": toi,
        "ds_tab": [(k, n, dem[k]) for k, n in TAB_KH], "ds_mon": MonHoc.objects.order_by("ten"),
        "loc_qs": qs_loc.urlencode(), "so_cho_mo": yc_cho_mo_khoa().count(),
        "kpi": {"dang_hoc": tat_ca.filter(trang_thai=KH.DANG_HOC).count(),
                "sap_het": tat_ca.filter(trang_thai=KH.DANG_HOC, con_lai__lte=NV_SAP_HET).count(),
                "tam_dung": tat_ca.filter(trang_thai=KH.TAM_DUNG).count(),
                "hoan_thanh": tat_ca.filter(trang_thai=KH.HOAN_THANH, hoan_thanh_luc__date__gte=dau_thang).count()},
    })


NHAN_CHUYEN = {KH.TAM_DUNG: ("Tạm dừng khóa", "bi-pause-circle", "Tạm dừng khóa học?",
                            "Gia sư sẽ không tạo được buổi mới cho đến khi khóa tiếp tục. Các buổi đã xếp sắp tới sẽ bị hủy.",
                            "VD: Học viên nghỉ thi học kỳ 2 tuần", "pri"),
               KH.DANG_HOC: ("Tiếp tục học", "bi-play-circle", "Tiếp tục khóa học?",
                             "Gia sư tạo lại được buổi học với số buổi còn lại.", "VD: Học viên đi học lại", "pri"),
               KH.HOAN_THANH: ("Đánh dấu hoàn thành", "bi-trophy", "Đánh dấu hoàn thành sớm?",
                               "Các buổi đã xếp sắp tới sẽ bị hủy. Có thể gia hạn lại nếu phụ huynh đăng ký thêm.",
                               "VD: Phụ huynh dừng sớm, đã đạt mục tiêu", "pri"),
               KH.HUY: ("Hủy khóa học", "bi-slash-circle", "Hủy khóa học?",
                        "Các buổi đã xếp lịch sẽ bị hủy và không tính thù lao. Không hoàn tác được.",
                        "VD: Gia đình chuyển nơi ở", "dangerfill")}


def _trang_chi_tiet(request, khoa, la_gia_su=False):
    """Tuyển sinh / QTV › Chi tiết khóa học (SD-23..25)."""
    from core.models import DoiGiaSu, HoSoGiaSu, NhatKy, ThuLao
    from core.services import gia_su as dv_gs
    from core.services import ngoai_le as dv_nl
    u = request.user
    lich_su = khoa.lich_su_doi_gia_su.select_related("gia_su_cu", "gia_su_moi", "tao_boi")
    cho_duyet = lich_su.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET).first()
    ds_buoi = list(khoa.buoi_hoc.select_related("gia_su", "thu_lao").order_by("bat_dau"))
    TT = BuoiHoc.TrangThai
    da_huy = [b for b in ds_buoi if b.trang_thai == TT.DA_HUY]
    da_bu = sum(1 for b in ds_buoi if b.hoc_bu_cho_id)
    da_xep = sum(1 for b in ds_buoi if b.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO)
    for b in ds_buoi:
        tl = getattr(b, "thu_lao", None) if hasattr(b, "thu_lao") else None
        if b.trang_thai == TT.DA_HUY:
            b.tl_nhan, b.tl_mau = "Không tính", "#9AA1B8"
        elif tl and tl.trang_thai == ThuLao.TrangThai.DA_DOI_SOAT:
            b.tl_nhan, b.tl_mau = "Đã đối soát", "#0F766E"
        elif tl:
            b.tl_nhan, b.tl_mau = tl.get_trang_thai_display(), "#4A5068"
        elif b.trang_thai_hien_thi[0] == "cho_xac_nhan":
            b.tl_nhan, b.tl_mau = "Chờ xác nhận", "#B45309"
        else:
            b.tl_nhan, b.tl_mau = "—", "#9AA1B8"
        b.nhom = ("da_huy" if b.trang_thai == TT.DA_HUY else "da_hoc" if b.trang_thai == TT.HOAN_TAT
                  else "sap_toi" if b.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO else "khac")
    mau_tt = {"TOT": ("#14B8A6", 64), "KHA": ("#60A5FA", 44), "CAN_HO_TRO": ("#F59E0B", 24)}
    tiep_thu = [{"n": b.so_thu_tu or i + 1, "c": mau_tt[b.xep_loai][0], "h": mau_tt[b.xep_loai][1]}
                for i, b in enumerate(x for x in ds_buoi if x.trang_thai == TT.HOAN_TAT and x.xep_loai)][-8:]
    hs = HoSoGiaSu.objects.filter(user=khoa.gia_su).first()
    co_the_doi = (not la_gia_su and (u.la_tuyen_sinh or u.la_admin) and not cho_duyet
                  and khoa.trang_thai in (KH.DANG_HOC, KH.TAM_DUNG) and khoa.yeu_cau.trang_thai == YC.CHINH_THUC)
    chuyen = []
    if u.la_tuyen_sinh:
        for moi, cu in dv.CHUYEN_HOP_LE.items():
            if khoa.trang_thai in cu and not (moi == KH.DANG_HOC and khoa.yeu_cau.trang_thai != YC.CHINH_THUC):
                n = NHAN_CHUYEN[moi]
                chuyen.append({"ma": moi, "nhan": n[0], "icon": n[1], "tieu_de": n[2], "mo_ta": n[3], "goi_y": n[4],
                               "nut": n[5]})
    nhat_ky = list(NhatKy.objects.filter(Q(ma_doi_tuong=khoa.ma) | Q(ma_doi_tuong=khoa.yeu_cau.ma))
                   .select_related("nguoi_thuc_hien").order_by("-thoi_diem")[:12])
    return render(request, "core/khoa_hoc/chi_tiet.html", {
        "khoa": khoa, "yc": khoa.yeu_cau, "hv": khoa.hoc_vien, "ds_buoi": ds_buoi,
        "tien_do": {"da_hoc": khoa.so_buoi_da_dung, "da_xep": da_xep,
                    "con_lai": max(khoa.so_buoi_dang_ky - khoa.so_buoi_da_dung - da_xep, 0),
                    "da_huy": len(da_huy), "da_bu": da_bu,
                    "pt_hoc": khoa.phan_tram,
                    "pt_xep": round(da_xep * 100 / khoa.so_buoi_dang_ky) if khoa.so_buoi_dang_ky else 0},
        "dem_buoi": {"tat_ca": len(ds_buoi), "da_hoc": sum(1 for b in ds_buoi if b.nhom == "da_hoc"),
                     "sap_toi": sum(1 for b in ds_buoi if b.nhom == "sap_toi"), "da_huy": len(da_huy)},
        "tiep_thu": tiep_thu, "hs_gs": hs, "cs_gs": dv_gs.chi_so_gia_su(hs) if hs else None,
        "so_buoi_gs_day": BuoiHoc.objects.filter(gia_su=khoa.gia_su, trang_thai=TT.HOAN_TAT).count(),
        "lich_su_doi": lich_su, "cho_duyet": cho_duyet,
        "so_lan_doi": lich_su.filter(trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN).count(),
        "co_the_doi_gia_su": co_the_doi, "ly_do_doi": DoiGiaSu.LyDo.choices,
        "goi_y_gs": dv_nl.goi_y_gia_su_moi(khoa) if co_the_doi else [],
        "co_the_gia_han": u.la_tuyen_sinh and khoa.trang_thai in (KH.DANG_HOC, KH.HOAN_THANH),
        "co_the_sua_so": u.la_admin, "toi_thieu": max(khoa.so_buoi_da_dung + da_xep, 1),
        "ds_chuyen": chuyen, "sap_het": khoa.sap_het_buoi, "nhat_ky": nhat_ky,
        "lich_su_gia_han": khoa.lich_su_gia_han.select_related("tao_boi")[:5],
        "mo": request.GET.get("mo", ""), "link_lop": request.build_absolute_uri(f"/lop/{khoa.ma_lop}/"),
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
        messages.success(request, f"{khoa.ma}: {khoa.get_trang_thai_display()}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("khoa_hoc_chi_tiet", pk=pk)


@vai_tro_required(TUYEN_SINH)
@require_POST
def gia_han(request, pk):
    """SD-24: Tuyển sinh gia hạn thêm buổi (chỉ tăng)."""
    khoa = get_object_or_404(KhoaHoc, pk=pk)
    try:
        dv.gia_han(request.user, khoa, request.POST.get("so_buoi_them"), request.POST.get("ly_do", ""),
                   request.POST.get("hoc_phi_moi_buoi") or None)
        messages.success(request, f"Đã gia hạn {khoa.ma}: tổng {khoa.so_buoi_dang_ky} buổi. Đã email gia sư.")
    except (ValidationError, ValueError) as e:
        messages.error(request, _loi(e) if isinstance(e, ValidationError) else "Học phí không hợp lệ.")
        return redirect(f"{reverse('khoa_hoc_chi_tiet', args=[pk])}?mo=gia-han")
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
    """Gia sư xem một khóa mình dạy: tiến độ, lịch cố định, các buổi (không có học phí, SĐT phụ huynh)."""
    from core.services.buoi_hoc import link_lop, nhan_buoi
    khoa = get_object_or_404(KhoaHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc", "tuyen_sinh_phu_trach"),
                             pk=pk, gia_su=request.user)
    ds = list(khoa.buoi_hoc.filter(gia_su=request.user).order_by("-bat_dau"))
    xep = khoa.so_buoi_dang_len_lich
    return render(request, "core/khoa_hoc/khoa_cua_toi.html", {
        "khoa": khoa, "ds_buoi": [{"b": b, "nhan": nhan_buoi(b), "tt": b.trang_thai_hien_thi} for b in ds],
        "link_lop": link_lop(khoa, request), "xep": xep,
        "w_da": round(khoa.so_buoi_da_dung * 100 / khoa.so_buoi_dang_ky),
        "w_xep": round(xep * 100 / khoa.so_buoi_dang_ky),
        "lich": ", ".join(f"{['T2','T3','T4','T5','T6','T7','CN'][int(x['thu'])]} {x['gio']}"
                          for x in (khoa.lich_co_dinh or []) if "thu" in x and "gio" in x),
    })
