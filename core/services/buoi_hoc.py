"""Nghiệp vụ buổi học – tiến trình 5.0 trên DFD (tạo buổi + Zoom, xác nhận, hậu kiểm, Zalo).

Backlog: PB-07 (gia sư tạo buổi học thử), PB-11..PB-15, PB-16, PB-29, PB-31, PB-32.

Vòng đời buổi học:
  tạo → LOI_ZOOM ⇄ (thử lại) → DA_LEN_LICH
  DA_LEN_LICH → HOAN_TAT        (gia sư xác nhận sau giờ kết thúc, trước hạn 12h)
  DA_LEN_LICH → DA_HUY           (gia sư hủy / dời lịch / quá hạn xác nhận → hệ thống tự hủy)
  HOAN_TAT    → DANG_XEM_XET     (hậu kiểm Zoom không đạt → thù lao tạm giữ, Admin xử lý ở Đợt B)

"Xác nhận trước, hậu kiểm sau": xác nhận không phải chờ Zoom; hậu kiểm chạy sau bằng `hau_kiem()`.
Zoom MVP: 1 tài khoản → tối đa SO_PHONG_ZOOM_DONG_THOI buổi chạy cùng lúc trên toàn trung tâm.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q as models_Q
from django.utils import timezone

from core.integrations.zalo import lay_zalo_client
from core.integrations.zoom import ZoomError, lay_zoom_client
from core.models import (BanNhapDanhGia, BuoiHoc, HauKiemBuoi, KhoaHoc, NhatKyGuiTin, TaiKhoanZoom, ThuLao,
                         YeuCauHocTap)
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email

logger = logging.getLogger(__name__)

TT = BuoiHoc.TrangThai
YC = YeuCauHocTap.TrangThai
KH = KhoaHoc.TrangThai
NV = settings.NGHIEP_VU
THOI_LUONG_HOC_THU = (60, 90, 120)


def _gio(n):
    return timedelta(hours=n)


def thoi_luong_demo():
    """Số phút của buổi học ở chế độ chạy thử (0 = tắt). Đọc lúc gọi để test bật/tắt được."""
    return settings.NGHIEP_VU.get("THOI_LUONG_BUOI_DEMO", 0)


def _cho_zoom_tong_hop():
    """Thời gian chờ Zoom tổng hợp báo cáo sau buổi học trước khi hậu kiểm."""
    return timedelta(minutes=1 if thoi_luong_demo() else 30)


# =============================================================================
# Kiểm tra khung giờ
# =============================================================================
def _buoi_trung_gio(bat_dau, ket_thuc, bo_qua_pk=None):
    """Các buổi đang giữ chỗ có khoảng thời gian giao với [bat_dau, ket_thuc)."""
    qs = BuoiHoc.objects.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__lt=ket_thuc,
                                ket_thuc_luc__gt=bat_dau)
    if bo_qua_pk:
        qs = qs.exclude(pk=bo_qua_pk)
    return list(qs.select_related("gia_su"))


def so_phong_zoom():
    """Số phòng chạy cùng lúc = số tài khoản host Zoom đang bật; chưa khai báo thì dùng tham số cũ."""
    n = TaiKhoanZoom.objects.filter(dang_bat=True).count()
    return n or NV["SO_PHONG_ZOOM_DONG_THOI"]


def _gio_muon_nhat():
    h, m = (settings.NGHIEP_VU.get("GIO_KET_THUC_MUON_NHAT") or "22:00").split(":")
    return int(h) * 60 + int(m)


def kiem_tra_khung_gio(gia_su, bat_dau, thoi_luong, bo_qua_pk=None):
    now = timezone.now()
    if bat_dau <= now:
        raise ValidationError({"bat_dau": "Giờ bắt đầu phải ở tương lai."})
    if bat_dau > now + timedelta(days=60):
        raise ValidationError({"bat_dau": "Chỉ xếp lịch trước tối đa 60 ngày."})
    ket_thuc = bat_dau + timedelta(minutes=thoi_luong)
    bd, kt = timezone.localtime(bat_dau), timezone.localtime(ket_thuc)
    if kt.date() != bd.date() or kt.hour * 60 + kt.minute > _gio_muon_nhat():
        raise ValidationError({"bat_dau": f"Buổi học phải kết thúc trước {NV.get('GIO_KET_THUC_MUON_NHAT', '22:00')} "
                                          f"(buổi này kết thúc {kt:%H:%M})."})
    trung = _buoi_trung_gio(bat_dau, ket_thuc, bo_qua_pk)
    cua_minh = [b for b in trung if b.gia_su_id == gia_su.pk]
    if cua_minh:
        b = cua_minh[0]
        raise ValidationError({"bat_dau": f"Bạn đã có buổi học {timezone.localtime(b.bat_dau):%H:%M %d/%m} trùng khung giờ này."})
    if len(trung) >= so_phong_zoom():
        raise ValidationError({"bat_dau": "Khung giờ này đã có buổi học khác dùng phòng Zoom của trung tâm. "
                                          "Vui lòng chọn giờ khác."})


def ngoai_gio_ranh(gia_su, bat_dau, thoi_luong):
    """True nếu buổi không nằm trọn trong một khung giờ rảnh đã đăng ký (chỉ cảnh báo, không chặn)."""
    ho_so = getattr(gia_su, "ho_so_gia_su", None)
    if ho_so is None:
        return False
    bd = timezone.localtime(bat_dau)
    kt = bd + timedelta(minutes=thoi_luong)
    return not ho_so.lich_ranh.filter(thu=bd.weekday(), tu_gio__lte=bd.time(), den_gio__gte=kt.time()).exists()


# =============================================================================
# Tạo buổi học + phòng Zoom
# =============================================================================
def _chu_de(buoi):
    loai = "Học thử" if buoi.loai == BuoiHoc.Loai.HOC_THU else "Buổi học"
    return f"{loai} {buoi.yeu_cau.mon_hoc} – {buoi.hoc_vien.ho_ten} – GS {buoi.gia_su.ho_ten}"


def chon_host(buoi, tru=None):
    """Tài khoản Zoom đang bật, không có buổi giao giờ. None = chưa khai báo nhóm host (dùng host mặc định);
    False = có nhóm host nhưng không còn host trống."""
    ds = TaiKhoanZoom.objects.filter(dang_bat=True)
    if tru:
        ds = ds.exclude(pk=tru.pk)
    if not ds.exists():
        return None
    ban = set(BuoiHoc.objects.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__lt=buoi.ket_thuc,
                                     ket_thuc_luc__gt=buoi.bat_dau, tai_khoan_zoom__isnull=False)
              .exclude(pk=buoi.pk).values_list("tai_khoan_zoom_id", flat=True))
    return ds.exclude(pk__in=ban).order_by("pk").first() or False


def _gan_zoom(buoi, host=None):
    """Gọi Zoom tạo phòng. Thành công → DA_LEN_LICH; lỗi → LOI_ZOOM + lưu lỗi (không ném lỗi ra ngoài)."""
    host = host if host is not None else chon_host(buoi)
    if host is False:
        buoi.trang_thai, buoi.zoom_loi = TT.LOI_ZOOM, "Không còn tài khoản Zoom trống trong khung giờ này."
        buoi.save(update_fields=["trang_thai", "zoom_loi", "cap_nhat_luc"])
        return False
    email = host.email_host if host else settings.ZOOM_HOST_EMAIL_MAC_DINH
    try:
        phong = lay_zoom_client().tao_phong(
            email, _chu_de(buoi), buoi.bat_dau, buoi.thoi_luong_phut,
            ghi_hinh=buoi.hoc_vien.dong_y_ghi_hinh)
    except ZoomError as exc:
        buoi.trang_thai, buoi.zoom_loi = TT.LOI_ZOOM, str(exc)[:1000]
        buoi.save(update_fields=["trang_thai", "zoom_loi", "cap_nhat_luc"])
        return False
    buoi.zoom_meeting_id, buoi.zoom_join_url = phong.meeting_id, phong.join_url
    buoi.zoom_start_url, buoi.zoom_passcode = phong.start_url, phong.passcode
    buoi.trang_thai, buoi.zoom_loi, buoi.tai_khoan_zoom = TT.DA_LEN_LICH, "", host or None
    buoi.save(update_fields=["zoom_meeting_id", "zoom_join_url", "zoom_start_url", "zoom_passcode",
                             "trang_thai", "zoom_loi", "tai_khoan_zoom", "cap_nhat_luc"])
    return True


def _xoa_zoom(buoi):
    if not buoi.zoom_meeting_id:
        return
    try:
        lay_zoom_client().xoa_phong(buoi.zoom_meeting_id)
    except ZoomError as exc:  # phòng Zoom thừa không ảnh hưởng nghiệp vụ, chỉ ghi lại
        logger.warning("Không xóa được phòng Zoom %s: %s", buoi.zoom_meeting_id, exc)


def khoa_co_the_xep(gia_su):
    """Khóa đang học của gia sư còn buổi để xếp lịch."""
    return [k for k in KhoaHoc.objects.filter(gia_su=gia_su, trang_thai=KH.DANG_HOC)
            .select_related("hoc_vien", "yeu_cau__mon_hoc") if k.so_buoi_co_the_xep > 0]


def yeu_cau_co_the_hoc_thu(gia_su):
    """Lớp đã nhận (DA_PHAN_CONG) chưa có buổi học thử nào đang mở/hoàn tất với gia sư này."""
    ds = YeuCauHocTap.objects.filter(gia_su=gia_su, trang_thai=YC.DA_PHAN_CONG, dang_ky_thang=False).select_related(
        "hoc_vien", "mon_hoc")
    return [y for y in ds if not y.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su)
            .exclude(trang_thai=TT.DA_HUY).exists()]


def kiem_tra_hoc_bu(lop, hoc_bu_cho):
    """Buổi được bù phải là buổi đã hủy vì gia sư / học viên nghỉ, cùng lớp, chưa được bù."""
    if hoc_bu_cho is None:
        return
    if hoc_bu_cho.trang_thai != TT.DA_HUY or hoc_bu_cho.ly_do_huy not in LY_DO_GIA_SU_CHON:
        raise ValidationError("Chỉ học bù cho buổi đã hủy vì gia sư hoặc học viên nghỉ.")
    cung_lop = (hoc_bu_cho.khoa_hoc_id == lop.pk) if isinstance(lop, KhoaHoc) else (hoc_bu_cho.yeu_cau_id == lop.pk)
    if not cung_lop:
        raise ValidationError("Buổi cần bù không thuộc lớp này.")
    if BuoiHoc.objects.filter(hoc_bu_cho=hoc_bu_cho).exclude(trang_thai=TT.DA_HUY).exists():
        raise ValidationError(f"Buổi {hoc_bu_cho.ma} đã có buổi học bù.")


def tao_buoi_chinh_thuc(gia_su, khoa, bat_dau, thay_the_cho=None, hoc_bu_cho=None):
    khoa.refresh_from_db()
    if khoa.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải khóa bạn phụ trách.")
    if khoa.trang_thai != KH.DANG_HOC:
        raise ValidationError(f"Khóa đang ở trạng thái \"{khoa.get_trang_thai_display()}\", chưa xếp lịch được.")
    if khoa.so_buoi_co_the_xep <= 0 and not thay_the_cho:
        raise ValidationError("Khóa đã xếp đủ số buổi đăng ký, không tạo thêm buổi được.")
    thoi_luong = thoi_luong_demo() or khoa.thoi_luong_phut
    kiem_tra_khung_gio(gia_su, bat_dau, thoi_luong, bo_qua_pk=getattr(thay_the_cho, "pk", None))
    kiem_tra_hoc_bu(khoa, hoc_bu_cho)
    return _tao(gia_su, BuoiHoc.Loai.CHINH_THUC, khoa.yeu_cau, bat_dau, thoi_luong,
                khoa=khoa, thu_lao=khoa.thu_lao_moi_buoi, thay_the_cho=thay_the_cho, hoc_bu_cho=hoc_bu_cho)


def tao_buoi_hoc_thu(gia_su, yc, bat_dau, thoi_luong, thay_the_cho=None):
    yc.refresh_from_db()
    if yc.gia_su_id != gia_su.pk or yc.trang_thai != YC.DA_PHAN_CONG:
        raise ValidationError("Chỉ tạo buổi học thử cho lớp bạn đã nhận và đang chờ chốt.")
    if yc.dang_ky_thang and not thay_the_cho:
        raise ValidationError("Phụ huynh đã đăng ký chính thức luôn (không học thử). Chờ Tuyển sinh mở khóa học.")
    if thoi_luong_demo():
        thoi_luong = thoi_luong_demo()
    elif thoi_luong not in THOI_LUONG_HOC_THU:
        raise ValidationError({"thoi_luong": "Thời lượng học thử không hợp lệ."})
    da_co = yc.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su).exclude(trang_thai=TT.DA_HUY)
    if thay_the_cho:
        da_co = da_co.exclude(pk=thay_the_cho.pk)
    if da_co.exists():
        raise ValidationError("Lớp này đã có buổi học thử. Muốn đổi giờ thì dùng Dời lịch.")
    kiem_tra_khung_gio(gia_su, bat_dau, thoi_luong, bo_qua_pk=getattr(thay_the_cho, "pk", None))
    return _tao(gia_su, BuoiHoc.Loai.HOC_THU, yc, bat_dau, thoi_luong, thay_the_cho=thay_the_cho)


def _tao(gia_su, loai, yc, bat_dau, thoi_luong, khoa=None, thu_lao=0, thay_the_cho=None, hoc_bu_cho=None):
    hv = yc.hoc_vien
    buoi = BuoiHoc.objects.create(
        loai=loai, khoa_hoc=khoa, yeu_cau=yc, gia_su=gia_su, hoc_vien=hv, bat_dau=bat_dau,
        thoi_luong_phut=thoi_luong, trang_thai=TT.LOI_ZOOM, thu_lao_du_kien=thu_lao,
        han_xac_nhan=bat_dau + timedelta(minutes=thoi_luong) + _gio(NV["HAN_XAC_NHAN_GIO"]),
        ban_ghi_trang_thai=BuoiHoc.BanGhi.CHO_XU_LY if hv.dong_y_ghi_hinh else BuoiHoc.BanGhi.KHONG_GHI,
        thay_the_cho=thay_the_cho, hoc_bu_cho=hoc_bu_cho,
    )
    ghi_nhat_ky(gia_su, "Tạo buổi học", buoi.ma, f"{buoi}; {thoi_luong} phút"
                + (f"; học bù cho {hoc_bu_cho.ma}" if hoc_bu_cho else ""))
    _gan_zoom(buoi)
    return buoi


def thu_lai_zoom(gia_su, buoi):
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai != TT.LOI_ZOOM:
        raise ValidationError("Buổi này không ở trạng thái lỗi Zoom.")
    if buoi.bat_dau <= timezone.now():
        raise ValidationError("Đã qua giờ bắt đầu, hãy hủy buổi này và tạo buổi mới.")
    return _gan_zoom(buoi)


def gio_mo_phong(buoi):
    return buoi.bat_dau - timedelta(minutes=NV.get("MO_PHONG_TRUOC_PHUT", 10))


def gio_dong_phong(buoi):
    return buoi.ket_thuc + timedelta(minutes=NV.get("DONG_PHONG_SAU_PHUT", 5))


def lay_link_mo_phong(gia_su, buoi):
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai != TT.DA_LEN_LICH or not buoi.zoom_meeting_id:
        raise ValidationError("Buổi học chưa có phòng Zoom.")
    now = timezone.now()
    if now < gio_mo_phong(buoi):
        raise ValidationError(f"Phòng mở lúc {timezone.localtime(gio_mo_phong(buoi)):%H:%M %d/%m} "
                              f"({NV.get('MO_PHONG_TRUOC_PHUT', 10)} phút trước giờ học).")
    if now > gio_dong_phong(buoi):
        raise ValidationError("Buổi học đã kết thúc, phòng Zoom đã đóng.")
    try:
        return lay_zoom_client().lay_start_url(buoi.zoom_meeting_id)
    except ZoomError as exc:
        raise ValidationError(f"Không lấy được link mở phòng: {exc}")


# =============================================================================
# Tạo nhiều buổi một lần (SD-13): kiểm tra trước, tạo từng buổi độc lập
# =============================================================================
def thoi_luong_cua_lop(lop, thoi_luong_thu=None):
    if thoi_luong_demo():
        return thoi_luong_demo()
    return lop.thoi_luong_phut if isinstance(lop, KhoaHoc) else int(thoi_luong_thu or 90)


def kiem_tra_ke_hoach(gia_su, lop, ds_bat_dau, hoc_bu_cho=None, thoi_luong_thu=None):
    """Kiểm tra từng buổi dự kiến; KHÔNG ghi gì. lop = KhoaHoc (chính thức) hoặc YeuCauHocTap (học thử).

    Trả về list dict: bat_dau, ket_thuc, muc ("ok" | "chan" | "canh_bao"), ly_do, nhan ("Buổi 6/16").
    """
    toi_da = NV.get("SO_BUOI_TAO_TOI_DA_MOT_LAN", 8)
    if not ds_bat_dau:
        raise ValidationError("Chọn ít nhất một ngày giờ học.")
    if len(ds_bat_dau) > toi_da:
        raise ValidationError(f"Mỗi lần tạo tối đa {toi_da} buổi.")
    la_khoa = isinstance(lop, KhoaHoc)
    if la_khoa:
        if lop.gia_su_id != gia_su.pk:
            raise ValidationError("Đây không phải khóa bạn phụ trách.")
        if lop.trang_thai != KH.DANG_HOC:
            raise ValidationError(f"Khóa đang ở trạng thái \"{lop.get_trang_thai_display()}\", chưa xếp lịch được.")
        con = lop.so_buoi_co_the_xep
        so_dau = lop.so_buoi_da_dung + lop.so_buoi_dang_len_lich
    else:
        if lop.gia_su_id != gia_su.pk or lop.trang_thai != YC.DA_PHAN_CONG:
            raise ValidationError("Chỉ tạo buổi học thử cho lớp bạn đã nhận và đang chờ chốt.")
        if lop.dang_ky_thang:
            raise ValidationError("Phụ huynh đã đăng ký chính thức luôn (không học thử). Chờ Tuyển sinh mở khóa học.")
        if lop.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su).exclude(trang_thai=TT.DA_HUY).exists():
            raise ValidationError("Lớp này đã có buổi học thử. Muốn đổi giờ thì dùng Dời lịch.")
        con, so_dau = 1, 0
    kiem_tra_hoc_bu(lop, hoc_bu_cho)
    thoi_luong = thoi_luong_cua_lop(lop, thoi_luong_thu)
    kq, da_nhan = [], []
    for i, bd in enumerate(sorted(ds_bat_dau)):
        kt = bd + timedelta(minutes=thoi_luong)
        dong = {"bat_dau": bd, "ket_thuc": kt, "muc": "ok", "ly_do": "",
                "nhan": (f"Buổi {so_dau + len(da_nhan) + 1}/{lop.so_buoi_dang_ky}" if la_khoa else "Học thử")}
        if len(da_nhan) >= con:
            dong.update(muc="chan", ly_do=("Khóa đã xếp đủ số buổi đăng ký." if la_khoa
                                           else "Học thử chỉ tạo một buổi."))
        elif any(bd < b2 and kt > b1 for b1, b2 in da_nhan):
            dong.update(muc="chan", ly_do="Trùng giờ với một buổi khác trong lần tạo này.")
        else:
            try:
                kiem_tra_khung_gio(gia_su, bd, thoi_luong)
            except ValidationError as exc:
                dong.update(muc="chan", ly_do=" ".join(m for v in exc.message_dict.values() for m in v)
                            if hasattr(exc, "error_dict") else " ".join(exc.messages))
        if dong["muc"] == "ok":
            da_nhan.append((bd, kt))
            if ngoai_gio_ranh(gia_su, bd, thoi_luong):
                dong.update(muc="canh_bao",
                            ly_do="Ngoài giờ rảnh đã đăng ký. Vẫn tạo được, nhớ thống nhất với phụ huynh.")
        if hoc_bu_cho and i == 0 and dong["muc"] != "chan":
            dong["nhan"] += " · Học bù"
        kq.append(dong)
    return kq


def tao_nhieu_buoi(gia_su, lop, ds_bat_dau, hoc_bu_cho=None, thoi_luong_thu=None):
    """Tạo các buổi đạt kiểm tra. Mỗi buổi một transaction riêng: buổi lỗi không kéo buổi khác.

    Trả về list dict: bat_dau, buoi (None nếu không tạo), loi.
    """
    ke_hoach = kiem_tra_ke_hoach(gia_su, lop, ds_bat_dau, hoc_bu_cho, thoi_luong_thu)
    kq, bu = [], hoc_bu_cho
    for dong in ke_hoach:
        if dong["muc"] == "chan":
            kq.append({"bat_dau": dong["bat_dau"], "buoi": None, "loi": dong["ly_do"]})
            continue
        try:
            with transaction.atomic():
                if isinstance(lop, KhoaHoc):
                    b = tao_buoi_chinh_thuc(gia_su, lop, dong["bat_dau"], hoc_bu_cho=bu)
                else:
                    b = tao_buoi_hoc_thu(gia_su, lop, dong["bat_dau"], thoi_luong_cua_lop(lop, thoi_luong_thu))
            bu = None  # chỉ buổi đầu tiên là buổi học bù
            kq.append({"bat_dau": dong["bat_dau"], "buoi": b, "loi": ""})
        except ValidationError as exc:
            kq.append({"bat_dau": dong["bat_dau"], "buoi": None,
                       "loi": " ".join(m for v in exc.message_dict.values() for m in v)
                       if hasattr(exc, "error_dict") else " ".join(exc.messages)})
    return kq


# =============================================================================
# Hủy / dời lịch
# =============================================================================
LY_DO_GIA_SU_CHON = [BuoiHoc.LyDoHuy.GIA_SU_HUY, BuoiHoc.LyDoHuy.HOC_VIEN_HUY]


def huy_buoi(nguoi, buoi, ly_do_huy, ghi_chu="", boi_he_thong=False):
    ghi_chu = (ghi_chu or "").strip()[:300]
    if not boi_he_thong:
        if buoi.gia_su_id != nguoi.pk:
            raise ValidationError("Đây không phải buổi học của bạn.")
        if ly_do_huy not in LY_DO_GIA_SU_CHON + [BuoiHoc.LyDoHuy.DOI_LICH]:
            raise ValidationError("Lý do hủy không hợp lệ.")
        if buoi.bat_dau <= timezone.now():
            raise ValidationError("Buổi học đã bắt đầu, không hủy được nữa. Nếu buổi không diễn ra, "
                                  "hãy để hệ thống tự hủy sau hạn xác nhận.")
    n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO).update(
        trang_thai=TT.DA_HUY, ly_do_huy=ly_do_huy, ly_do_huy_ghi_chu=ghi_chu, kiem_tra_ghi_chu=ghi_chu,
        cap_nhat_luc=timezone.now())
    if n == 0:
        raise ValidationError("Buổi học không còn ở trạng thái hủy được.")
    buoi.refresh_from_db()
    ghi_nhat_ky(nguoi, "Hủy buổi học", buoi.ma, f"{buoi.get_ly_do_huy_display()}. {ghi_chu}".strip())
    # Xóa phòng Zoom SAU khi lưu thành công: nếu thao tác bị rollback, phòng cũ vẫn còn dùng được.
    transaction.on_commit(lambda: _xoa_zoom(buoi))
    return buoi


def doi_lich(gia_su, buoi, bat_dau_moi):
    """Dời lịch = hủy buổi cũ (DOI_LICH) + tạo buổi mới trỏ về buổi cũ. Kiểm tra buổi mới trước khi hủy."""
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai not in BuoiHoc.TRANG_THAI_CHIEM_CHO:
        raise ValidationError("Buổi học này không dời lịch được.")
    if buoi.bat_dau <= timezone.now():
        raise ValidationError("Buổi học đã bắt đầu, không dời lịch được.")
    with transaction.atomic():
        # Tạo buổi mới TRƯỚC (kiểm tra giờ, khóa…); lỗi ở bước này thì buổi cũ giữ nguyên, phòng Zoom cũ còn.
        if buoi.loai == BuoiHoc.Loai.CHINH_THUC:
            moi = tao_buoi_chinh_thuc(gia_su, buoi.khoa_hoc, bat_dau_moi, thay_the_cho=buoi)
        else:
            moi = tao_buoi_hoc_thu(gia_su, buoi.yeu_cau, bat_dau_moi, buoi.thoi_luong_phut, thay_the_cho=buoi)
        huy_buoi(gia_su, buoi, BuoiHoc.LyDoHuy.DOI_LICH,
                 f"Dời sang {timezone.localtime(bat_dau_moi):%H:%M %d/%m/%Y}")
    return moi


# =============================================================================
# Xác nhận hoàn tất (gia sư) → số buổi, thù lao, Zalo
# =============================================================================
def xac_nhan_hoan_tat(gia_su, buoi, du_lieu, bo_qua_han=False, nguoi_thuc_hien=None):
    """du_lieu: noi_dung, xep_loai, danh_gia (≥ 30 ký tự), dan_do_buoi_sau, ghi_chu_tuyen_sinh, gui_zalo_phu_huynh.

    bo_qua_han + nguoi_thuc_hien: Quản trị viên khôi phục từ bản nháp sau lỗi hệ thống (SD-34).
    """
    now = timezone.now()
    if buoi.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải buổi học của bạn.")
    if buoi.trang_thai != TT.DA_LEN_LICH:
        raise ValidationError(f"Buổi học đang ở trạng thái \"{buoi.get_trang_thai_display()}\", không xác nhận được.")
    if now < buoi.ket_thuc:
        raise ValidationError(f"Chỉ xác nhận được sau giờ kết thúc ({timezone.localtime(buoi.ket_thuc):%H:%M %d/%m}).")
    if buoi.han_xac_nhan and now > buoi.han_xac_nhan and not bo_qua_han:
        raise ValidationError("Đã quá hạn xác nhận. Nếu buổi học thực sự đã diễn ra, hãy gửi yêu cầu mở lại.")
    toi_thieu = NV.get("DO_DAI_NHAN_XET_TOI_THIEU", 30)
    danh_gia = (du_lieu.get("danh_gia") or "").strip()
    if len(danh_gia) < toi_thieu:
        raise ValidationError({"danh_gia": f"Nhận xét gửi phụ huynh cần ít nhất {toi_thieu} ký tự."})
    if du_lieu.get("xep_loai") not in BuoiHoc.XepLoai.values:
        raise ValidationError({"xep_loai": "Hãy chọn mức tiếp thu."})
    if not (du_lieu.get("noi_dung") or "").strip():
        raise ValidationError({"noi_dung": "Hãy ghi nội dung đã dạy."})
    gui_zalo = du_lieu.get("gui_zalo_phu_huynh", True) not in (False, "", "0", "off", None)
    nguoi = nguoi_thuc_hien or gia_su

    with transaction.atomic():
        n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai=TT.DA_LEN_LICH).update(
            trang_thai=TT.HOAN_TAT, xac_nhan_luc=now, cap_nhat_luc=now,
            noi_dung=du_lieu["noi_dung"].strip(), xep_loai=du_lieu["xep_loai"], danh_gia=danh_gia,
            dan_do_buoi_sau=(du_lieu.get("dan_do_buoi_sau") or "").strip(),
            ghi_chu_tuyen_sinh=(du_lieu.get("ghi_chu_tuyen_sinh") or "").strip(), gui_zalo_phu_huynh=gui_zalo)
        if n == 0:
            raise ValidationError("Buổi học vừa được xác nhận hoặc thay đổi, vui lòng tải lại trang.")
        if buoi.khoa_hoc_id:
            # Cộng số buổi có điều kiện: không bao giờ vượt số đăng ký, kể cả bấm 2 lần cùng lúc.
            n = KhoaHoc.objects.filter(pk=buoi.khoa_hoc_id, so_buoi_da_dung__lt=F("so_buoi_dang_ky")).update(
                so_buoi_da_dung=F("so_buoi_da_dung") + 1)
            if n == 0:
                raise ValidationError("Khóa học đã dùng hết số buổi đăng ký.")
            khoa = KhoaHoc.objects.get(pk=buoi.khoa_hoc_id)
            BuoiHoc.objects.filter(pk=buoi.pk).update(so_thu_tu=khoa.so_buoi_da_dung)
            if khoa.so_buoi_da_dung >= khoa.so_buoi_dang_ky and khoa.trang_thai == KH.DANG_HOC:
                KhoaHoc.objects.filter(pk=khoa.pk).update(trang_thai=KH.HOAN_THANH, hoan_thanh_luc=now)
            if buoi.thu_lao_du_kien:
                from core.services.thu_lao import thang_ghi_nhan
                ThuLao.objects.create(buoi_hoc=buoi, gia_su=gia_su, so_tien=buoi.thu_lao_du_kien,
                                      thang=thang_ghi_nhan(gia_su, timezone.localtime(buoi.bat_dau).date()))
        BanNhapDanhGia.objects.filter(buoi_hoc=buoi).delete()
        ho_so = getattr(gia_su, "ho_so_gia_su", None)
        HauKiemBuoi.objects.get_or_create(buoi_hoc=buoi, defaults={
            "nguoi_phu_trach_id": getattr(ho_so, "nguoi_moi_id", None), "do_dai_nhan_xet": len(danh_gia)})
        chi_tiet = str(BuoiHoc.XepLoai(du_lieu["xep_loai"]).label)
        if nguoi_thuc_hien:
            chi_tiet = f"Quản trị viên khôi phục thay gia sư {gia_su.ho_ten} từ bản nháp. {chi_tiet}"
        ghi_nhat_ky(nguoi, "Xác nhận hoàn tất buổi học", buoi.ma, chi_tiet)
    buoi.refresh_from_db()
    if gui_zalo:
        gui_zalo_danh_gia(buoi)
        gui_email_danh_gia(buoi)
    return buoi


def luu_nhap(gia_su, buoi, du_lieu):
    """Tự lưu nháp phiếu đánh giá (SD-15). Chỉ gia sư của buổi, buổi đang chờ xác nhận / lên lịch."""
    if buoi.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải buổi học của bạn.")
    if buoi.trang_thai != TT.DA_LEN_LICH:
        raise ValidationError("Buổi học không còn ở trạng thái nhập đánh giá.")
    giu = {k: str(du_lieu.get(k, ""))[:2000] for k in
           ("noi_dung", "xep_loai", "danh_gia", "dan_do_buoi_sau", "ghi_chu_tuyen_sinh", "gui_zalo_phu_huynh")}
    nhap, _ = BanNhapDanhGia.objects.update_or_create(buoi_hoc=buoi, defaults={"du_lieu": giu})
    return nhap


def so_thu_tu_du_kien(buoi):
    """Buổi thứ mấy của khóa (đã xác nhận thì lấy số thật; đang lên lịch thì ước tính theo thứ tự thời gian)."""
    if buoi.so_thu_tu:
        return buoi.so_thu_tu
    if not buoi.khoa_hoc_id:
        return None
    k = buoi.khoa_hoc
    truoc = k.buoi_hoc.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__lt=buoi.bat_dau).count()
    return k.so_buoi_da_dung + truoc + (1 if buoi.trang_thai in BuoiHoc.TRANG_THAI_CHIEM_CHO else 0)


def nhan_buoi(buoi):
    """"Buổi 6/16 · Học bù" / "Học thử"."""
    if buoi.loai == BuoiHoc.Loai.HOC_THU:
        nhan = "Học thử"
    else:
        so = so_thu_tu_du_kien(buoi)
        nhan = f"Buổi {so}/{buoi.khoa_hoc.so_buoi_dang_ky}" if so else "Buổi chính thức"
    if buoi.hoc_bu_cho_id:
        nhan += " · Học bù"
    return nhan


def link_lop(buoi_hoac_khoa, request=None):
    """Link lớp cố định /lop/<ma_lop>/ (học thử: theo mã buổi)."""
    from django.urls import reverse
    if isinstance(buoi_hoac_khoa, KhoaHoc):
        ma = buoi_hoac_khoa.ma_lop or buoi_hoac_khoa.ma
    elif buoi_hoac_khoa.khoa_hoc_id:
        ma = buoi_hoac_khoa.khoa_hoc.ma_lop or buoi_hoac_khoa.khoa_hoc.ma
    else:
        ma = buoi_hoac_khoa.ma
    url = reverse("vao_lop", args=[ma])
    return request.build_absolute_uri(url) if request else url


def noi_dung_moi_vao_lop(buoi, request=None):
    """Tin nhắn gia sư dán vào nhóm Zalo lớp (SD-13). KHÔNG có host key, học phí, SĐT phụ huynh."""
    bd = timezone.localtime(buoi.bat_dau)
    thu = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][bd.weekday()]
    lop = buoi.khoa_hoc.ma if buoi.khoa_hoc_id else buoi.yeu_cau.ma
    dong = [f"Topic: Buổi dạy {lop} - {buoi.yeu_cau.mon_hoc} ({nhan_buoi(buoi)}) của gia sư {buoi.gia_su.ho_ten} "
            f"và học viên {buoi.hoc_vien.ho_ten} vào {bd:%H:%M} {thu} {bd:%d/%m/%Y}",
            f"Vào lớp: {link_lop(buoi, request)}"]
    if buoi.zoom_join_url:
        dong.append(f"Link Zoom: {buoi.zoom_join_url}")
    if buoi.zoom_meeting_id:
        mid = buoi.zoom_meeting_id
        dong.append("Meeting ID: " + (" ".join([mid[:3], mid[3:7], mid[7:]]) if len(mid) == 11 else mid))
    if buoi.zoom_passcode:
        dong.append(f"Passcode: {buoi.zoom_passcode}")
    dong.append(f"Phòng mở trước {NV.get('MO_PHONG_TRUOC_PHUT', 10)} phút.")
    return "\n".join(dong)


def buoi_dang_mo(ma_lop, now=None):
    """(buổi trong cửa sổ vào lớp, buổi sắp tới) của một lớp cố định (SD-14)."""
    now = now or timezone.now()
    ma = (ma_lop or "").upper()
    if ma.startswith("BH-"):
        ds = BuoiHoc.objects.filter(pk=int(ma[3:]) if ma[3:].isdigit() else 0)
    else:
        ds = BuoiHoc.objects.filter(khoa_hoc__ma_lop=ma)
    ds = ds.filter(trang_thai=TT.DA_LEN_LICH).exclude(zoom_join_url="").order_by("bat_dau")
    truoc = timedelta(minutes=NV.get("MO_PHONG_TRUOC_PHUT", 10))
    sau = timedelta(minutes=NV.get("DONG_PHONG_SAU_PHUT", 5))
    dang = ds.filter(bat_dau__lte=now + truoc, ket_thuc_luc__gte=now - sau).first()
    sap = ds.filter(bat_dau__gt=now + truoc).first()
    return dang, sap


def noi_dung_gui_phu_huynh(buoi):
    """Tin nhắn gửi phụ huynh (dùng cho ZNS và nút Sao chép khi chưa có OA Zalo)."""
    dong = [
        f"Trung tâm Gia sư Trực tuyến gửi phụ huynh em {buoi.hoc_vien.ho_ten}:",
        f"Buổi {'học thử' if buoi.loai == BuoiHoc.Loai.HOC_THU else 'học'} môn {buoi.yeu_cau.mon_hoc} "
        f"lúc {timezone.localtime(buoi.bat_dau):%H:%M %d/%m/%Y} với gia sư {buoi.gia_su.ho_ten}.",
        f"- Nội dung: {buoi.noi_dung}",
        f"- Đánh giá: {buoi.get_xep_loai_display()}",
        f"- Nhận xét: {buoi.danh_gia}",
    ]
    if buoi.dan_do_buoi_sau:
        dong.append(f"- Dặn dò buổi sau: {buoi.dan_do_buoi_sau}")
    if buoi.khoa_hoc_id:
        k = buoi.khoa_hoc
        dong.append(f"Tiến độ khóa: {k.so_buoi_da_dung}/{k.so_buoi_dang_ky} buổi.")
    return "\n".join(dong)


def gui_zalo_danh_gia(buoi):
    """Gửi đánh giá cho phụ huynh qua Zalo ZNS. Lỗi gửi KHÔNG làm hỏng việc xác nhận."""
    hv = buoi.hoc_vien
    du_lieu = {
        "ten_hoc_vien": hv.ho_ten, "mon_hoc": str(buoi.yeu_cau.mon_hoc),
        "thoi_gian": f"{timezone.localtime(buoi.bat_dau):%H:%M %d/%m/%Y}", "gia_su": buoi.gia_su.ho_ten,
        "noi_dung": buoi.noi_dung[:100], "danh_gia": buoi.get_xep_loai_display(),
        "nhan_xet": buoi.danh_gia[:100],
    }
    try:
        kq = lay_zalo_client().gui_zns(hv.sdt_phu_huynh, du_lieu)
        ok, phan_hoi = kq.thanh_cong, kq.phan_hoi
    except Exception as exc:  # thiếu cấu hình, lỗi mạng…
        ok, phan_hoi = False, str(exc)
    NhatKyGuiTin.objects.create(kenh=NhatKyGuiTin.Kenh.ZALO, nguoi_nhan=hv.sdt_phu_huynh,
                                tieu_de=f"Đánh giá {buoi.ma}", noi_dung=noi_dung_gui_phu_huynh(buoi),
                                buoi_hoc=buoi, thanh_cong=ok, phan_hoi=phan_hoi[:2000])
    buoi.zalo_trang_thai = BuoiHoc.GuiZalo.DA_GUI if ok else BuoiHoc.GuiZalo.LOI
    buoi.save(update_fields=["zalo_trang_thai"])
    return ok


def gui_email_danh_gia(buoi):
    """Gửi đánh giá buổi học tới email phụ huynh (kênh miễn phí, song song với Zalo).
    Học viên chưa có email phụ huynh → bỏ qua (giữ CHUA_GUI). Lỗi gửi KHÔNG làm hỏng việc xác nhận."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    hv = buoi.hoc_vien
    if not hv.email_phu_huynh:
        return None
    bd = timezone.localtime(buoi.bat_dau)
    tieu_de = f"Đánh giá buổi {buoi.yeu_cau.mon_hoc} của {hv.ho_ten} – {bd:%d/%m/%Y}"
    van_ban = noi_dung_gui_phu_huynh(buoi)
    try:
        html = render_to_string("email/danh_gia_buoi.html", {"b": buoi, "hv": hv, "bd": bd})
        m = EmailMultiAlternatives(tieu_de, van_ban, settings.DEFAULT_FROM_EMAIL, [hv.email_phu_huynh])
        m.attach_alternative(html, "text/html")
        m.send(fail_silently=False)
        ok, phan_hoi = True, "OK"
    except Exception as exc:  # mạng lỗi, sai mật khẩu SMTP…
        logger.warning("Gửi email đánh giá %s thất bại: %s", buoi.ma, exc)
        ok, phan_hoi = False, str(exc)
    NhatKyGuiTin.objects.create(kenh=NhatKyGuiTin.Kenh.EMAIL, nguoi_nhan=hv.email_phu_huynh, tieu_de=tieu_de[:200],
                                noi_dung=van_ban, buoi_hoc=buoi, thanh_cong=ok, phan_hoi=phan_hoi[:2000])
    buoi.email_trang_thai = BuoiHoc.GuiZalo.DA_GUI if ok else BuoiHoc.GuiZalo.LOI
    buoi.save(update_fields=["email_trang_thai"])
    return ok


# =============================================================================
# Quét theo hạn (rẻ, chạy khi mở trang): nhắc hạn + tự hủy quá hạn
# =============================================================================
def quet_han(now=None):
    now = now or timezone.now()
    # 1) Nhắc gia sư khi còn NHAC_TRUOC_HAN_GIO giờ.
    can_nhac = BuoiHoc.objects.filter(trang_thai=TT.DA_LEN_LICH, da_nhac_han=False, han_xac_nhan__gt=now,
                                      han_xac_nhan__lte=now + _gio(NV["NHAC_TRUOC_HAN_GIO"]))
    for b in can_nhac.select_related("gia_su", "hoc_vien", "yeu_cau__mon_hoc"):
        if b.ket_thuc > now:
            continue
        if BuoiHoc.objects.filter(pk=b.pk, da_nhac_han=False).update(da_nhac_han=True):
            gui_email(b.gia_su, f"Nhắc xác nhận buổi học {b.ma}",
                      f"Buổi {b.yeu_cau.mon_hoc} với {b.hoc_vien.ho_ten} lúc {timezone.localtime(b.bat_dau):%H:%M %d/%m} "
                      f"chưa được xác nhận. Hạn cuối: {timezone.localtime(b.han_xac_nhan):%H:%M %d/%m}. "
                      "Quá hạn hệ thống sẽ tự hủy buổi và không tính thù lao.", buoi_hoc=b)
    # 2) Tự hủy buổi quá hạn xác nhận.
    qua_han = list(BuoiHoc.objects.filter(trang_thai=TT.DA_LEN_LICH, han_xac_nhan__lt=now)
                   .select_related("gia_su", "hoc_vien", "yeu_cau__mon_hoc"))
    for b in qua_han:
        if BuoiHoc.objects.filter(pk=b.pk, trang_thai=TT.DA_LEN_LICH).update(
                trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN, cap_nhat_luc=now):
            ghi_nhat_ky(None, "Tự hủy buổi quá hạn xác nhận", b.ma, str(b))
            gui_email(b.gia_su, f"Buổi học {b.ma} đã bị hủy do quá hạn xác nhận",
                      f"Buổi {b.yeu_cau.mon_hoc} với {b.hoc_vien.ho_ten} lúc {timezone.localtime(b.bat_dau):%H:%M %d/%m} "
                      f"không được xác nhận trước {timezone.localtime(b.han_xac_nhan):%H:%M %d/%m} nên đã bị hủy. "
                      f"Nếu buổi học thực sự đã diễn ra, liên hệ Admin trong {NV['NGAY_MO_LAI_TOI_DA']} ngày "
                      "để được mở lại.", buoi_hoc=b)
    # 3) Buổi lỗi Zoom đã qua giờ bắt đầu → hủy (không còn ý nghĩa thử lại) và báo gia sư.
    for b in BuoiHoc.objects.filter(trang_thai=TT.LOI_ZOOM, bat_dau__lt=now).select_related(
            "gia_su", "hoc_vien", "yeu_cau__mon_hoc"):
        if BuoiHoc.objects.filter(pk=b.pk, trang_thai=TT.LOI_ZOOM).update(
                trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.LOI_ZOOM, cap_nhat_luc=now):
            ghi_nhat_ky(None, "Tự hủy buổi không tạo được phòng Zoom", b.ma, b.zoom_loi[:300])
            gui_email(b.gia_su, f"Buổi học {b.ma} bị hủy vì chưa có phòng Zoom",
                      f"Buổi {b.yeu_cau.mon_hoc} với {b.hoc_vien.ho_ten} lúc {timezone.localtime(b.bat_dau):%H:%M %d/%m} "
                      "chưa tạo được phòng Zoom trước giờ học nên đã bị hủy và không tính vào khóa. "
                      "Hãy tạo buổi bù và báo phụ huynh.", buoi_hoc=b)
    return len(qua_han)


# =============================================================================
# Hậu kiểm Zoom (gọi API, chạy bằng lệnh quet_dinh_ky): tham gia + bản ghi
# =============================================================================
def _phut_giao(khoang_a, khoang_b):
    """Tổng số phút giao nhau giữa hai danh sách khoảng [vào, ra)."""
    tong = 0.0
    for a1, a2 in khoang_a:
        for b1, b2 in khoang_b:
            dau, cuoi = max(a1, b1), min(a2, b2)
            if cuoi > dau:
                tong += (cuoi - dau).total_seconds() / 60
    return int(tong)


def danh_gia_tham_gia(buoi, ds):
    """→ (đạt?, phút cùng có mặt, phút thực tế). Gia sư (host) và học viên phải cùng có mặt ≥ ngưỡng."""
    host = [(p.vao_luc, p.ra_luc) for p in ds if p.la_host and p.vao_luc and p.ra_luc]
    khach = [(p.vao_luc, p.ra_luc) for p in ds if not p.la_host and p.vao_luc and p.ra_luc]
    chung = _phut_giao(host, khach)
    tat_ca = [t for k in host + khach for t in k]
    thuc_te = int((max(tat_ca) - min(tat_ca)).total_seconds() // 60) if tat_ca else 0
    return chung >= buoi.thoi_luong_phut * NV["NGUONG_THAM_GIA"], chung, thuc_te


def hau_kiem(now=None):
    """SD-20: chấm 5 tiêu chí cho buổi đã xác nhận (lấy người tham gia từ Zoom) + lấy bản ghi.
    KHÔNG đổi trạng thái buổi, KHÔNG tạm giữ thù lao: Tuyển sinh người mời gia sư kết luận (SD-21)."""
    from core.services import hau_kiem as dv_hk
    from core.services.thong_bao import thong_bao
    now = now or timezone.now()
    zoom = lay_zoom_client()
    da_xu_ly = 0
    gom = {}  # tuyển sinh → [số buổi, số có cảnh báo]
    ds = (BuoiHoc.objects.filter(trang_thai=TT.HOAN_TAT, bat_dau__gte=now - timedelta(days=NV["NGAY_MO_LAI_TOI_DA"]))
          .filter(models_Q(hau_kiem__isnull=True) | models_Q(hau_kiem__da_cham=False,
                                                              hau_kiem__ket_luan=HauKiemBuoi.KetLuan.CHUA_KIEM_TRA)))
    for b in ds.select_related("gia_su__ho_so_gia_su", "hoc_vien", "yeu_cau__mon_hoc"):
        if b.ket_thuc + _cho_zoom_tong_hop() > now:
            continue  # Zoom cần thời gian tổng hợp báo cáo
        hk, _ = HauKiemBuoi.objects.get_or_create(buoi_hoc=b, defaults={
            "nguoi_phu_trach_id": getattr(getattr(b.gia_su, "ho_so_gia_su", None), "nguoi_moi_id", None)})
        hk.buoi_hoc = b
        if not b.zoom_meeting_id:
            dv_hk.cham(hk, None, co_du_lieu=False)
        else:
            try:
                nguoi = zoom.lay_nguoi_tham_gia(b.zoom_meeting_id)
            except ZoomError as exc:
                logger.info("Hậu kiểm %s chưa lấy được dữ liệu: %s", b.ma, exc)
                continue
            if nguoi is None:
                BuoiHoc.objects.filter(pk=b.pk).update(
                    kiem_tra=BuoiHoc.KiemTra.KHONG_DU_LIEU,
                    kiem_tra_ghi_chu="Gói Zoom không cung cấp danh sách người tham gia, buổi được giữ như gia sư xác nhận.")
                dv_hk.cham(hk, None, co_du_lieu=False)
            else:
                _, chung, thuc_te = danh_gia_tham_gia(b, nguoi)
                BuoiHoc.objects.filter(pk=b.pk).update(phut_tham_gia_chung=chung, thoi_luong_thuc_te=thuc_te)
                dv_hk.cham(hk, nguoi)
        da_xu_ly += 1
        if hk.nguoi_phu_trach_id:
            x = gom.setdefault(hk.nguoi_phu_trach_id, [0, 0])
            x[0] += 1
            x[1] += hk.so_canh_bao > 0
    if gom:
        from django.urls import reverse
        from core.models import User
        for u in User.objects.filter(pk__in=gom):
            n, m = gom[u.pk]
            thong_bao(u, f"{n} buổi chờ hậu kiểm" + (f", {m} buổi có cảnh báo" if m else ""),
                      "Hệ thống đã đối chiếu dữ liệu Zoom và phiếu đánh giá.", reverse("hau_kiem"), "XEM_XET")

    # Bản ghi (chỉ buổi phụ huynh đồng ý ghi hình).
    cho = BuoiHoc.objects.filter(trang_thai__in=[TT.HOAN_TAT, TT.DANG_XEM_XET],
                                 ban_ghi_trang_thai=BuoiHoc.BanGhi.CHO_XU_LY).exclude(zoom_meeting_id="")
    for b in cho:
        if b.ket_thuc + _cho_zoom_tong_hop() > now:
            continue
        try:
            bg = zoom.lay_ban_ghi(b.zoom_meeting_id)
        except ZoomError:
            continue
        if bg.san_sang:
            BuoiHoc.objects.filter(pk=b.pk).update(
                ban_ghi_trang_thai=BuoiHoc.BanGhi.SAN_SANG, ban_ghi_url=bg.share_url, ban_ghi_passcode=bg.passcode,
                ban_ghi_het_han=now + timedelta(days=NV["NGAY_LUU_BAN_GHI"]))
        elif b.ket_thuc + timedelta(days=2) < now:
            BuoiHoc.objects.filter(pk=b.pk).update(ban_ghi_trang_thai=BuoiHoc.BanGhi.LOI)
    BuoiHoc.objects.filter(ban_ghi_trang_thai=BuoiHoc.BanGhi.SAN_SANG, ban_ghi_het_han__lt=now).update(
        ban_ghi_trang_thai=BuoiHoc.BanGhi.HET_HAN)
    return da_xu_ly
