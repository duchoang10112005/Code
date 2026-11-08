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
from django.db.models import F
from django.utils import timezone

from core.integrations.zalo import lay_zalo_client
from core.integrations.zoom import ZoomError, lay_zoom_client
from core.models import BuoiHoc, KhoaHoc, NhatKyGuiTin, ThuLao, YeuCauHocTap
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


# =============================================================================
# Kiểm tra khung giờ
# =============================================================================
def _buoi_trung_gio(bat_dau, ket_thuc, bo_qua_pk=None):
    """Các buổi đang giữ chỗ có khoảng thời gian giao với [bat_dau, ket_thuc)."""
    qs = BuoiHoc.objects.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__lt=ket_thuc)
    if bo_qua_pk:
        qs = qs.exclude(pk=bo_qua_pk)
    # ket_thuc của buổi khác = bat_dau + thoi_luong → lọc tiếp bằng Python (dữ liệu nhỏ, tránh hàm ngày của SQLite).
    return [b for b in qs.select_related("gia_su") if b.ket_thuc > bat_dau]


def kiem_tra_khung_gio(gia_su, bat_dau, thoi_luong, bo_qua_pk=None):
    now = timezone.now()
    if bat_dau <= now:
        raise ValidationError("Giờ bắt đầu phải ở tương lai.")
    if bat_dau > now + timedelta(days=60):
        raise ValidationError("Chỉ xếp lịch trước tối đa 60 ngày.")
    ket_thuc = bat_dau + timedelta(minutes=thoi_luong)
    trung = _buoi_trung_gio(bat_dau, ket_thuc, bo_qua_pk)
    cua_minh = [b for b in trung if b.gia_su_id == gia_su.pk]
    if cua_minh:
        b = cua_minh[0]
        raise ValidationError(f"Bạn đã có buổi học {timezone.localtime(b.bat_dau):%H:%M %d/%m} trùng khung giờ này.")
    if len(trung) >= NV["SO_PHONG_ZOOM_DONG_THOI"]:
        raise ValidationError("Khung giờ này đã có buổi học khác dùng phòng Zoom của trung tâm. "
                              "Vui lòng chọn giờ khác.")


# =============================================================================
# Tạo buổi học + phòng Zoom
# =============================================================================
def _chu_de(buoi):
    loai = "Học thử" if buoi.loai == BuoiHoc.Loai.HOC_THU else "Buổi học"
    return f"{loai} {buoi.yeu_cau.mon_hoc} – {buoi.hoc_vien.ho_ten} – GS {buoi.gia_su.ho_ten}"


def _gan_zoom(buoi):
    """Gọi Zoom tạo phòng. Thành công → DA_LEN_LICH; lỗi → LOI_ZOOM + lưu lỗi (không ném lỗi ra ngoài)."""
    try:
        phong = lay_zoom_client().tao_phong(
            settings.ZOOM_HOST_EMAIL_MAC_DINH, _chu_de(buoi), buoi.bat_dau, buoi.thoi_luong_phut,
            ghi_hinh=buoi.hoc_vien.dong_y_ghi_hinh)
    except ZoomError as exc:
        buoi.trang_thai, buoi.zoom_loi = TT.LOI_ZOOM, str(exc)[:1000]
        buoi.save(update_fields=["trang_thai", "zoom_loi", "cap_nhat_luc"])
        return False
    buoi.zoom_meeting_id, buoi.zoom_join_url = phong.meeting_id, phong.join_url
    buoi.zoom_start_url, buoi.zoom_passcode = phong.start_url, phong.passcode
    buoi.trang_thai, buoi.zoom_loi = TT.DA_LEN_LICH, ""
    buoi.save(update_fields=["zoom_meeting_id", "zoom_join_url", "zoom_start_url", "zoom_passcode",
                             "trang_thai", "zoom_loi", "cap_nhat_luc"])
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
    ds = YeuCauHocTap.objects.filter(gia_su=gia_su, trang_thai=YC.DA_PHAN_CONG).select_related("hoc_vien", "mon_hoc")
    return [y for y in ds if not y.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su)
            .exclude(trang_thai=TT.DA_HUY).exists()]


def tao_buoi_chinh_thuc(gia_su, khoa, bat_dau, thay_the_cho=None):
    khoa.refresh_from_db()
    if khoa.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải khóa bạn phụ trách.")
    if khoa.trang_thai != KH.DANG_HOC:
        raise ValidationError(f"Khóa đang ở trạng thái \"{khoa.get_trang_thai_display()}\", chưa xếp lịch được.")
    if khoa.so_buoi_co_the_xep <= 0 and not thay_the_cho:
        raise ValidationError("Khóa đã xếp đủ số buổi đăng ký, không tạo thêm buổi được.")
    kiem_tra_khung_gio(gia_su, bat_dau, khoa.thoi_luong_phut, bo_qua_pk=getattr(thay_the_cho, "pk", None))
    return _tao(gia_su, BuoiHoc.Loai.CHINH_THUC, khoa.yeu_cau, bat_dau, khoa.thoi_luong_phut,
                khoa=khoa, thu_lao=khoa.thu_lao_moi_buoi, thay_the_cho=thay_the_cho)


def tao_buoi_hoc_thu(gia_su, yc, bat_dau, thoi_luong, thay_the_cho=None):
    yc.refresh_from_db()
    if yc.gia_su_id != gia_su.pk or yc.trang_thai != YC.DA_PHAN_CONG:
        raise ValidationError("Chỉ tạo buổi học thử cho lớp bạn đã nhận và đang chờ chốt.")
    if thoi_luong not in THOI_LUONG_HOC_THU:
        raise ValidationError("Thời lượng học thử không hợp lệ.")
    da_co = yc.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su).exclude(trang_thai=TT.DA_HUY)
    if thay_the_cho:
        da_co = da_co.exclude(pk=thay_the_cho.pk)
    if da_co.exists():
        raise ValidationError("Lớp này đã có buổi học thử. Muốn đổi giờ thì dùng Dời lịch.")
    kiem_tra_khung_gio(gia_su, bat_dau, thoi_luong, bo_qua_pk=getattr(thay_the_cho, "pk", None))
    return _tao(gia_su, BuoiHoc.Loai.HOC_THU, yc, bat_dau, thoi_luong, thay_the_cho=thay_the_cho)


def _tao(gia_su, loai, yc, bat_dau, thoi_luong, khoa=None, thu_lao=0, thay_the_cho=None):
    hv = yc.hoc_vien
    buoi = BuoiHoc.objects.create(
        loai=loai, khoa_hoc=khoa, yeu_cau=yc, gia_su=gia_su, hoc_vien=hv, bat_dau=bat_dau,
        thoi_luong_phut=thoi_luong, trang_thai=TT.LOI_ZOOM, thu_lao_du_kien=thu_lao,
        han_xac_nhan=bat_dau + timedelta(minutes=thoi_luong) + _gio(NV["HAN_XAC_NHAN_GIO"]),
        ban_ghi_trang_thai=BuoiHoc.BanGhi.CHO_XU_LY if hv.dong_y_ghi_hinh else BuoiHoc.BanGhi.KHONG_GHI,
        thay_the_cho=thay_the_cho,
    )
    ghi_nhat_ky(gia_su, "Tạo buổi học", buoi.ma, f"{buoi}; {thoi_luong} phút")
    _gan_zoom(buoi)
    return buoi


def thu_lai_zoom(gia_su, buoi):
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai != TT.LOI_ZOOM:
        raise ValidationError("Buổi này không ở trạng thái lỗi Zoom.")
    if buoi.bat_dau <= timezone.now():
        raise ValidationError("Đã qua giờ bắt đầu, hãy hủy buổi này và tạo buổi mới.")
    return _gan_zoom(buoi)


def lay_link_mo_phong(gia_su, buoi):
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai != TT.DA_LEN_LICH or not buoi.zoom_meeting_id:
        raise ValidationError("Buổi học chưa có phòng Zoom.")
    try:
        return lay_zoom_client().lay_start_url(buoi.zoom_meeting_id)
    except ZoomError as exc:
        raise ValidationError(f"Không lấy được link mở phòng: {exc}")


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
        trang_thai=TT.DA_HUY, ly_do_huy=ly_do_huy, kiem_tra_ghi_chu=ghi_chu, cap_nhat_luc=timezone.now())
    if n == 0:
        raise ValidationError("Buổi học không còn ở trạng thái hủy được.")
    buoi.refresh_from_db()
    ghi_nhat_ky(nguoi, "Hủy buổi học", buoi.ma, f"{buoi.get_ly_do_huy_display()}. {ghi_chu}".strip())
    _xoa_zoom(buoi)
    return buoi


def doi_lich(gia_su, buoi, bat_dau_moi):
    """Dời lịch = hủy buổi cũ (DOI_LICH) + tạo buổi mới trỏ về buổi cũ. Kiểm tra buổi mới trước khi hủy."""
    if buoi.gia_su_id != gia_su.pk or buoi.trang_thai not in BuoiHoc.TRANG_THAI_CHIEM_CHO:
        raise ValidationError("Buổi học này không dời lịch được.")
    if buoi.bat_dau <= timezone.now():
        raise ValidationError("Buổi học đã bắt đầu, không dời lịch được.")
    kiem_tra_khung_gio(gia_su, bat_dau_moi, buoi.thoi_luong_phut, bo_qua_pk=buoi.pk)
    with transaction.atomic():
        huy_buoi(gia_su, buoi, BuoiHoc.LyDoHuy.DOI_LICH,
                 f"Dời sang {timezone.localtime(bat_dau_moi):%H:%M %d/%m/%Y}")
        if buoi.loai == BuoiHoc.Loai.CHINH_THUC:
            moi = tao_buoi_chinh_thuc(gia_su, buoi.khoa_hoc, bat_dau_moi, thay_the_cho=buoi)
        else:
            moi = tao_buoi_hoc_thu(gia_su, buoi.yeu_cau, bat_dau_moi, buoi.thoi_luong_phut, thay_the_cho=buoi)
    return moi


# =============================================================================
# Xác nhận hoàn tất (gia sư) → số buổi, thù lao, Zalo
# =============================================================================
def xac_nhan_hoan_tat(gia_su, buoi, du_lieu):
    """du_lieu: noi_dung, xep_loai, danh_gia, dan_do_buoi_sau."""
    now = timezone.now()
    if buoi.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải buổi học của bạn.")
    if buoi.trang_thai != TT.DA_LEN_LICH:
        raise ValidationError(f"Buổi học đang ở trạng thái \"{buoi.get_trang_thai_display()}\", không xác nhận được.")
    if now < buoi.ket_thuc:
        raise ValidationError(f"Chỉ xác nhận được sau giờ kết thúc ({timezone.localtime(buoi.ket_thuc):%H:%M %d/%m}).")
    if buoi.han_xac_nhan and now > buoi.han_xac_nhan:
        raise ValidationError("Đã quá hạn xác nhận. Liên hệ Admin nếu buổi học thực sự đã diễn ra.")

    with transaction.atomic():
        n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai=TT.DA_LEN_LICH).update(
            trang_thai=TT.HOAN_TAT, xac_nhan_luc=now, cap_nhat_luc=now,
            noi_dung=du_lieu["noi_dung"], xep_loai=du_lieu["xep_loai"], danh_gia=du_lieu["danh_gia"],
            dan_do_buoi_sau=du_lieu.get("dan_do_buoi_sau", ""))
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
                KhoaHoc.objects.filter(pk=khoa.pk).update(trang_thai=KH.HOAN_THANH)
            if buoi.thu_lao_du_kien:
                from core.services.thu_lao import thang_ghi_nhan
                ThuLao.objects.create(buoi_hoc=buoi, gia_su=gia_su, so_tien=buoi.thu_lao_du_kien,
                                      thang=thang_ghi_nhan(gia_su, timezone.localtime(buoi.bat_dau).date()))
        ghi_nhat_ky(gia_su, "Xác nhận hoàn tất buổi học", buoi.ma,
                    str(BuoiHoc.XepLoai(du_lieu["xep_loai"]).label))
    buoi.refresh_from_db()
    gui_zalo_danh_gia(buoi)
    return buoi


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
    # 3) Buổi lỗi Zoom đã qua giờ bắt đầu → hủy (không còn ý nghĩa thử lại).
    BuoiHoc.objects.filter(trang_thai=TT.LOI_ZOOM, bat_dau__lt=now).update(
        trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.ADMIN_HUY, kiem_tra_ghi_chu="Lỗi Zoom, không tạo được phòng")
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
    """Kiểm tra các buổi đã xác nhận: lấy người tham gia + bản ghi từ Zoom. Trả về số buổi đã xử lý."""
    now = now or timezone.now()
    zoom = lay_zoom_client()
    da_xu_ly = 0
    ds = BuoiHoc.objects.filter(trang_thai=TT.HOAN_TAT, kiem_tra=BuoiHoc.KiemTra.CHUA_KIEM_TRA,
                                bat_dau__gte=now - timedelta(days=NV["NGAY_MO_LAI_TOI_DA"])).exclude(zoom_meeting_id="")
    for b in ds.select_related("gia_su", "hoc_vien", "yeu_cau__mon_hoc"):
        if b.ket_thuc + timedelta(minutes=30) > now:
            continue  # Zoom cần thời gian tổng hợp báo cáo
        try:
            nguoi = zoom.lay_nguoi_tham_gia(b.zoom_meeting_id)
        except ZoomError as exc:
            logger.info("Hậu kiểm %s chưa lấy được dữ liệu: %s", b.ma, exc)
            continue
        da_xu_ly += 1
        if nguoi is None:
            BuoiHoc.objects.filter(pk=b.pk).update(
                kiem_tra=BuoiHoc.KiemTra.KHONG_DU_LIEU,
                kiem_tra_ghi_chu="Gói Zoom không cung cấp danh sách người tham gia, buổi được giữ như gia sư xác nhận.")
            continue
        dat, chung, thuc_te = danh_gia_tham_gia(b, nguoi)
        if dat:
            BuoiHoc.objects.filter(pk=b.pk).update(kiem_tra=BuoiHoc.KiemTra.HOP_LE, phut_tham_gia_chung=chung,
                                                   thoi_luong_thuc_te=thuc_te)
            continue
        ghi_chu = (f"Gia sư và học viên cùng có mặt {chung}/{b.thoi_luong_phut} phút "
                   f"(cần ≥ {round(NV['NGUONG_THAM_GIA'] * 100)}%).")
        with transaction.atomic():
            BuoiHoc.objects.filter(pk=b.pk).update(
                trang_thai=TT.DANG_XEM_XET, kiem_tra=BuoiHoc.KiemTra.CO_VAN_DE, kiem_tra_ghi_chu=ghi_chu,
                phut_tham_gia_chung=chung, thoi_luong_thuc_te=thuc_te)
            ThuLao.objects.filter(buoi_hoc=b, trang_thai=ThuLao.TrangThai.TAM_TINH).update(
                trang_thai=ThuLao.TrangThai.TAM_GIU)
            ghi_nhat_ky(None, "Hậu kiểm: buổi có vấn đề", b.ma, ghi_chu)
        gui_email(b.gia_su, f"Buổi học {b.ma} đang được xem xét",
                  f"Buổi {b.yeu_cau.mon_hoc} với {b.hoc_vien.ho_ten} lúc {timezone.localtime(b.bat_dau):%H:%M %d/%m} "
                  f"chưa đạt kiểm tra tham gia Zoom: {ghi_chu}\nThù lao buổi này tạm giữ cho tới khi Admin xem xét. "
                  "Nếu có lý do (mất mạng, đổi thiết bị…), hãy phản hồi email này cho trung tâm.", buoi_hoc=b)

    # Bản ghi (chỉ buổi phụ huynh đồng ý ghi hình).
    cho = BuoiHoc.objects.filter(trang_thai__in=[TT.HOAN_TAT, TT.DANG_XEM_XET],
                                 ban_ghi_trang_thai=BuoiHoc.BanGhi.CHO_XU_LY).exclude(zoom_meeting_id="")
    for b in cho:
        if b.ket_thuc + timedelta(minutes=30) > now:
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
