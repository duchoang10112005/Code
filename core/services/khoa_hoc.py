"""Nghiệp vụ khóa học – tiến trình 4.0 trên DFD (4.1 ghi kết quả học thử, 4.2 tạo khóa, 4.3 theo dõi).

Backlog: PB-07 (phần kết quả học thử), PB-08, PB-09, PB-10. Quy tắc: BRULE-13..16.

Từ yêu cầu DA_PHAN_CONG:
  Nhánh A – chưa học thử → tạo khóa ngay → CHINH_THUC
  Nhánh B – có buổi học thử HOÀN TẤT với gia sư hiện tại → ghi kết quả:
      TIEP_TUC        → HOC_THU_XONG → tạo khóa → CHINH_THUC
      TIM_GIA_SU_KHAC → DANG_TIM (bỏ gán gia sư, NVTS mời người khác)
      DUNG            → DONG
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import BuoiHoc, KhoaHoc, YeuCauHocTap
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email
from core.services.bang_gia import tinh_gia
from core.services.tien_ich import dinh_dang_phan_tram, dinh_dang_tien
from core.services.yeu_cau import la_du_dieu_kien

YC = YeuCauHocTap.TrangThai
KQ = YeuCauHocTap.KetQuaHocThu
KH = KhoaHoc.TrangThai


# =============================================================================
# Tiện ích
# =============================================================================
def buoi_hoc_thu(yc):
    """Các buổi học thử của yêu cầu VỚI GIA SƯ HIỆN TẠI (đổi gia sư thì học thử cũ không còn tính)."""
    if not yc.gia_su_id:
        return BuoiHoc.objects.none()
    return yc.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su_id=yc.gia_su_id)


def buoi_hoc_thu_hoan_tat(yc):
    return buoi_hoc_thu(yc).filter(trang_thai=BuoiHoc.TrangThai.HOAN_TAT).order_by("-bat_dau").first()


def buoi_hoc_thu_gan_nhat(yc):
    """Buổi học thử chưa hủy gần nhất với gia sư hiện tại (để hiện trên giao diện)."""
    return buoi_hoc_thu(yc).exclude(trang_thai=BuoiHoc.TrangThai.DA_HUY).order_by("-bat_dau").first()


def huy_buoi_thu_chua_hoc(yc, gia_su, ly_do):
    """Hủy các buổi học thử chưa diễn ra của một gia sư (khi đổi gia sư / đóng yêu cầu).
    Phòng Zoom tương ứng sẽ được xóa khi Phần 5 nối Zoom thật."""
    return yc.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=gia_su,
                              trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO).update(
        trang_thai=BuoiHoc.TrangThai.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.ADMIN_HUY,
        kiem_tra_ghi_chu=ly_do[:300])


def co_buoi_hoc_thu(yc):
    """Đã có buổi học thử (chưa hủy) với gia sư hiện tại → không đi nhánh A được nữa."""
    return buoi_hoc_thu(yc).exclude(trang_thai=BuoiHoc.TrangThai.DA_HUY).exists()


def co_the_tao_khoa(yc):
    if yc.trang_thai == YC.DA_PHAN_CONG:
        return not co_buoi_hoc_thu(yc)  # nhánh A
    return yc.trang_thai == YC.HOC_THU_XONG and yc.ket_qua_hoc_thu == KQ.TIEP_TUC


# =============================================================================
# 4.1 Ghi nhận kết quả học thử
# =============================================================================
def ghi_ket_qua_hoc_thu(nvts, yc, ket_qua, ghi_chu=""):
    ghi_chu = (ghi_chu or "").strip()[:300]
    if ket_qua not in KQ.values:
        raise ValidationError("Kết quả học thử không hợp lệ.")
    if not buoi_hoc_thu_hoan_tat(yc):
        raise ValidationError("Chưa có buổi học thử hoàn tất với gia sư hiện tại, chưa ghi kết quả được.")
    if ket_qua == KQ.DUNG and not ghi_chu:
        raise ValidationError("Cần ghi lý do phụ huynh không tiếp tục.")

    gia_su = yc.gia_su
    now = timezone.now()
    cap_nhat = {"ket_qua_hoc_thu": ket_qua, "ghi_chu_hoc_thu": ghi_chu, "cap_nhat_luc": now}
    if ket_qua == KQ.TIEP_TUC:
        cap_nhat["trang_thai"] = YC.HOC_THU_XONG
    elif ket_qua == KQ.TIM_GIA_SU_KHAC:
        cap_nhat.update(trang_thai=YC.DANG_TIM, gia_su=None, phan_cong_luc=None)
    else:
        cap_nhat.update(trang_thai=YC.DONG, ly_do_dong=ghi_chu)

    with transaction.atomic():
        n = YeuCauHocTap.objects.filter(pk=yc.pk, trang_thai=YC.DA_PHAN_CONG).update(**cap_nhat)
        if n == 0:
            raise ValidationError("Yêu cầu không còn ở trạng thái Đã phân công.")
        ghi_nhat_ky(nvts, "Ghi kết quả học thử", yc.ma, f"{KQ(ket_qua).label}. {ghi_chu}".strip())
        if ket_qua != KQ.TIEP_TUC and gia_su:
            huy_buoi_thu_chua_hoc(yc, gia_su, f"Kết quả học thử: {KQ(ket_qua).label}")
    yc.refresh_from_db()

    if ket_qua != KQ.TIEP_TUC and gia_su:
        gui_email(gia_su, f"Kết quả học thử {yc.ma}",
                  f"Sau buổi học thử môn {yc.mon_hoc} với học viên {yc.hoc_vien}, phụ huynh chọn: "
                  f"{KQ(ket_qua).label}.\nCảm ơn bạn đã dạy thử.")
    return yc


# =============================================================================
# 4.2 Tạo khóa học chính thức
# =============================================================================
def tao_khoa_hoc(nvts, yc, so_buoi, thoi_luong_phut):
    """NVTS chỉ chọn gói (10/20/30 buổi) và khung giờ (1h/1,5h/2h); giá do hệ thống tính từ Bảng giá
    rồi CHỤP LẠI vào khóa (Admin đổi bảng giá sau này không ảnh hưởng khóa đã tạo)."""
    yc.refresh_from_db()
    if yc.trang_thai == YC.DA_PHAN_CONG and co_buoi_hoc_thu(yc):
        raise ValidationError("Yêu cầu này đã học thử: cần ghi kết quả \"Tiếp tục\" trước khi tạo khóa.")
    if yc.gia_su_id and not la_du_dieu_kien(yc.gia_su, yc.mon_hoc):
        raise ValidationError(f"Gia sư {yc.gia_su.ho_ten} không còn đủ điều kiện dạy môn {yc.mon_hoc} "
                              "(bị khóa, tạm ngừng hoặc bị thu hồi môn).")
    if not co_the_tao_khoa(yc):
        raise ValidationError("Chỉ tạo khóa cho yêu cầu đã phân công (đăng ký thẳng) "
                              "hoặc đã học thử với kết quả Tiếp tục.")
    bao_gia = tinh_gia(yc.mon_hoc, so_buoi, thoi_luong_phut)
    trang_thai_cu = yc.trang_thai
    try:
        with transaction.atomic():
            n = YeuCauHocTap.objects.filter(pk=yc.pk, trang_thai=trang_thai_cu).update(
                trang_thai=YC.CHINH_THUC, cap_nhat_luc=timezone.now())
            if n == 0:
                raise ValidationError("Yêu cầu vừa được người khác cập nhật, vui lòng tải lại trang.")
            khoa = KhoaHoc.objects.create(
                yeu_cau=yc, hoc_vien=yc.hoc_vien, gia_su=yc.gia_su, tao_boi=nvts,
                so_buoi_dang_ky=bao_gia.so_buoi, thoi_luong_phut=bao_gia.thoi_luong_phut,
                don_gia_gio=bao_gia.don_gia_gio, hoc_phi_goc_moi_buoi=bao_gia.hoc_phi_goc,
                ty_le_giam=bao_gia.ty_le_giam, ty_le_trung_tam=bao_gia.ty_le_trung_tam,
                hoc_phi_moi_buoi=bao_gia.hoc_phi, thu_lao_moi_buoi=bao_gia.thu_lao,
                quyen_loi_goi=bao_gia.quyen_loi)
            nhanh = "nhánh A – đăng ký thẳng" if trang_thai_cu == YC.DA_PHAN_CONG else "sau học thử"
            ghi_nhat_ky(nvts, "Tạo khóa học chính thức", str(khoa),
                        f"{nhanh}; gói {khoa.so_buoi_dang_ky} buổi × {khoa.get_thoi_luong_phut_display()}, "
                        f"giảm {dinh_dang_phan_tram(khoa.ty_le_giam)} → {dinh_dang_tien(khoa.hoc_phi_moi_buoi)}/buổi; "
                        f"thù lao {dinh_dang_tien(khoa.thu_lao_moi_buoi)}/buổi")
    except IntegrityError:
        raise ValidationError("Yêu cầu này đã có khóa học.")
    gui_email(khoa.gia_su, f"Khóa học mới: {khoa}",
              f"Trung tâm đã mở khóa {yc.mon_hoc} cho học viên {yc.hoc_vien}: {khoa.so_buoi_dang_ky} buổi, "
              f"{khoa.get_thoi_luong_phut_display()}/buổi, thù lao {dinh_dang_tien(khoa.thu_lao_moi_buoi)}/buổi.\n"
              "Vào mục Lớp của tôi để xem và tạo buổi học.")
    return khoa


# =============================================================================
# Đổi trạng thái khóa (tạm dừng / tiếp tục / hủy)
# =============================================================================
CHUYEN_HOP_LE = {
    KH.TAM_DUNG: {KH.DANG_HOC},
    KH.DANG_HOC: {KH.TAM_DUNG},
    KH.HUY: {KH.DANG_HOC, KH.TAM_DUNG},
}


def doi_trang_thai_khoa(nvts, khoa, moi, ly_do=""):
    ly_do = (ly_do or "").strip()[:300]
    if moi not in CHUYEN_HOP_LE:
        raise ValidationError("Trạng thái không hợp lệ.")
    if moi in (KH.TAM_DUNG, KH.HUY) and not ly_do:
        raise ValidationError("Cần ghi lý do tạm dừng / hủy khóa.")
    cu = khoa.get_trang_thai_display()
    n = KhoaHoc.objects.filter(pk=khoa.pk, trang_thai__in=CHUYEN_HOP_LE[moi]).update(
        trang_thai=moi, ghi_chu=ly_do)
    if n == 0:
        raise ValidationError(f"Không chuyển được từ \"{cu}\" sang \"{KH(moi).label}\".")
    khoa.refresh_from_db()
    ghi_nhat_ky(nvts, "Đổi trạng thái khóa học", str(khoa), f"{cu} → {khoa.get_trang_thai_display()}. {ly_do}".strip())
    gui_email(khoa.gia_su, f"{khoa}: {khoa.get_trang_thai_display()}",
              f"Khóa {khoa} chuyển sang trạng thái {khoa.get_trang_thai_display()}." + (f"\nLý do: {ly_do}" if ly_do else ""))
    return khoa
