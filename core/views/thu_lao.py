"""Phần 6 – Thu nhập (gia sư), đối soát thù lao (NVTS kiểm tra → Admin chốt), xuất CSV."""

import csv
from datetime import datetime, timedelta
from itertools import groupby

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import ThuLao, User
from core.permissions import ADMIN, GIA_SU, TUYEN_SINH, vai_tro_required
from core.services import thu_lao as dv
from core.services.tien_ich import thong_diep_loi as _loi


def _thang(request):
    try:
        return datetime.strptime(request.GET.get("thang") or request.POST.get("thang") or "", "%Y-%m").date()
    except ValueError:
        return dv.dau_thang()


def _thu_lao_trong_thang(gia_su, thang):
    return (ThuLao.objects.filter(gia_su=gia_su, thang=thang)
            .select_related("buoi_hoc__hoc_vien", "buoi_hoc__yeu_cau__mon_hoc", "buoi_hoc__khoa_hoc")
            .order_by("buoi_hoc__hoc_vien__ho_ten", "buoi_hoc__bat_dau"))


def _theo_hoc_vien(ds):
    return [(hv, list(nhom)) for hv, nhom in groupby(ds, key=lambda t: t.buoi_hoc.hoc_vien)]


@vai_tro_required(GIA_SU)
def thu_nhap(request):
    """Gia sư – Thu nhập theo tháng (SD-29)."""
    ctx = dv.thu_nhap_gia_su(request.user, _thang(request))
    ho_so = getattr(request.user, "ho_so_gia_su", None)
    ctx["lien_he"] = getattr(ho_so, "nguoi_moi", None)
    # Dải 4 bước: bước hiện tại là bước tiếp theo cần làm.
    hien_tai = {"DANG_MO": 0, "DA_KIEM_TRA": 2, "DA_CHOT": 3, "DA_CHI_TRA": 4}.get(ctx["trang_thai_thang"], 0)
    ds = ctx["doi_soat"]
    buoc = [("Ghi nhận buổi dạy", "Đang diễn ra trong tháng" if hien_tai == 0 else "Đã khóa số buổi"),
            ("Tuyển sinh kiểm tra", f"{ds.kiem_tra_luc:%d/%m}" if ds and ds.kiem_tra_luc else "Đầu tháng sau"),
            ("Quản trị viên chốt", f"{ds.chot_luc:%d/%m}" if ds and ds.chot_luc else "Sau khi kiểm tra"),
            ("Chi trả", f"{ds.chi_tra_luc:%d/%m}" if ds and ds.chi_tra_luc else "Sau khi chốt")]
    ctx["buoc_tn"] = [{"ten": t, "phu": p, "lop": "xong" if i < hien_tai else ("dang" if i == hien_tai else "")}
                      for i, (t, p) in enumerate(buoc)]
    return render(request, "core/thu_lao/thu_nhap.html", ctx)


@vai_tro_required(ADMIN, TUYEN_SINH)
def doi_soat(request):
    """Tài chính › Đối soát thù lao (SD-30/31): Tuyển sinh kiểm tra từng gia sư, QTV chốt tháng và đánh dấu chi trả."""
    from core.models import MonGiaSu
    thang = _thang(request)
    bang = dv.tong_hop(thang)
    tl = {}
    for t in (ThuLao.objects.filter(thang=thang).select_related("buoi_hoc__hoc_vien", "buoi_hoc__yeu_cau__mon_hoc",
                                                                  "buoi_hoc__khoa_hoc").order_by("buoi_hoc__bat_dau")):
        tl.setdefault(t.gia_su_id, []).append(t)
    mon = {}
    for m in MonGiaSu.objects.filter(trang_thai=MonGiaSu.TrangThai.DA_DUYET).select_related("mon_hoc", "ho_so"):
        mon.setdefault(m.ho_so.user_id, []).append(str(m.mon_hoc))
    for d in bang:
        d.ds_buoi = tl.get(d.gia_su.pk, [])
        d.mon = " · ".join(mon.get(d.gia_su.pk, [])[:3])
    nay = dv.dau_thang()
    ds_thang = []
    t = dv.dau_thang(nay - timedelta(days=62))
    while t <= nay:
        ds_thang.append({"thang": t, "tt": dv.trang_thai_ca_thang(t)})
        t = dv.thang_sau(t)
    so_kt = sum(1 for d in bang if d.trang_thai in ("DA_KIEM_TRA", "DA_CHOT", "DA_CHI_TRA"))
    tt = dv.trang_thai_ca_thang(thang)
    ngay_tra = dv.thang_sau(thang).replace(day=5)
    return render(request, "core/thu_lao/doi_soat.html", {
        "thang": thang, "bang": bang, "tong_ca_thang": sum(d.tong for d in bang), "ds_thang": ds_thang,
        "so_buoi": sum(d.so_buoi for d in bang), "so_giu": sum(d.so_tam_giu for d in bang),
        "tong_dc": sum(d.dieu_chinh for d in bang), "so_kt": so_kt, "so_gs": len(bang),
        "pt_kt": round(so_kt * 100 / len(bang)) if bang else 0, "tt_thang": tt, "ngay_tra": ngay_tra,
        "chot_duoc": request.user.la_admin and bang and tt == "DA_KIEM_TRA",
        "chi_tra_duoc": request.user.la_admin and tt == "DA_CHOT",
        "thang_truoc": dv.dau_thang(thang - timedelta(days=1)), "thang_sau": dv.thang_sau(thang),
    })


@vai_tro_required(ADMIN)
@require_POST
def chot_thang(request):
    thang = _thang(request)
    try:
        da, bo = dv.chot_thang(request.user, thang)
        messages.success(request, f"Đã chốt thù lao tháng {thang:%m/%Y} · {len(da)} gia sư · "
                         + f"{sum(d.tong for d in da):,}đ".replace(",", "."))
        for gs, ly_do in bo:
            messages.error(request, f"Bỏ qua {gs.ho_ten}: {ly_do}")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return _ve_doi_soat(thang)


@vai_tro_required(ADMIN)
@require_POST
def chi_tra(request):
    thang = _thang(request)
    try:
        n = dv.danh_dau_chi_tra(request.user, thang, request.POST.get("chung_tu", ""))
        messages.success(request, f"Đã đánh dấu chi trả thù lao tháng {thang:%m/%Y} cho {n} gia sư.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return _ve_doi_soat(thang)


@vai_tro_required(ADMIN, TUYEN_SINH)
def doi_soat_gia_su(request, pk):
    """Chi tiết từng gia sư nay nằm trong dòng mở rộng của trang Đối soát."""
    get_object_or_404(User, pk=pk, vai_tro=User.VaiTro.GIA_SU)
    return redirect(f"{reverse('doi_soat')}?thang={_thang(request):%Y-%m}")


def _ve_doi_soat(thang, pk=None):
    return redirect(f"{reverse('doi_soat')}?thang={thang:%Y-%m}")


@vai_tro_required(ADMIN, TUYEN_SINH)
@require_POST
def them_dieu_chinh(request, pk):
    gs = get_object_or_404(User, pk=pk, vai_tro=User.VaiTro.GIA_SU)
    thang = _thang(request)
    try:
        so = int((request.POST.get("so_tien") or "0").replace(".", "").replace(",", ""))
        dv.them_dieu_chinh(request.user, gs, thang, so, request.POST.get("ly_do", ""))
        messages.success(request, "Đã thêm khoản điều chỉnh. Cần kiểm tra lại tháng này trước khi chốt.")
    except ValueError:
        messages.error(request, "Số tiền không hợp lệ (nhập số, âm để trừ).")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return _ve_doi_soat(thang, pk)


@vai_tro_required(TUYEN_SINH)
@require_POST
def kiem_tra(request, pk):
    gs = get_object_or_404(User, pk=pk, vai_tro=User.VaiTro.GIA_SU)
    thang = _thang(request)
    try:
        dv.kiem_tra(request.user, gs, thang)
        messages.success(request, f"Đã kiểm tra thù lao {thang:%m/%Y} của {gs.ho_ten}. Chờ Admin chốt.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return _ve_doi_soat(thang)


@vai_tro_required(ADMIN)
@require_POST
def chot(request, pk):
    gs = get_object_or_404(User, pk=pk, vai_tro=User.VaiTro.GIA_SU)
    thang = _thang(request)
    try:
        dv.chot(request.user, gs, thang)
        messages.success(request, f"Đã chốt thù lao {thang:%m/%Y} của {gs.ho_ten}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return _ve_doi_soat(thang)


@vai_tro_required(ADMIN, TUYEN_SINH)
def xuat_csv(request):
    thang = _thang(request)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="thu-lao-{thang:%Y-%m}.csv"'
    resp.write("﻿")  # BOM để Excel đọc đúng tiếng Việt
    w = csv.writer(resp)
    w.writerow(["Gia sư", "Email", "Số buổi", "Tạm tính", "Đã đối soát", "Tạm giữ", "Điều chỉnh", "Tổng", "Trạng thái"])
    nhan = {"DA_CHI_TRA": "Đã chi trả", "DA_CHOT": "Đã chốt", "DA_KIEM_TRA": "Tuyển sinh đã kiểm tra", "CAN_KIEM_TRA_LAI": "Cần kiểm tra lại",
            "CHUA_KIEM_TRA": "Chưa kiểm tra"}
    for d in dv.tong_hop(thang):
        w.writerow([d.gia_su.ho_ten, d.gia_su.email, d.so_buoi, d.tam_tinh, d.da_doi_soat, d.tam_giu, d.dieu_chinh,
                    d.tong, nhan[d.trang_thai]])
    return resp
