"""Phần 5 – Buổi học của gia sư (DFD 5.0): tạo buổi + Zoom, hủy / dời lịch, xác nhận hoàn tất.

Quyền: chỉ gia sư, và chỉ buổi học của chính mình (buổi của người khác → 404).
"""

from datetime import timedelta

from django.conf import settings

from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import DoiLichForm, HuyBuoiForm, LocBuoiForm, TaoBuoiForm, XacNhanBuoiForm
from core.models import BuoiHoc, KhoaHoc, YeuCauHocTap
from core.permissions import GIA_SU, vai_tro_required
from core.services import buoi_hoc as dv
from core.services.tien_ich import thong_diep_loi as _loi

TT = BuoiHoc.TrangThai


def _buoi_cua_toi(request, pk):
    return get_object_or_404(
        BuoiHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc", "gia_su"),
        pk=pk, gia_su=request.user)


@vai_tro_required(GIA_SU)
def danh_sach(request):
    dv.quet_han()
    u = request.user
    form = LocBuoiForm(request.GET or None)
    thang = timezone.localdate().replace(day=1)
    trang_thai = ""
    if form.is_valid():
        thang = form.cleaned_data["thang"] or thang
        trang_thai = form.cleaned_data["trang_thai"]
    elif not request.GET:
        form = LocBuoiForm(initial={"thang": thang})
    den = date(thang.year + (thang.month == 12), thang.month % 12 + 1, 1)
    goc = BuoiHoc.objects.filter(gia_su=u).select_related("hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc")
    trong_thang = goc.filter(bat_dau__date__gte=thang, bat_dau__date__lt=den).order_by("bat_dau")
    if trang_thai:
        trong_thang = trong_thang.filter(trang_thai=trang_thai)
    now = timezone.now()
    cho_xac_nhan = [b for b in goc.filter(trang_thai=TT.DA_LEN_LICH, bat_dau__lte=now).order_by("bat_dau")
                    if b.cho_xac_nhan]
    return render(request, "core/buoi_hoc/danh_sach.html", {
        "form": form, "thang": thang,
        "ds": [{"b": b, "nhan": dv.nhan_buoi(b), "tt": b.trang_thai_hien_thi} for b in trong_thang],
        "thang_truoc": (thang - timedelta(days=1)).replace(day=1), "thang_sau": den, "trang_thai": trang_thai,
        "ds_trang_thai": BuoiHoc.TrangThai.choices,
        "cho_xac_nhan": cho_xac_nhan,
        "sap_toi": goc.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=now).order_by("bat_dau")[:10],
        "co_lop": bool(dv.khoa_co_the_xep(u) or dv.yeu_cau_co_the_hoc_thu(u)),
    })


def lay_lop(user, ma):
    """"k-5" → KhoaHoc của gia sư; "t-7" → YeuCauHocTap (học thử) của gia sư. Không phải của mình → 404."""
    loai, _, pk = (ma or "").partition("-")
    if loai == "k":
        return get_object_or_404(KhoaHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc"), pk=pk, gia_su=user)
    return get_object_or_404(YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc"), pk=pk, gia_su=user)


def lay_buoi_bu(user, lop, pk):
    if not pk:
        return None
    return get_object_or_404(BuoiHoc, pk=pk, gia_su=user)


@vai_tro_required(GIA_SU)
def tao(request):
    """Gia sư – Tạo buổi học v2 (SD-13): một hoặc nhiều buổi lặp tuần, học bù, kết quả từng buổi."""
    import json
    from core.services.trang_chu import MAU_LOP
    u = request.user
    form = TaoBuoiForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lop = lay_lop(u, form.cleaned_data["lop"])
        try:
            kq = dv.tao_nhieu_buoi(u, lop, form.ke_hoach(), lay_buoi_bu(u, lop, form.cleaned_data["hoc_bu_cho"]),
                                   form.cleaned_data.get("thoi_luong"))
        except ValidationError as e:
            form.add_error(None, e)
        else:
            tao_duoc = [x["buoi"].pk for x in kq if x["buoi"]]
            for x in kq:
                if not x["buoi"]:
                    messages.warning(request, f"Không tạo buổi {timezone.localtime(x['bat_dau']):%H:%M %d/%m}: {x['loi']}")
            if tao_duoc:
                return redirect(f"{reverse('buoi_tao')}?da_tao={','.join(map(str, tao_duoc))}")

    # Kết quả sau khi tạo
    da_tao = []
    if request.GET.get("da_tao"):
        ids = [int(x) for x in request.GET["da_tao"].split(",") if x.isdigit()][:20]
        for b in BuoiHoc.objects.filter(pk__in=ids, gia_su=u).select_related(
                "hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc", "tai_khoan_zoom").order_by("bat_dau"):
            da_tao.append({"b": b, "nhan": dv.nhan_buoi(b), "link_lop": dv.link_lop(b, request),
                           "tin_nhan": dv.noi_dung_moi_vao_lop(b, request),
                           "mo_luc": dv.gio_mo_phong(b), "dong_luc": dv.gio_dong_phong(b)})

    now = timezone.now()
    ds_lop, bu, lich_co_dinh = [], {}, {}
    for i, k in enumerate(KhoaHoc.objects.filter(gia_su=u, trang_thai=KhoaHoc.TrangThai.DANG_HOC)
                          .select_related("hoc_vien", "yeu_cau__mon_hoc").order_by("pk")):
        m = MAU_LOP[i % len(MAU_LOP)]
        xep = k.so_buoi_dang_len_lich
        ds_lop.append({"ma": f"k-{k.pk}", "loai": "khoa", "tieu_de": str(k.yeu_cau.mon_hoc), "ma_hien": k.ma,
                       "phu": f"{k.hoc_vien.ho_ten} · {k.thoi_luong_phut} phút/buổi", "chu_tat": k.hoc_vien.ho_ten,
                       "mau": m, "da": k.so_buoi_da_dung, "tong": k.so_buoi_dang_ky, "con_xep": k.so_buoi_co_the_xep,
                       "w_da": round(k.so_buoi_da_dung * 100 / k.so_buoi_dang_ky),
                       "w_xep": round(xep * 100 / k.so_buoi_dang_ky), "thoi_luong": k.thoi_luong_phut,
                       "lich": ", ".join(f"{['T2','T3','T4','T5','T6','T7','CN'][int(x['thu'])]} {x['gio']}"
                                         for x in (k.lich_co_dinh or []) if "thu" in x and "gio" in x)})
        lich_co_dinh[f"k-{k.pk}"] = k.lich_co_dinh or []
        bu[f"k-{k.pk}"] = [{"pk": b.pk, "nhan": f"{b.ma} · {timezone.localtime(b.bat_dau):%H:%M %d/%m} · {b.get_ly_do_huy_display()}"}
                           for b in k.buoi_hoc.filter(trang_thai=TT.DA_HUY, ly_do_huy__in=dv.LY_DO_GIA_SU_CHON,
                                                       buoi_hoc_bu__isnull=True).order_by("-bat_dau")[:10]]
    for y in dv.yeu_cau_co_the_hoc_thu(u):
        ds_lop.append({"ma": f"t-{y.pk}", "loai": "thu", "tieu_de": str(y.mon_hoc), "ma_hien": y.ma,
                       "phu": f"{y.hoc_vien.ho_ten} · Học thử", "chu_tat": y.hoc_vien.ho_ten,
                       "mau": ("#FF7A59", "#FFF1EA", "#C2410C"), "lich": y.lich_mong_muon, "thoi_luong": 90})
    chon = request.POST.get("lop") or (f"k-{request.GET['khoa']}" if request.GET.get("khoa") else
                                       f"t-{request.GET['yeu_cau']}" if request.GET.get("yeu_cau") else
                                       f"t-{request.GET['yc']}" if request.GET.get("yc") else "")
    # Chấm lịch: buổi đã có của gia sư trong 9 tuần tới
    mau_lop = {x["ma"]: x["mau"][0] for x in ds_lop}
    cham = {}
    for b in BuoiHoc.objects.filter(gia_su=u, trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO + [TT.HOAN_TAT],
                                    bat_dau__gte=now - timedelta(days=7), bat_dau__lte=now + timedelta(days=63)):
        d = f"{timezone.localtime(b.bat_dau):%Y-%m-%d}"
        m = mau_lop.get(f"k-{b.khoa_hoc_id}" if b.khoa_hoc_id else f"t-{b.yeu_cau_id}", "#9AA1B8")
        if m not in cham.setdefault(d, []):
            cham[d].append(m)
    return render(request, "core/buoi_hoc/tao.html", {
        "form": form, "ds_lop": ds_lop, "chon": chon, "da_tao": da_tao,
        "du_lieu_js": json.dumps({"bu": bu, "lich": lich_co_dinh, "cham": cham,
                                  "hom_nay": f"{timezone.localdate():%Y-%m-%d}",
                                  "thoi_luong": {x["ma"]: x["thoi_luong"] for x in ds_lop},
                                  "con_xep": {x["ma"]: x.get("con_xep", 1) for x in ds_lop},
                                  "toi_da": settings.NGHIEP_VU.get("SO_BUOI_TAO_TOI_DA_MOT_LAN", 8)}),
    })


def _ngu_canh_chi_tiet(request, buoi, form=None):
    """Dữ liệu trang Chi tiết buổi học v2 (SD-14..SD-19)."""
    from core.models import NhatKy, NhatKyGuiTin, YeuCauXuLy
    now = timezone.now()
    nhap = getattr(buoi, "ban_nhap", None) if buoi.trang_thai == TT.DA_LEN_LICH else None
    if form is None and buoi.cho_xac_nhan:
        form = XacNhanBuoiForm(initial={"gui_zalo_phu_huynh": True, **(nhap.du_lieu if nhap else {})})
        if nhap and nhap.du_lieu.get("gui_zalo_phu_huynh") in ("false", "0", ""):
            form.initial["gui_zalo_phu_huynh"] = False
    hau_kiem = getattr(buoi, "hau_kiem", None)
    thu_lao = getattr(buoi, "thu_lao", None)
    truoc = None
    if buoi.khoa_hoc_id:
        truoc = buoi.khoa_hoc.buoi_hoc.filter(trang_thai=TT.HOAN_TAT, bat_dau__lt=buoi.bat_dau).order_by("-bat_dau").first()
    nhat_ky = [{"luc": x.thoi_diem, "chu": x.hanh_dong + (f": {x.chi_tiet[:80]}" if x.chi_tiet and len(x.chi_tiet) < 120 else ""),
                "ai": x.nguoi_thuc_hien.ho_ten if x.nguoi_thuc_hien else "Hệ thống"}
               for x in NhatKy.objects.filter(ma_doi_tuong=buoi.ma).select_related("nguoi_thuc_hien").order_by("thoi_diem")]
    nhat_ky += [{"luc": t.thoi_diem, "chu": f"{'Gửi Zalo phụ huynh' if t.kenh == 'ZALO' else 'Email'}: {t.tieu_de}"
                 + ("" if t.thanh_cong else " (lỗi)"), "ai": "Hệ thống"}
                for t in NhatKyGuiTin.objects.filter(buoi_hoc=buoi)]
    if buoi.phong_mo_luc:
        nhat_ky.append({"luc": buoi.phong_mo_luc, "chu": "Zoom mở phòng", "ai": "Hệ thống"})
    if buoi.phong_dong_luc:
        nhat_ky.append({"luc": buoi.phong_dong_luc, "chu": "Buổi học kết thúc, Zoom đóng phòng", "ai": "Hệ thống"})
    nhat_ky.sort(key=lambda x: x["luc"])
    sap = []
    if buoi.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO:
        if buoi.bat_dau > now:
            sap.append({"chu": f"Zoom mở phòng (trước {settings.NGHIEP_VU.get('MO_PHONG_TRUOC_PHUT', 10)} phút)",
                        "luc": dv.gio_mo_phong(buoi)})
        sap.append({"chu": "Đánh giá và xác nhận hoàn tất", "luc": buoi.han_xac_nhan, "han": True})
        sap.append({"chu": "Gửi nhận xét cho phụ huynh qua Zalo", "luc": None, "goi_y": "Ngay sau khi bạn xác nhận"})
        sap.append({"chu": "Hậu kiểm Zoom và tính thù lao", "luc": None, "goi_y": "Tuyển sinh phụ trách kiểm tra"})
    yc_xl = YeuCauXuLy.objects.filter(buoi_hoc=buoi).order_by("-tao_luc").first()
    tt_hien = buoi.trang_thai_hien_thi
    return {
        "buoi": buoi, "TT": TT, "form_xac_nhan": form, "nhap": nhap, "tt_hien": tt_hien, "now": now,
        "form_huy": HuyBuoiForm(), "form_doi_lich": DoiLichForm(),
        "co_the_doi": buoi.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO and buoi.bat_dau > now,
        "nhan": dv.nhan_buoi(buoi), "link_lop": dv.link_lop(buoi, request),
        "tin_nhan_lop": dv.noi_dung_moi_vao_lop(buoi, request) if buoi.zoom_meeting_id else "",
        "mo_luc": dv.gio_mo_phong(buoi), "dong_luc": dv.gio_dong_phong(buoi),
        "da_mo_phong": dv.gio_mo_phong(buoi) <= now <= dv.gio_dong_phong(buoi),
        "noi_dung_phu_huynh": dv.noi_dung_gui_phu_huynh(buoi) if buoi.xac_nhan_luc else "",
        "hau_kiem": hau_kiem, "thu_lao": thu_lao, "truoc": truoc, "nhat_ky": nhat_ky, "sap": sap,
        "yc_xl": yc_xl, "co_the_xin_mo_lai": buoi.tu_huy and buoi.han_xac_nhan and
        buoi.han_xac_nhan + timedelta(days=settings.NGHIEP_VU["NGAY_MO_LAI_TOI_DA"]) >= now
        and not (yc_xl and yc_xl.loai == "MO_LAI" and yc_xl.trang_thai == "CHO_XU_LY"),
        "han_mo_lai": buoi.han_xac_nhan + timedelta(days=settings.NGHIEP_VU["NGAY_MO_LAI_TOI_DA"]) if buoi.han_xac_nhan else None,
        "toi_thieu": settings.NGHIEP_VU.get("DO_DAI_NHAN_XET_TOI_THIEU", 30),
        "ho_so_moi": getattr(getattr(buoi.gia_su, "ho_so_gia_su", None), "nguoi_moi", None),
    }


@vai_tro_required(GIA_SU)
def chi_tiet(request, pk):
    dv.quet_han()
    buoi = _buoi_cua_toi(request, pk)
    return render(request, "core/buoi_hoc/chi_tiet.html", _ngu_canh_chi_tiet(request, buoi))


@vai_tro_required(GIA_SU)
@require_POST
def xin_mo_lai(request, pk):
    from core.models import YeuCauXuLy
    from core.services.ngoai_le import gui_yeu_cau_xu_ly
    buoi = _buoi_cua_toi(request, pk)
    try:
        yc = gui_yeu_cau_xu_ly(request.user, buoi, YeuCauXuLy.Loai.MO_LAI, request.POST.get("noi_dung", ""),
                               request.POST.get("minh_chung_url", ""))
        messages.success(request, f"Đã gửi yêu cầu mở lại. Quản trị viên sẽ xem xét trước "
                                  f"{timezone.localtime(yc.han_xu_ly):%H:%M %d/%m}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def bao_su_co(request, pk):
    from core.models import YeuCauXuLy
    from core.services.ngoai_le import gui_yeu_cau_xu_ly
    buoi = _buoi_cua_toi(request, pk)
    loai = request.POST.get("loai") if request.POST.get("loai") in ("SU_CO_ZOOM", "LOI_HE_THONG") else "SU_CO_ZOOM"
    try:
        gui_yeu_cau_xu_ly(request.user, buoi, loai, request.POST.get("noi_dung", ""))
        messages.success(request, "Đã báo sự cố cho Quản trị viên. Bạn sẽ nhận thông báo khi có kết quả.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
def mo_phong(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    try:
        return redirect(dv.lay_link_mo_phong(request.user, buoi))
    except ValidationError as e:
        messages.error(request, _loi(e))
        return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def thu_lai_zoom(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    try:
        if dv.thu_lai_zoom(request.user, buoi):
            messages.success(request, "Đã tạo phòng Zoom.")
        else:
            messages.error(request, "Zoom vẫn chưa phản hồi. Thử lại sau ít phút.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    tiep = request.POST.get("tiep", "")
    if tiep.startswith("/") and not tiep.startswith("//"):
        return redirect(tiep)
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def huy(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = HuyBuoiForm(request.POST)
    if form.is_valid():
        try:
            dv.huy_buoi(request.user, buoi, form.cleaned_data["ly_do_huy"], form.cleaned_data["ghi_chu"])
            messages.success(request, "Đã hủy buổi học và xóa phòng Zoom. Nhớ báo phụ huynh qua Zalo.")
        except ValidationError as e:
            messages.error(request, _loi(e))
    else:
        messages.error(request, "Vui lòng chọn lý do hủy.")
    return redirect("buoi_chi_tiet", pk=pk)


@vai_tro_required(GIA_SU)
@require_POST
def doi_lich(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = DoiLichForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Giờ mới không hợp lệ.")
        return redirect("buoi_chi_tiet", pk=pk)
    try:
        moi = dv.doi_lich(request.user, buoi, form.cleaned_data["bat_dau"])
    except ValidationError as e:
        messages.error(request, _loi(e))
        return redirect("buoi_chi_tiet", pk=pk)
    messages.success(request, "Đã dời lịch: buổi cũ đã hủy, buổi mới có phòng Zoom mới. Gửi lại link cho học viên.")
    return redirect("buoi_chi_tiet", pk=moi.pk)


@vai_tro_required(GIA_SU)
@require_POST
def xac_nhan(request, pk):
    buoi = _buoi_cua_toi(request, pk)
    form = XacNhanBuoiForm(request.POST)
    if form.is_valid():
        try:
            buoi = dv.xac_nhan_hoan_tat(request.user, buoi, form.cleaned_data)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                for k, v in e.error_dict.items():
                    form.add_error(k if k in form.fields else None, v)
            else:
                messages.error(request, _loi(e))
                return redirect("buoi_chi_tiet", pk=pk)
        else:
            if not form.cleaned_data.get("gui_zalo_phu_huynh"):
                messages.success(request, f"Đã xác nhận hoàn tất lúc {timezone.localtime(buoi.xac_nhan_luc):%H:%M}. "
                                          "Bạn đã tắt gửi Zalo – hãy sao chép nhận xét gửi phụ huynh.")
            elif buoi.zalo_trang_thai == BuoiHoc.GuiZalo.DA_GUI:
                messages.success(request, "Đã xác nhận hoàn tất. Đánh giá đã được gửi cho phụ huynh qua Zalo.")
            else:
                messages.warning(request, "Đã xác nhận hoàn tất, nhưng chưa gửi được Zalo. "
                                          "Bấm Gửi lại hoặc sao chép nhận xét gửi phụ huynh.")
            return redirect("buoi_chi_tiet", pk=pk)
    # Form lỗi: hiển thị lại trang với lỗi tại từng ô (bản nháp vẫn giữ).
    return render(request, "core/buoi_hoc/chi_tiet.html", _ngu_canh_chi_tiet(request, buoi, form), status=400)


def vao_lop(request, ma_lop):
    """Link lớp cố định gửi trong nhóm Zalo (SD-14, công khai): trong cửa sổ giờ học → chuyển vào Zoom."""
    from django.http import HttpResponseRedirect
    dang, sap = dv.buoi_dang_mo(ma_lop)
    if dang:
        return HttpResponseRedirect(dang.zoom_join_url)
    mo_luc = (sap.bat_dau - timedelta(minutes=settings.NGHIEP_VU.get("MO_PHONG_TRUOC_PHUT", 10))) if sap else None
    return render(request, "core/buoi_hoc/vao_lop.html", {"ma_lop": ma_lop.upper(), "sap": sap, "mo_luc": mo_luc})
