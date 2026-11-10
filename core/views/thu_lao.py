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
    thang = _thang(request)
    tong = (dv.tong_hop(thang, request.user) or [dv.DongTong(gia_su=request.user)])[0]
    return render(request, "core/thu_lao/thu_nhap.html", {
        "thang": thang, "thang_truoc": dv.dau_thang(thang - timedelta(days=1)),
        "thang_sau": dv.thang_sau(thang), "tong": tong,
        "nhom": _theo_hoc_vien(_thu_lao_trong_thang(request.user, thang)),
    })


@vai_tro_required(ADMIN, TUYEN_SINH)
def doi_soat(request):
    thang = _thang(request)
    bang = dv.tong_hop(thang)
    return render(request, "core/thu_lao/doi_soat.html", {
        "thang": thang, "bang": bang, "tong_ca_thang": sum(d.tong for d in bang),
        "thang_truoc": dv.dau_thang(thang - timedelta(days=1)), "thang_sau": dv.thang_sau(thang),
    })


@vai_tro_required(ADMIN, TUYEN_SINH)
def doi_soat_gia_su(request, pk):
    gs = get_object_or_404(User, pk=pk, vai_tro=User.VaiTro.GIA_SU)
    thang = _thang(request)
    tong = (dv.tong_hop(thang, gs) or [dv.DongTong(gia_su=gs)])[0]
    return render(request, "core/thu_lao/doi_soat_gia_su.html", {
        "gs": gs, "thang": thang, "tong": tong,
        "nhom": _theo_hoc_vien(_thu_lao_trong_thang(gs, thang)),
    })


def _ve_doi_soat(thang, pk=None):
    url = reverse("doi_soat_gia_su", args=[pk]) if pk else reverse("doi_soat")
    return redirect(f"{url}?thang={thang:%Y-%m}")


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
    nhan = {"DA_CHOT": "Đã chốt", "DA_KIEM_TRA": "Tuyển sinh đã kiểm tra", "CAN_KIEM_TRA_LAI": "Cần kiểm tra lại",
            "CHUA_KIEM_TRA": "Chưa kiểm tra"}
    for d in dv.tong_hop(thang):
        w.writerow([d.gia_su.ho_ten, d.gia_su.email, d.so_buoi, d.tam_tinh, d.da_doi_soat, d.tam_giu, d.dieu_chinh,
                    d.tong, nhan[d.trang_thai]])
    return resp
