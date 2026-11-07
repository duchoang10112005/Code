"""Nghiệp vụ hồ sơ gia sư – tiến trình 2.0 trên DFD (PB-04; BRULE-09, BRULE-10).

Quy tắc:
- Gia sư tự cập nhật kinh nghiệm, lịch rảnh và ĐĂNG KÝ môn (trạng thái Chờ duyệt).
- Gia sư KHÔNG sửa/xóa được môn đã duyệt; chỉ rút được môn đang chờ hoặc bị từ chối.
- Chỉ Admin duyệt / từ chối / thu hồi môn và đổi trạng thái hồ sơ.
- Hồ sơ chỉ được chuyển sang "Đang hoạt động" khi có ít nhất 1 môn đã duyệt.
Mọi thao tác của Admin đều ghi nhật ký (D9) và gửi email báo cho gia sư.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import HoSoGiaSu, LichRanh, MonGiaSu
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email


# ---------- Phía gia sư ----------------------------------------------------
def dang_ky_mon(ho_so, mon_hoc, cap_do):
    mg, tao_moi = MonGiaSu.objects.get_or_create(
        ho_so=ho_so, mon_hoc=mon_hoc,
        defaults={"cap_do": cap_do, "trang_thai": MonGiaSu.TrangThai.CHO_DUYET},
    )
    if not tao_moi:
        if mg.trang_thai == MonGiaSu.TrangThai.TU_CHOI:
            # Đăng ký lại môn từng bị từ chối → quay về chờ duyệt.
            mg.cap_do, mg.trang_thai, mg.ghi_chu_duyet = cap_do, MonGiaSu.TrangThai.CHO_DUYET, ""
            mg.duyet_boi, mg.duyet_luc = None, None
            mg.save()
        else:
            raise ValidationError(f"Bạn đã đăng ký môn {mon_hoc} ({mg.get_trang_thai_display().lower()}).")
    return mg


def rut_mon(ho_so, mon_gia_su):
    if mon_gia_su.ho_so_id != ho_so.pk:
        raise ValidationError("Môn này không thuộc hồ sơ của bạn.")
    if mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_DUYET:
        raise ValidationError("Môn đã được duyệt không thể tự rút. Vui lòng liên hệ Admin để xét duyệt lại.")
    mon_gia_su.delete()


def them_lich_ranh(ho_so, thu, tu_gio, den_gio):
    if den_gio <= tu_gio:
        raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")
    trung = ho_so.lich_ranh.filter(thu=thu, tu_gio__lt=den_gio, den_gio__gt=tu_gio).first()
    if trung:
        raise ValidationError(f"Khung giờ bị trùng với khung đã có: {trung}.")
    return LichRanh.objects.create(ho_so=ho_so, thu=thu, tu_gio=tu_gio, den_gio=den_gio)


# ---------- Phía Admin -----------------------------------------------------
def _bao_gia_su(ho_so, tieu_de, noi_dung):
    gui_email(ho_so.user, tieu_de, f"Chào {ho_so.user.ho_ten},\n\n{noi_dung}\n\nTrung tâm Gia sư Trực tuyến")


@transaction.atomic
def duyet_mon(admin, mon_gia_su, ghi_chu=""):
    mon_gia_su.trang_thai = MonGiaSu.TrangThai.DA_DUYET
    mon_gia_su.duyet_boi, mon_gia_su.duyet_luc = admin, timezone.now()
    mon_gia_su.ghi_chu_duyet = ghi_chu
    mon_gia_su.save()
    ghi_nhat_ky(admin, "Duyệt môn dạy", mon_gia_su.ho_so.user.username, f"{mon_gia_su.mon_hoc} – {mon_gia_su.cap_do}")
    _bao_gia_su(mon_gia_su.ho_so, f"Môn {mon_gia_su.mon_hoc} đã được duyệt",
                f"Môn {mon_gia_su.mon_hoc} ({mon_gia_su.cap_do or 'không ghi cấp độ'}) của bạn đã được duyệt. "
                "Từ nay bạn có thể nhận lời mời dạy môn này.")


@transaction.atomic
def tu_choi_mon(admin, mon_gia_su, ly_do):
    if not ly_do.strip():
        raise ValidationError("Cần ghi lý do từ chối để gia sư biết cách bổ sung.")
    da_duyet_truoc = mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_DUYET
    mon_gia_su.trang_thai = MonGiaSu.TrangThai.TU_CHOI
    mon_gia_su.duyet_boi, mon_gia_su.duyet_luc = admin, timezone.now()
    mon_gia_su.ghi_chu_duyet = ly_do
    mon_gia_su.save()
    hanh_dong = "Thu hồi môn đã duyệt" if da_duyet_truoc else "Từ chối môn dạy"
    ghi_nhat_ky(admin, hanh_dong, mon_gia_su.ho_so.user.username, f"{mon_gia_su.mon_hoc}: {ly_do}")
    _bao_gia_su(mon_gia_su.ho_so, f"Môn {mon_gia_su.mon_hoc} chưa được duyệt",
                f"Môn {mon_gia_su.mon_hoc} của bạn {'đã bị thu hồi' if da_duyet_truoc else 'chưa được duyệt'}.\n"
                f"Lý do: {ly_do}\nBạn có thể bổ sung thông tin và đăng ký lại trong mục Hồ sơ của tôi.")
    # Hồ sơ đang hoạt động mà không còn môn nào được duyệt → tạm ngừng.
    ho_so = mon_gia_su.ho_so
    if ho_so.trang_thai == HoSoGiaSu.TrangThai.HOAT_DONG and not ho_so.mon_day.filter(
        trang_thai=MonGiaSu.TrangThai.DA_DUYET
    ).exists():
        ho_so.trang_thai = HoSoGiaSu.TrangThai.TAM_NGUNG
        ho_so.save(update_fields=["trang_thai"])
        ghi_nhat_ky(admin, "Tự tạm ngừng hồ sơ", ho_so.user.username, "Không còn môn nào được duyệt")


@transaction.atomic
def doi_trang_thai_ho_so(admin, ho_so, trang_thai_moi):
    if trang_thai_moi == HoSoGiaSu.TrangThai.HOAT_DONG and not ho_so.mon_day.filter(
        trang_thai=MonGiaSu.TrangThai.DA_DUYET
    ).exists():
        raise ValidationError("Cần duyệt ít nhất 1 môn trước khi cho gia sư hoạt động.")
    cu = ho_so.get_trang_thai_display()
    ho_so.trang_thai = trang_thai_moi
    ho_so.save(update_fields=["trang_thai"])
    ghi_nhat_ky(admin, "Đổi trạng thái hồ sơ gia sư", ho_so.user.username, f"{cu} → {ho_so.get_trang_thai_display()}")
    _bao_gia_su(ho_so, "Cập nhật trạng thái hồ sơ",
                f"Hồ sơ gia sư của bạn chuyển sang trạng thái: {ho_so.get_trang_thai_display()}.")
