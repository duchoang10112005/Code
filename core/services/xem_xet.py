"""Quản trị viên › Cần xem xét (SD-32..34): hàng đợi hợp nhất và các thao tác xử lý.

QTV không hậu kiểm buổi học (Q1). Phạm vi: xin mở lại / buổi tự hủy, lỗi hệ thống, sự cố Zoom,
duyệt đổi gia sư lần ≥ 2, hồ sơ gia sư mới, môn dạy chờ duyệt. Trang chủ QTV thêm: yêu cầu chờ quá 24 giờ,
thù lao chờ chốt.
"""

import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from core.models import (BanNhapDanhGia, BuoiHoc, DoiGiaSu, DoiSoatThang, HoSoGiaSu, MonGiaSu, SuCoHeThong, User,
                         YeuCauXuLy)
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email, thong_bao
from core.services.tim_kiem import chuan_hoa

NV = settings.NGHIEP_VU
TT = BuoiHoc.TrangThai
XL = YeuCauXuLy.TrangThai

TAB = [("", "Tất cả"), ("mo_lai", "Mở lại buổi"), ("loi", "Lỗi hệ thống"), ("doi_gia_su", "Đổi gia sư"),
       ("ho_so", "Hồ sơ & môn")]
# loai → (nhãn, icon, màu chữ, nền icon, tab)
KIEU = {
    "mo_lai": ("Xin mở lại buổi", "bi-hourglass-split", "#C2410C", "#FFF4E5", "mo_lai"),
    "tu_huy": ("Buổi tự hủy", "bi-hourglass-bottom", "#646B85", "#F1F3F8", "mo_lai"),
    "loi_he_thong": ("Lỗi hệ thống", "bi-cpu", "#C2292E", "#FDECEC", "loi"),
    "su_co_zoom": ("Lỗi Zoom", "bi-camera-video-off", "#C2292E", "#FDECEC", "loi"),
    "doi_gia_su": ("Đổi gia sư", "bi-arrow-repeat", "#4F46E5", "#EEF0FF", "doi_gia_su"),
    "ho_so": ("Hồ sơ gia sư mới", "bi-person", "#4F46E5", "#EEF0FF", "ho_so"),
    "mon": ("Môn dạy chờ duyệt", "bi-journal-check", "#4F46E5", "#EEF0FF", "ho_so"),
}


def _cho(luc, now):
    s = (now - luc).total_seconds()
    if s < 3600:
        return f"Chờ {max(int(s // 60), 1)} phút"
    if s < 86400:
        return f"Chờ {int(s // 3600)} giờ"
    return f"Chờ {int(s // 86400)} ngày"


def _buoi_tieu_de(b):
    return f"{b.yeu_cau.mon_hoc} · {b.hoc_vien.ho_ten} · {timezone.localtime(b.bat_dau):%d/%m}"


def _muc(loai, pk, ma, tieu_de, mo_ta, luc, now, han=None, obj=None, buoi=None, **them):
    k = KIEU[loai]
    return {"loai": loai, "key": f"{loai}-{pk}", "ma": ma, "tieu_de": tieu_de, "mo_ta": mo_ta, "luc": luc,
            "cho": _cho(luc, now), "han": han, "obj": obj, "buoi": buoi, "nhan": k[0], "icon": k[1], "mau": k[2],
            "nen": k[3], "tab": k[4], **them}


def tat_ca(now=None):
    """Mọi mục đang chờ QTV, sắp theo hạn gần nhất rồi thời gian chờ."""
    now = now or timezone.now()
    ds = []
    yc = (YeuCauXuLy.objects.filter(trang_thai__in=[XL.CHO_XU_LY, XL.CHUYEN_KY_THUAT])
          .select_related("buoi_hoc__gia_su", "buoi_hoc__hoc_vien", "buoi_hoc__yeu_cau__mon_hoc",
                          "buoi_hoc__khoa_hoc", "nguoi_gui", "su_co"))
    co_yc = set()
    for y in yc:
        b = y.buoi_hoc
        if b:
            co_yc.add(b.pk)
        loai = {"MO_LAI": "mo_lai", "LOI_HE_THONG": "loi_he_thong", "SU_CO_ZOOM": "su_co_zoom"}[y.loai]
        mo_ta = (f"{b.ma} · " if b else "") + (f"{y.nguoi_gui.ho_ten}: " if y.nguoi_gui else "") + (y.noi_dung or "")
        ds.append(_muc(loai, y.pk, b.ma if b else f"SC-{y.su_co_id or y.pk}", _buoi_tieu_de(b) if b else "Lỗi hệ thống",
                       mo_ta, y.tao_luc, now, y.han_xu_ly, y, b, ky_thuat=y.trang_thai == XL.CHUYEN_KY_THUAT))
    tu = now - timedelta(days=NV["NGAY_MO_LAI_TOI_DA"])
    for b in (BuoiHoc.objects.filter(trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN, han_xac_nhan__gte=tu)
              .exclude(pk__in=co_yc).select_related("gia_su", "hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc")):
        ds.append(_muc("tu_huy", b.pk, b.ma, _buoi_tieu_de(b),
                       f"{b.ma} · Tự hủy do quá 12 giờ chưa xác nhận · gia sư {b.gia_su.ho_ten}",
                       b.han_xac_nhan, now, b.han_xac_nhan + timedelta(days=NV["NGAY_MO_LAI_TOI_DA"]), b, b))
    for d in DoiGiaSu.objects.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET).select_related(
            "khoa_hoc__hoc_vien", "khoa_hoc__yeu_cau__mon_hoc", "gia_su_cu", "gia_su_moi", "tao_boi"):
        k = d.khoa_hoc
        ds.append(_muc("doi_gia_su", d.pk, k.ma, f"{k.ma} · {k.yeu_cau.mon_hoc} · "
                       + (f"đổi sang {d.gia_su_moi.ho_ten}" if d.gia_su_moi else "mở lại tìm gia sư"),
                       f"Đề xuất bởi {d.tao_boi.ho_ten if d.tao_boi else '—'} · {d.get_ly_do_display()}",
                       d.tao_luc, now, obj=d))
    cho_hs = set()
    for h in HoSoGiaSu.objects.filter(trang_thai=HoSoGiaSu.TrangThai.CHO_DUYET,
                                      user__vai_tro=User.VaiTro.GIA_SU).select_related("user", "nguoi_moi"):
        mon = list(h.mon_day.filter(trang_thai=MonGiaSu.TrangThai.CHO_DUYET).select_related("mon_hoc"))
        cho_hs.add(h.pk)
        ds.append(_muc("ho_so", h.pk, "Hồ sơ", f"{h.user.ho_ten} · gia sư mới",
                       ("Đăng ký: " + ", ".join(str(m.mon_hoc) for m in mon) if mon else "Chưa đăng ký môn")
                       + (f" · {h.truong_hoc}" if h.truong_hoc else ""), h.user.date_joined, now, obj=h,
                       url=reverse("gia_su_chi_tiet", args=[h.pk])))
    for m in (MonGiaSu.objects.filter(trang_thai=MonGiaSu.TrangThai.CHO_DUYET, ho_so__user__vai_tro=User.VaiTro.GIA_SU)
              .exclude(ho_so_id__in=cho_hs).select_related("ho_so__user", "mon_hoc")):
        ds.append(_muc("mon", m.pk, "Môn dạy", f"{m.ho_so.user.ho_ten} · thêm môn {m.mon_hoc}",
                       f"{m.cap_do or 'Chưa chọn cấp độ'} · hồ sơ {m.ho_so.get_trang_thai_display().lower()}",
                       m.gui_luc or m.ho_so.user.date_joined, now, obj=m,
                       url=reverse("gia_su_chi_tiet", args=[m.ho_so_id])))
    xa = now + timedelta(days=3650)
    ds.sort(key=lambda x: (x.get("ky_thuat", False), x["han"] or xa, x["luc"]))
    return ds


_MA = re.compile(r"^(bh|kh|yc)0*(\d+)$")


def hang_doi(q="", tab=""):
    """→ (danh sách lọc, đếm theo tab, thẻ 'mã không có yêu cầu' hoặc None)."""
    ds = tat_ca()
    dem = {k: (len(ds) if not k else sum(1 for x in ds if x["tab"] == k)) for k, _ in TAB}
    loc = [x for x in ds if not tab or x["tab"] == tab]
    khong_co = None
    if q:
        g = chuan_hoa(q).replace("-", "").replace(" ", "")
        m = _MA.match(g)
        if m:
            ma = f"{m.group(1).upper()}-{int(m.group(2)):0{5 if m.group(1) == 'bh' else 4}d}"
            loc = [x for x in loc if x["ma"] == ma or (x["buoi"] and x["buoi"].ma == ma)]
            if not loc and m.group(1) == "bh":
                b = BuoiHoc.objects.filter(pk=int(m.group(2))).first()
                if b:
                    khong_co = b
        else:
            loc = [x for x in loc if g in chuan_hoa(f"{x['tieu_de']} {x['mo_ta']} {x['ma']}").replace(" ", "")]
    return loc, dem, khong_co


def tong_quan_trang_chu(now=None):
    """Nhóm ngoại lệ cho trang chủ QTV: chờ quá 24 giờ, mở lại/lỗi, chờ duyệt, thù lao chờ chốt."""
    from core.services.ngoai_le import ds_cho_lau
    now = now or timezone.now()
    ds = tat_ca(now)
    cho_lau = list(ds_cho_lau(24))
    from core.services.thu_lao import tong_hop
    thang_chot = {}
    for t in sorted(set(DoiSoatThang.objects.filter(trang_thai=DoiSoatThang.TrangThai.DA_KIEM_TRA)
                        .values_list("thang", flat=True))):
        ok = [d for d in tong_hop(t) if d.trang_thai == "DA_KIEM_TRA"]  # tổng không đổi kể từ lúc kiểm tra
        if ok:
            thang_chot[t] = ok
    return {
        "cho_lau": cho_lau,
        "mo_lai_loi": [x for x in ds if x["tab"] in ("mo_lai", "loi")],
        "cho_duyet": [x for x in ds if x["tab"] in ("doi_gia_su", "ho_so")],
        "cho_chot": [{"thang": t, "ds": v} for t, v in sorted(thang_chot.items())],
        "tong": len(ds) + len(cho_lau) + len(thang_chot),
    }


# =============================================================================
# SD-33: mở lại / từ chối
# =============================================================================
def tu_choi_mo_lai(admin, yc, ly_do):
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValidationError({"ly_do": "Ghi chú quyết định bắt buộc khi từ chối."})
    if not YeuCauXuLy.objects.filter(pk=yc.pk, trang_thai__in=[XL.CHO_XU_LY, XL.CHUYEN_KY_THUAT]).update(
            trang_thai=XL.TU_CHOI, xu_ly_boi=admin, xu_ly_luc=timezone.now(), ket_qua=ly_do[:300]):
        raise ValidationError("Yêu cầu này đã được xử lý.")
    ma = yc.buoi_hoc.ma if yc.buoi_hoc_id else ""
    ghi_nhat_ky(admin, f"Từ chối yêu cầu: {yc.get_loai_display().lower()}", ma, ly_do)
    if yc.nguoi_gui:
        thong_bao(yc.nguoi_gui, f"Yêu cầu {yc.get_loai_display().lower()} {ma} bị từ chối", ly_do[:200],
                  reverse("buoi_chi_tiet", args=[yc.buoi_hoc_id]) if yc.buoi_hoc_id else "", "BUOI_HOC")
        gui_email(yc.nguoi_gui, f"Yêu cầu {yc.get_loai_display().lower()} {ma} bị từ chối", f"Lý do: {ly_do}")


def chuyen_ky_thuat(admin, yc, ghi_chu=""):
    if not YeuCauXuLy.objects.filter(pk=yc.pk, trang_thai=XL.CHO_XU_LY).update(
            trang_thai=XL.CHUYEN_KY_THUAT, xu_ly_boi=admin, ket_qua=(ghi_chu or "Chuyển kỹ thuật")[:300]):
        raise ValidationError("Yêu cầu này đã được xử lý.")
    ghi_nhat_ky(admin, "Chuyển lỗi hệ thống cho kỹ thuật", yc.buoi_hoc.ma if yc.buoi_hoc_id else f"SC-{yc.su_co_id}",
                ghi_chu)


def _xong(admin, yc, ket_qua):
    YeuCauXuLy.objects.filter(pk=yc.pk).update(trang_thai=XL.DA_XU_LY, xu_ly_boi=admin, xu_ly_luc=timezone.now(),
                                               ket_qua=(ket_qua or "")[:300])


# =============================================================================
# SD-34: khôi phục từ bản nháp, tạo lại phòng Zoom bằng host khác
# =============================================================================
def ban_nhap_du(buoi):
    n = BanNhapDanhGia.objects.filter(buoi_hoc=buoi).first()
    if not n:
        return None
    d = n.du_lieu if isinstance(getattr(n, "du_lieu", None), dict) else {
        k: getattr(n, k, "") for k in ("noi_dung", "xep_loai", "danh_gia", "dan_do_buoi_sau")}
    return d if all((d.get(k) or "").strip() for k in ("noi_dung", "xep_loai", "danh_gia")) else None


def khoi_phuc_tu_nhap(admin, yc, ly_do):
    from core.services.buoi_hoc import xac_nhan_hoan_tat
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValidationError({"ly_do": "Ghi lý do khôi phục."})
    b = yc.buoi_hoc
    if not b:
        raise ValidationError("Sự cố này không gắn với buổi học.")
    d = ban_nhap_du(b)
    if not d:
        raise ValidationError("Bản nháp chưa đủ 3 mục bắt buộc. Hãy mở lại để gia sư tự xác nhận.")
    with transaction.atomic():
        xac_nhan_hoan_tat(b.gia_su, b, {**d, "gui_zalo_phu_huynh": True}, bo_qua_han=True, nguoi_thuc_hien=admin)
        _xong(admin, yc, f"Khôi phục từ bản nháp: {ly_do}")
    thong_bao(b.gia_su, f"Buổi {b.ma} đã được xác nhận từ bản nháp", "Quản trị viên đã khôi phục thay bạn sau lỗi hệ thống.",
              reverse("buoi_chi_tiet", args=[b.pk]), "BUOI_HOC")


def mo_lai_tu_yeu_cau(admin, yc_hoac_buoi, ly_do):
    """Mở lại buổi tự hủy (từ yêu cầu của gia sư hoặc trực tiếp). Lỗi hệ thống: gia hạn xác nhận 24 giờ."""
    from core.services import ngoai_le
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValidationError({"ly_do": "Ghi lý do mở lại."})
    if isinstance(yc_hoac_buoi, BuoiHoc):
        return ngoai_le.mo_lai(admin, yc_hoac_buoi, ly_do)
    yc, b = yc_hoac_buoi, yc_hoac_buoi.buoi_hoc
    if b.trang_thai == TT.DA_HUY and b.ly_do_huy == BuoiHoc.LyDoHuy.QUA_HAN:
        ngoai_le.mo_lai(admin, b, ly_do)
    elif b.trang_thai == TT.DA_LEN_LICH:
        han = timezone.now() + timedelta(hours=NV["GIO_XAC_NHAN_KHI_MO_LAI"])
        BuoiHoc.objects.filter(pk=b.pk).update(han_xac_nhan=han, da_nhac_han=False)
        ghi_nhat_ky(admin, "Gia hạn xác nhận sau lỗi hệ thống", b.ma, ly_do)
        thong_bao(b.gia_su, f"Buổi {b.ma}: thêm thời gian xác nhận",
                  f"Xác nhận trước {timezone.localtime(han):%H:%M %d/%m}", reverse("buoi_chi_tiet", args=[b.pk]),
                  "BUOI_HOC")
    else:
        raise ValidationError("Buổi không ở trạng thái mở lại được.")
    _xong(admin, yc, f"Mở lại: {ly_do}")


def tao_lai_zoom(admin, yc_hoac_buoi):
    from core.services.buoi_hoc import _gan_zoom, _xoa_zoom, chon_host
    yc = yc_hoac_buoi if isinstance(yc_hoac_buoi, YeuCauXuLy) else None
    b = yc.buoi_hoc if yc else yc_hoac_buoi
    if not b or b.trang_thai not in (TT.LOI_ZOOM, TT.DA_LEN_LICH) or b.bat_dau <= timezone.now():
        raise ValidationError("Chỉ tạo lại phòng cho buổi sắp diễn ra.")
    host = chon_host(b, tru=b.tai_khoan_zoom)
    _xoa_zoom(b)
    if not _gan_zoom(b, host):
        b.refresh_from_db()
        raise ValidationError(f"Zoom vẫn lỗi: {b.zoom_loi[:200]}")
    ghi_nhat_ky(admin, "Tạo lại phòng Zoom bằng host khác", b.ma, b.tai_khoan_zoom.email_host if b.tai_khoan_zoom else "")
    if yc:
        _xong(admin, yc, "Đã tạo lại phòng Zoom")
    thong_bao(b.gia_su, f"Phòng Zoom buổi {b.ma} đã được tạo lại", "Sao chép lại tin nhắn Zalo gửi phụ huynh.",
              reverse("buoi_chi_tiet", args=[b.pk]), "BUOI_HOC")


def ghi_su_co(request, exc_text):
    """Middleware gọi khi có lỗi 500: lưu sự cố; nếu đường dẫn gắn với một buổi → tạo YeuCauXuLy + gia hạn 24 giờ."""
    u = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    form = {k: ("***" if "mat_khau" in k or "password" in k else v[:300])
            for k, v in (request.POST.items() if request.method == "POST" else []) if k != "csrfmiddlewaretoken"}
    sc = SuCoHeThong.objects.create(nguoi_dung=u, duong_dan=request.path[:500], phuong_thuc=request.method,
                                    chi_tiet=exc_text[-4000:], du_lieu_form=form)
    m = re.match(r"^/buoi-hoc/(\d+)/", request.path)
    b = BuoiHoc.objects.filter(pk=int(m.group(1))).first() if m else None
    if b and u and b.gia_su_id == u.pk:
        han = (b.han_xac_nhan or timezone.now()) + timedelta(hours=24)
        YeuCauXuLy.objects.create(loai=YeuCauXuLy.Loai.LOI_HE_THONG, buoi_hoc=b, nguoi_gui=u, su_co=sc,
                                  noi_dung=f"Lỗi khi {request.method} {request.path}", han_xu_ly=b.han_xac_nhan)
        if b.trang_thai == TT.DA_LEN_LICH:
            BuoiHoc.objects.filter(pk=b.pk).update(han_xac_nhan=han)
    from core.services.thong_bao import thong_bao_quan_tri
    thong_bao_quan_tri("Lỗi hệ thống", f"{request.method} {request.path}" + (f" · {b.ma}" if b else ""),
                       reverse("xem_xet") + "?tab=loi", "XEM_XET")
    return sc
