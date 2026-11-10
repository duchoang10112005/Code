"""Phần 2 – Hồ sơ gia sư (tiến trình 2.0 trên DFD; PB-04, PB-19, PB-24)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import HoSoGiaSuForm, LichRanhForm, LocGiaSuForm
from core.models import HoSoGiaSu, LichRanh, MinhChung, MonGiaSu, User
from core.permissions import ADMIN, GIA_SU, TUYEN_SINH, vai_tro_required
from core.services import gia_su as dv
from core.services.tien_ich import thong_diep_loi as _loi


# =============================================================================
# Gia sư – Hồ sơ của tôi
# =============================================================================
def _ho_so_cua(user):
    ho_so, _ = HoSoGiaSu.objects.get_or_create(user=user)
    return ho_so


def _trang_ho_so(request, ho_so, form_ho_so=None, loi_mon=None, status=200):
    import json
    from core.models import CapDo, LichRanh, MonHoc
    from core.services.yeu_cau import KHUNG
    ranh = {f"{t}-{k}" for t, k in ho_so.lich_ranh.exclude(khung="").values_list("thu", "khung")}
    dang_day = dv.khung_dang_day(ho_so)
    nhan = dict(LichRanh.Khung.choices)
    luoi = [{"ma": k, "ten": nhan[k].rsplit(" ", 1)[0], "gio": LichRanh.GIO_KHUNG[k],
             "o": [{"ma": f"{t}-{k}", "ranh": f"{t}-{k}" in ranh, "lop": dang_day.get(f"{t}-{k}")} for t in range(7)]}
            for k in KHUNG]
    ds_mon = list(ho_so.mon_day.select_related("mon_hoc").prefetch_related("minh_chung", "cap_do_duyet")
                  .order_by("trang_thai", "mon_hoc__ten"))
    da_dang_ky = {m.mon_hoc_id for m in ds_mon if m.trang_thai in ("DA_DUYET", "CHO_DUYET")}
    mon_mo = [{"pk": m.pk, "ten": m.ten, "ma": m.ma, "bai_test_url": m.bai_test_url, "so_cau": m.bai_test_so_cau,
               "phut": m.bai_test_phut, "diem_dat": float(m.diem_dat) if m.diem_dat is not None else None,
               "cap_do": [{"pk": c.pk, "ten": c.ten} for c in CapDo.objects.filter(dang_mo=True, mon_hoc=m)
                          .order_by("thu_tu", "ten")],
               "ly_do_tu_choi": next((x.ghi_chu_duyet for x in ds_mon if x.mon_hoc_id == m.pk and x.trang_thai == "TU_CHOI"), "")}
              for m in MonHoc.objects.filter(dang_mo=True).exclude(pk__in=da_dang_ky).order_by("ten")]
    u = ho_so.user
    muc = [bool(u.so_dien_thoai), bool(ho_so.trinh_do or ho_so.truong_hoc), bool(ho_so.kinh_nghiem),
           bool(ranh), any(m.trang_thai == "DA_DUYET" for m in ds_mon)]
    return render(request, "core/gia_su/ho_so_cua_toi.html", {
        "ho_so": ho_so, "ds_mon": ds_mon, "luoi": luoi, "so_ranh": len(ranh),
        "so_mon_duyet": sum(1 for m in ds_mon if m.trang_thai == "DA_DUYET"),
        "form_ho_so": form_ho_so or HoSoGiaSuForm(instance=ho_so), "loi_mon": loi_mon,
        "hoan_thien": round(sum(muc) * 100 / len(muc)), "loai_minh_chung": MinhChung.Loai.choices,
        "du_lieu_mon": json.dumps(mon_mo), "gui_lai": request.GET.get("gui_lai", ""),
        "buoc_wizard": [("Chọn môn", "Môn và cấp độ"), ("Bài test", "Điểm và ảnh kết quả"),
                        ("Minh chứng", "Bằng cấp, chứng chỉ"), ("Xem lại", "Cam kết và gửi")],
    }, status=status)


@vai_tro_required(GIA_SU)
def ho_so_cua_toi(request):
    return _trang_ho_so(request, _ho_so_cua(request.user))


@vai_tro_required(GIA_SU)
@require_POST
def cap_nhat_ho_so(request):
    ho_so = _ho_so_cua(request.user)
    tam_nghi_cu = ho_so.tam_nghi_den
    form = HoSoGiaSuForm(request.POST, instance=ho_so)
    if form.is_valid():
        ho_so = form.save()
        n = dv.cap_nhat_ho_so(ho_so, tam_nghi_cu)
        messages.success(request, "Đã lưu thông tin hồ sơ." + (f" Đã vô hiệu {n} lời mời đang chờ vì bạn tạm nghỉ." if n else ""))
        return redirect("ho_so_cua_toi")
    return _trang_ho_so(request, ho_so, form_ho_so=form, status=400)


def _doc_minh_chung(request):
    """Đọc các dòng minh chứng mc-<i>-loai / -url / -mo_ta / -tep (popup đăng ký môn)."""
    ds = []
    for i in range(int(request.POST.get("mc_so", 0) or 0)):
        loai = request.POST.get(f"mc-{i}-loai")
        if not loai:
            continue
        ds.append({"loai": loai, "url": request.POST.get(f"mc-{i}-url", "").strip(),
                   "tep": request.FILES.get(f"mc-{i}-tep"), "mo_ta": request.POST.get(f"mc-{i}-mo_ta", "")})
    return ds


@vai_tro_required(GIA_SU)
@require_POST
def dang_ky_mon(request):
    """Đăng ký môn – popup 4 bước (SD-27): cấp độ, bài test, minh chứng, xem lại."""
    from decimal import Decimal, InvalidOperation
    from core.models import MonHoc
    ho_so = _ho_so_cua(request.user)
    mon = MonHoc.objects.filter(pk=request.POST.get("mon_hoc") or 0).first()
    day_du = request.POST.get("v2") == "1"
    try:
        if mon is None:
            raise ValidationError({"mon_hoc": "Chọn môn muốn dạy."})
        if day_du and not request.POST.get("cam_ket"):
            raise ValidationError({"cam_ket": "Đánh dấu cam kết trước khi gửi đăng ký."})
        diem = None
        if request.POST.get("diem_test", "").strip():
            try:
                diem = Decimal(request.POST["diem_test"].replace(",", "."))
            except InvalidOperation:
                raise ValidationError({"diem_test": "Nhập điểm từ 0 đến 10."})
        mg = dv.dang_ky_mon(ho_so, mon, cap_do=request.POST.get("cap_do", ""),
                            cap_do_ids=[int(x) for x in request.POST.getlist("cap_do_ids") if x.isdigit()],
                            diem_test=diem, anh_ket_qua=request.FILES.get("anh_ket_qua_test"),
                            link_ket_qua=request.POST.get("link_ket_qua_test", "").strip(),
                            minh_chung=_doc_minh_chung(request), ly_do_dang_ky=request.POST.get("ly_do_dang_ky", ""),
                            bat_buoc_day_du=day_du)
    except ValidationError as e:
        if request.headers.get("X-Requested-With") == "fetch":
            from core.api import loi_nghiep_vu
            return loi_nghiep_vu(e)
        messages.error(request, _loi(e))
        return redirect("ho_so_cua_toi")
    msg = f"Đã gửi đăng ký môn {mg.mon_hoc}. Quản trị viên duyệt trong 1–2 ngày làm việc."
    if request.headers.get("X-Requested-With") == "fetch":
        from core.api import tra_ve
        messages.success(request, msg)
        return tra_ve(True, msg)
    messages.success(request, msg)
    return redirect("ho_so_cua_toi")


@vai_tro_required(ADMIN, GIA_SU)
def xem_tep(request, loai, pk):
    """Tệp minh chứng / ảnh kết quả test: chỉ chủ hồ sơ và Quản trị viên mở được."""
    from django.http import FileResponse, Http404
    from core.models import MinhChung
    if loai == "mc":
        obj = get_object_or_404(MinhChung.objects.select_related("ho_so"), pk=pk)
        tep, chu = obj.tep, obj.ho_so.user_id
    else:
        obj = get_object_or_404(MonGiaSu.objects.select_related("ho_so"), pk=pk)
        tep, chu = obj.anh_ket_qua_test, obj.ho_so.user_id
    if not tep or (not request.user.la_admin and request.user.pk != chu):
        raise Http404
    return FileResponse(tep.open("rb"), filename=tep.name.rsplit("/", 1)[-1])


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
            messages.error(request, _loi(e))
            return _trang_ho_so(request, ho_so, status=400)
    messages.error(request, " ".join(m for v in form.errors.values() for m in v) or "Giờ rảnh chưa hợp lệ.")
    return _trang_ho_so(request, ho_so, status=400)


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
