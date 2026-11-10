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

from core.forms import HocVienForm, KetQuaHocThuForm, LocYeuCauForm, YeuCauForm
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
TAB_YC = [("", "Tất cả"), ("MOI", "Mới"), ("DANG_TIM", "Đang mời gia sư"), ("DA_PHAN_CONG", "Đã có gia sư"),
          ("HOC_THU_XONG", "Học thử"), ("CHINH_THUC", "Đã mở khóa"), ("DONG", "Đã đóng")]


@vai_tro_required(ADMIN, TUYEN_SINH)
def danh_sach(request):
    """Tuyển sinh – Yêu cầu học tập: tab trạng thái + đếm, tìm (bỏ dấu), lọc môn / người tạo, Bước tiếp theo."""
    from django.db.models import Prefetch
    from core.models import BuoiHoc, MonHoc
    from core.services.tim_kiem import chuan_hoa
    dv.quet_loi_moi_het_han()
    tt = request.GET.get("trang_thai", "")
    q = request.GET.get("q", "").strip()
    mon = request.GET.get("mon", "")
    nguoi = request.GET.get("nguoi", "")
    goc = YeuCauHocTap.objects.all()
    if mon.isdigit():
        goc = goc.filter(mon_hoc_id=int(mon))
    if nguoi == "toi":
        goc = goc.filter(tao_boi=request.user)
    dem = {k: (goc.filter(trang_thai=k) if k else goc).count() for k, _ in TAB_YC}
    qs = goc.filter(trang_thai=tt) if tt else goc
    qs = qs.select_related("hoc_vien", "mon_hoc", "gia_su", "tao_boi", "khoa_hoc").prefetch_related(
        "loi_moi", Prefetch("buoi_hoc", queryset=BuoiHoc.objects.filter(loai=BuoiHoc.Loai.HOC_THU))).order_by("-tao_luc")
    if q:
        cq = chuan_hoa(q)
        so = cq.removeprefix("yc").lstrip("0")
        ids = [y.pk for y in qs.only("pk", "hoc_vien__ho_ten", "hoc_vien__ten_phu_huynh", "hoc_vien__sdt_phu_huynh")
               if (so.isdigit() and y.pk == int(so)) or cq in chuan_hoa(y.hoc_vien.ho_ten)
               or cq in chuan_hoa(y.hoc_vien.ten_phu_huynh) or cq in y.hoc_vien.sdt_phu_huynh]
        qs = qs.filter(pk__in=ids)
    trang = Paginator(qs, 20).get_page(request.GET.get("page"))
    dong = [{"yc": y, "buoc": dv.buoc_tiep_theo(y), "mau": dv.MAU_TRANG_THAI_YC.get(y.trang_thai, "xam"),
             "co_the_dong": y.trang_thai in (YC.MOI, YC.DANG_TIM)} for y in trang]
    return render(request, "core/yeu_cau/danh_sach.html", {
        "trang": trang, "dong": dong, "tab": TAB_YC, "dem": dem, "tt": tt, "q": q, "mon": mon, "nguoi": nguoi,
        "ds_mon": MonHoc.objects.order_by("ten"), "ly_do_dong": dv.LY_DO_DONG,
    })


@vai_tro_required(TUYEN_SINH)
def tao(request):
    """Tuyển sinh – Tạo yêu cầu (SD-05): học viên mới / đã có, lưới khung giờ, xem trước."""
    import json
    from core.models import CapDo
    hv_pk = request.POST.get("hoc_vien") or request.GET.get("hoc_vien") or ""
    hv_co_san = HocVien.objects.filter(pk=hv_pk).first() if str(hv_pk).isdigit() else None
    form_hv = HocVienForm(request.POST or None, prefix="hv")
    form_yc = YeuCauForm(request.POST or None)
    if request.method == "POST":
        hv_hop_le = bool(hv_co_san) or form_hv.is_valid()
        if form_yc.is_valid() and hv_hop_le:
            with transaction.atomic():
                hoc_vien = hv_co_san
                if not hoc_vien:
                    hoc_vien = form_hv.save(commit=False)
                    hoc_vien.tao_boi = hoc_vien.tuyen_sinh_phu_trach = request.user
                    hoc_vien.save()
                    ghi_nhat_ky(request.user, "Thêm học viên", hoc_vien.ho_ten)
                du_lieu = {k: v for k, v in form_yc.cleaned_data.items()}
                yc = dv.tao_yeu_cau(request.user, hoc_vien, du_lieu)
            messages.success(request, f"Đã tiếp nhận {yc.ma}. Chọn gia sư bên dưới để gửi lời mời.")
            return redirect("yeu_cau_chi_tiet", pk=yc.pk)
    cap_do = {}
    for c in CapDo.objects.filter(dang_mo=True).order_by("thu_tu", "ten"):
        cap_do.setdefault(str(c.mon_hoc_id or ""), []).append({"pk": c.pk, "ten": c.ten})
    so_loi = len(form_yc.errors) + (0 if hv_co_san else len(form_hv.errors))
    return render(request, "core/yeu_cau/tao.html", {
        "form_hv": form_hv, "form_yc": form_yc, "hv_co_san": hv_co_san, "so_loi": so_loi,
        "khung_chon": form_yc.data.getlist("khung_mong_muon") if form_yc.is_bound else [],
        "cap_do_js": json.dumps(cap_do), "luoi": _luoi_khung(),
    }, status=400 if request.method == "POST" else 200)


def _luoi_khung():
    from core.models import LichRanh
    nhan = dict(LichRanh.Khung.choices)
    return [{"ma": k, "ten": nhan[k].rsplit(" ", 1)[0], "gio": LichRanh.GIO_KHUNG[k]}
            for k in ("SANG", "CHIEU", "TOI_SOM", "TOI")]


BUOC_YC = [("MOI", "Mới"), ("DANG_TIM", "Đang mời gia sư"), ("DA_PHAN_CONG", "Đã có gia sư"),
           ("HOC_THU_XONG", "Học thử"), ("CHINH_THUC", "Đã mở khóa")]


def trang_chi_tiet_yc(request, yc, form_khoa=None, status=None):
    """Tuyển sinh – Chi tiết yêu cầu (SD-06..SD-12)."""
    from core.forms import KhoaHocForm
    from core.models import NhatKy
    from core.services.yeu_cau import luoi_khop
    dv.quet_loi_moi_het_han()
    yc.refresh_from_db()
    de_xuat = dv.de_xuat_gia_su(yc) if _co_the_sua(yc) else []
    thu_tu = [k for k, _ in BUOC_YC]
    hien = 2 if (yc.trang_thai == YC.DA_PHAN_CONG and dv_kh.buoi_hoc_thu_gan_nhat(yc)) else (
        thu_tu.index(yc.trang_thai) if yc.trang_thai in thu_tu else -1)
    buoc = [{"ten": n, "lop": "xong" if i < hien else ("dang" if i == hien else "")} for i, (_, n) in enumerate(BUOC_YC)]
    hang, _, _, _ = luoi_khop(None, yc.khung_mong_muon)
    dong_tg = [{"luc": x.thoi_diem, "ai": x.nguoi_thuc_hien.ho_ten if x.nguoi_thuc_hien else "Hệ thống",
                "chu": x.hanh_dong[:1].lower() + x.hanh_dong[1:], "phu": x.chi_tiet[:120]}
               for x in NhatKy.objects.filter(ma_doi_tuong=yc.ma).select_related("nguoi_thuc_hien").order_by("-thoi_diem")[:12]]
    for lm in yc.loi_moi.select_related("gia_su").exclude(phan_hoi_luc=None).exclude(trang_thai="VOIDED"):
        dong_tg.append({"luc": lm.phan_hoi_luc, "ai": lm.gia_su.ho_ten, "phu": lm.ly_do_tu_choi or lm.ghi_chu_gia_su,
                        "chu": {"ACCEPTED": "nhận lớp", "REJECTED": "từ chối lời mời"}.get(lm.trang_thai, "để lời mời hết hạn")})
    dong_tg.sort(key=lambda x: x["luc"], reverse=True)
    ctx = {
        "yc": yc, "de_xuat": de_xuat, "co_the_sua": _co_the_sua(yc), "buoc": buoc, "luoi": hang,
        "ds_loi_moi": yc.loi_moi.select_related("gia_su").order_by("-gui_luc"), "dong_tg": dong_tg[:12],
        "mau_tt": dv.MAU_TRANG_THAI_YC.get(yc.trang_thai, "xam"), "buoc_tiep": dv.buoc_tiep_theo(yc),
        "ly_do_dong": dv.LY_DO_DONG, "form_khoa": form_khoa or KhoaHocForm(initial={"thoi_luong_phut": 90}),
        "mo": "khoa" if form_khoa is not None else request.GET.get("mo", ""), "KQ": YeuCauHocTap.KetQuaHocThu,
    }
    if yc.trang_thai in (YC.DA_PHAN_CONG, YC.HOC_THU_XONG):
        ctx.update(buoi_thu=dv_kh.buoi_hoc_thu_gan_nhat(yc), buoi_thu_hoan_tat=dv_kh.buoi_hoc_thu_hoan_tat(yc),
                   co_the_tao_khoa=dv_kh.co_the_tao_khoa(yc), co_the_dang_ky_thang=(
                       yc.trang_thai == YC.DA_PHAN_CONG and not yc.dang_ky_thang and not dv_kh.co_buoi_hoc_thu(yc)),
                   co_the_ghi_kq=bool(dv_kh.buoi_hoc_thu_hoan_tat(yc)) and yc.trang_thai == YC.DA_PHAN_CONG)
    if yc.trang_thai == YC.CHINH_THUC:
        ctx["khoa"] = getattr(yc, "khoa_hoc", None)
    if request.user.la_admin and yc.trang_thai in (YC.MOI, YC.DANG_TIM):
        ctx["gs_gan_thang"] = [d["ho_so"].user for d in de_xuat if not d["tam_nghi"]]
    return render(request, "core/yeu_cau/chi_tiet.html", ctx, status=status or 200)


@vai_tro_required(ADMIN, TUYEN_SINH)
def chi_tiet(request, pk):
    yc = get_object_or_404(YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su", "tao_boi", "cap_do"), pk=pk)
    return trang_chi_tiet_yc(request, yc)


@vai_tro_required(TUYEN_SINH)
@require_POST
def dang_ky_thang(request, pk):
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    try:
        dv_kh.danh_dau_dang_ky_thang(request.user, yc)
        messages.success(request, "Đã ghi: phụ huynh đăng ký chính thức luôn. Bước tiếp theo: Mở khóa học.")
        return redirect(reverse("yeu_cau_chi_tiet", args=[pk]) + "?mo=khoa")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)


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
    """SD-09. Gọi bằng fetch sau khi hết thời gian Hoàn tác (trả JSON), hoặc form thường."""
    yc = get_object_or_404(YeuCauHocTap, pk=pk)
    la_api = request.headers.get("X-Requested-With") == "fetch"
    ly_do = request.POST.get("ly_do", "").strip()
    if request.POST.get("ghi_chu", "").strip():
        ly_do = f"{ly_do}: {request.POST['ghi_chu'].strip()}"
    try:
        dv.dong_yeu_cau(request.user, yc, ly_do)
        msg = f"Đã đóng {yc.ma}. Các lời mời đang chờ đã bị hủy."
        if la_api:
            from core.api import tra_ve
            return tra_ve(True, msg)
        messages.success(request, msg)
    except ValidationError as e:
        if la_api:
            from core.api import loi_nghiep_vu
            return loi_nghiep_vu(e)
        messages.error(request, _loi(e))
    return redirect(request.POST.get("tiep") if str(request.POST.get("tiep", "")).startswith("/") else
                    reverse("yeu_cau_chi_tiet", args=[pk]))


# =============================================================================
# NV tuyển sinh – Học viên
# =============================================================================
@vai_tro_required(ADMIN, TUYEN_SINH)
def hoc_vien_danh_sach(request):
    return _trang_hoc_vien(request)


def _trang_hoc_vien(request, form_sua=None, chon_pk=None):
    """Tuyển sinh › Học viên: tab theo tình trạng suy ra, lọc môn / Tôi phụ trách, khung chi tiết bên phải."""
    from core.models import BuoiHoc, MonHoc
    from core.services import hoc_vien as dv_hv
    q = request.GET.get("q", "").strip()
    mon = request.GET.get("mon", "")
    mon = int(mon) if mon.isdigit() else None
    toi = request.GET.get("toi") == "1"
    tat_ca = dv_hv.ds_hoc_vien(q, mon, request.user if toi else None)
    dem = {"": len(tat_ca)}
    for k, _, _ in dv_hv.TINH_TRANG:
        dem[k] = sum(1 for x in tat_ca if x["tt"][0] == k)
    tab = request.GET.get("tinh_trang", "")
    tab = tab if tab in dem else ""
    loc = [x for x in tat_ca if not tab or x["tt"][0] == tab]
    trang = Paginator(loc, 20).get_page(request.GET.get("page"))
    chon_pk = str(chon_pk or request.GET.get("chon", ""))
    chon = next((x for x in trang if str(x["hv"].pk) == chon_pk), None)
    if chon is None and chon_pk:
        chon = next((x for x in tat_ca if str(x["hv"].pk) == chon_pk), None)
    if chon is None and trang.object_list:
        chon = trang.object_list[0]
    if chon:
        hv = chon["hv"]
        chon["ds_yc"] = sorted(hv.yeu_cau.all(), key=lambda y: y.tao_luc, reverse=True)
        chon["buoi"] = list(BuoiHoc.objects.filter(hoc_vien=hv).order_by("-bat_dau")[:4])
        if request.user.la_tuyen_sinh and form_sua is None:
            form_sua = HocVienForm(instance=hv, prefix="hv")
    from core.models import KhoaHoc
    sap_het = [k for k in KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC) if k.sap_het_buoi]
    qs_loc = request.GET.copy()
    for k in ("chon", "page"):
        qs_loc.pop(k, None)
    return render(request, "core/hoc_vien/danh_sach.html", {
        "trang": trang, "chon": chon, "q": q, "mon": mon, "toi": toi, "tab": tab,
        "ds_tab": [("", "Tất cả", dem[""])] + [(k, n, dem[k]) for k, n, _ in dv_hv.TINH_TRANG],
        "ds_mon": MonHoc.objects.order_by("ten"), "loc_qs": qs_loc.urlencode(),
        "kpi": {"tong": HocVien.objects.count(), "dang_hoc": dem["dang_hoc"] if not (q or mon or toi) else None,
                "dang_tim": (dem["dang_tim"] + dem["hoc_thu"]) if not (q or mon or toi) else None,
                "sap_het": len(sap_het)},
        "form_sua": form_sua, "mo_sua": form_sua is not None and form_sua.is_bound,
    }, status=400 if form_sua is not None and form_sua.is_bound else 200)


@vai_tro_required(ADMIN, TUYEN_SINH)
def hoc_vien_chi_tiet(request, pk):
    """GET → danh sách với khung chi tiết của học viên này. POST (Tuyển sinh) → sửa thông tin."""
    hv = get_object_or_404(HocVien, pk=pk)
    if request.method == "POST" and request.user.la_tuyen_sinh:
        form = HocVienForm(request.POST, instance=hv, prefix="hv")
        if form.is_valid():
            form.save()
            ghi_nhat_ky(request.user, "Sửa thông tin học viên", hv.ho_ten, ", ".join(form.changed_data))
            messages.success(request, "Đã lưu thông tin học viên.")
            return redirect(f"{reverse('hoc_vien_danh_sach')}?chon={pk}")
        return _trang_hoc_vien(request, form_sua=form, chon_pk=pk)
    return redirect(f"{reverse('hoc_vien_danh_sach')}?chon={pk}")


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
