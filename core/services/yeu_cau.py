"""Nghiệp vụ yêu cầu học tập & lời mời nhận lớp – tiến trình 3.0 trên DFD (3.1–3.4).

Backlog: PB-02, PB-03, PB-05, PB-06, PB-22, PB-30. Quy tắc: BRULE-11, BRULE-12.

Trạng thái yêu cầu:  MOI →(gửi lời mời)→ DANG_TIM →(Accept hợp lệ đầu tiên)→ DA_PHAN_CONG ; MOI/DANG_TIM → DONG
Trạng thái lời mời:  CHO → ACCEPTED | REJECTED | VOIDED | HET_HAN

"Accept hợp lệ đầu tiên thắng" dùng CẬP NHẬT CÓ ĐIỀU KIỆN (UPDATE … WHERE trang_thai = …):
database chỉ cho đúng một câu UPDATE khớp điều kiện, nên hai gia sư bấm cùng lúc
cũng chỉ một người được phân công — kể cả trên SQLite (không có khóa dòng).
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from core.models import HoSoGiaSu, KhoaHoc, LoiMoi, MonGiaSu, User, YeuCauHocTap
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email

YC = YeuCauHocTap.TrangThai
LM = LoiMoi.TrangThai


# =============================================================================
# Tiện ích
# =============================================================================
def quet_loi_moi_het_han():
    """PB-30: lời mời quá hạn 24h → HET_HAN. Gọi "lười" ở đầu các trang liên quan."""
    return LoiMoi.objects.filter(trang_thai=LM.CHO, het_han_luc__lte=timezone.now()).update(trang_thai=LM.HET_HAN)


def gia_su_du_dieu_kien(mon_hoc):
    """BRULE-11: hồ sơ đang hoạt động, tài khoản không bị khóa, có môn ĐÃ DUYỆT trùng môn yêu cầu."""
    return (HoSoGiaSu.objects
            .filter(trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG, user__is_active=True,
                    user__vai_tro=User.VaiTro.GIA_SU,
                    mon_day__mon_hoc=mon_hoc, mon_day__trang_thai=MonGiaSu.TrangThai.DA_DUYET)
            .select_related("user").distinct())


def la_du_dieu_kien(user, mon_hoc):
    return gia_su_du_dieu_kien(mon_hoc).filter(user=user).exists()


# =============================================================================
# 3.1 Tiếp nhận yêu cầu
# =============================================================================
@transaction.atomic
def tao_yeu_cau(nvts, hoc_vien, du_lieu):
    """hoc_vien: HocVien đã lưu (mới hoặc có sẵn). du_lieu: cleaned_data của YeuCauForm."""
    yc = YeuCauHocTap.objects.create(hoc_vien=hoc_vien, tao_boi=nvts, trang_thai=YC.MOI, **du_lieu)
    ghi_nhat_ky(nvts, "Tiếp nhận yêu cầu học tập", str(yc), f"Học viên {hoc_vien}, môn {yc.mon_hoc}")
    return yc


# =============================================================================
# 3.2 Đề xuất gia sư phù hợp (theo quy tắc, không dùng AI – PB-05)
# =============================================================================
def de_xuat_gia_su(yeu_cau):
    """Trả về danh sách dict đã sắp xếp: trùng nhiều ngày rảnh trước → đang dạy ít khóa trước → tên."""
    quet_loi_moi_het_han()
    thu_can = set(yeu_cau.thu_mong_muon or [])
    ds = (gia_su_du_dieu_kien(yeu_cau.mon_hoc)
          .annotate(so_khoa=Count("user__khoa_hoc_phu_trach",
                                  filter=Q(user__khoa_hoc_phu_trach__trang_thai=KhoaHoc.TrangThai.DANG_HOC),
                                  distinct=True))
          .prefetch_related("lich_ranh", "mon_day__mon_hoc"))
    loi_moi = {lm.gia_su_id: lm for lm in yeu_cau.loi_moi.order_by("gui_luc")}  # lời mời gần nhất mỗi gia sư

    ket_qua = []
    for hs in ds:
        thu_ranh = {l.thu for l in hs.lich_ranh.all()}
        mon = next(m for m in hs.mon_day.all() if m.mon_hoc_id == yeu_cau.mon_hoc_id)
        lm = loi_moi.get(hs.user_id)
        ket_qua.append({
            "ho_so": hs,
            "mon": mon,
            "lich_ranh": list(hs.lich_ranh.all()),
            "thu_trung": sorted(thu_ranh & thu_can),
            "so_khoa": hs.so_khoa,
            "loi_moi": lm,
            "dang_cho": bool(lm and lm.trang_thai == LM.CHO),
        })
    ket_qua.sort(key=lambda x: (-len(x["thu_trung"]), x["so_khoa"], x["ho_so"].user.ho_ten))
    return ket_qua


# =============================================================================
# 3.3 Gửi lời mời nhận lớp
# =============================================================================
def gui_loi_moi(nvts, yeu_cau, ds_user_id):
    if yeu_cau.trang_thai not in (YC.MOI, YC.DANG_TIM):
        raise ValidationError("Chỉ gửi lời mời cho yêu cầu đang Mới hoặc Đang tìm gia sư.")
    if not ds_user_id:
        raise ValidationError("Hãy chọn ít nhất một gia sư.")
    quet_loi_moi_het_han()

    hop_le = gia_su_du_dieu_kien(yeu_cau.mon_hoc).filter(user_id__in=ds_user_id)
    da_moi = set(yeu_cau.loi_moi.filter(trang_thai=LM.CHO).values_list("gia_su_id", flat=True))
    moi = []
    with transaction.atomic():
        for hs in hop_le:
            if hs.user_id in da_moi:
                continue
            moi.append(LoiMoi.objects.create(yeu_cau=yeu_cau, gia_su=hs.user, gui_boi=nvts))
        if moi:
            YeuCauHocTap.objects.filter(pk=yeu_cau.pk, trang_thai=YC.MOI).update(
                trang_thai=YC.DANG_TIM, cap_nhat_luc=timezone.now())
            ghi_nhat_ky(nvts, "Gửi lời mời nhận lớp", str(yeu_cau),
                        "Gửi tới: " + ", ".join(lm.gia_su.ho_ten for lm in moi))
    for lm in moi:
        gui_email(lm.gia_su, f"Lời mời nhận lớp {yeu_cau.mon_hoc} – {yeu_cau.trinh_do}",
                  f"Chào {lm.gia_su.ho_ten},\n\nTrung tâm mời bạn nhận lớp {yeu_cau.mon_hoc} ({yeu_cau.trinh_do}).\n"
                  f"Mục tiêu: {yeu_cau.muc_tieu}\nThời gian mong muốn: {yeu_cau.ten_thu_mong_muon} – {yeu_cau.lich_mong_muon}\n\n"
                  f"Lời mời có hiệu lực đến {timezone.localtime(lm.het_han_luc):%H:%M %d/%m/%Y}. "
                  f"Vào mục Lời mời nhận lớp để phản hồi ({reverse('loi_moi_cua_toi')}).\n\nTrung tâm Gia sư Trực tuyến")
    yeu_cau.refresh_from_db()
    bo_qua = len(ds_user_id) - len(moi)
    return moi, bo_qua


# =============================================================================
# 3.4 Xử lý phản hồi nhận lớp
# =============================================================================
class _DaCoNguoiNhan(Exception):
    pass


def chap_nhan(gia_su, loi_moi):
    """Accept hợp lệ đầu tiên thắng (BRULE-12, PB-22)."""
    now = timezone.now()
    yc = loi_moi.yeu_cau
    if loi_moi.gia_su_id != gia_su.pk:
        raise ValidationError("Lời mời này không phải của bạn.")
    if not la_du_dieu_kien(gia_su, yc.mon_hoc):
        raise ValidationError("Bạn chưa đủ điều kiện nhận lớp môn này "
                              "(hồ sơ đang tạm ngừng hoặc môn chưa được duyệt).")
    try:
        with transaction.atomic():
            n = LoiMoi.objects.filter(pk=loi_moi.pk, trang_thai=LM.CHO, het_han_luc__gt=now).update(
                trang_thai=LM.ACCEPTED, phan_hoi_luc=now)
            if n == 0:
                raise ValidationError("Lời mời không còn hiệu lực (đã hết hạn, đã phản hồi hoặc đã bị hủy).")
            n = YeuCauHocTap.objects.filter(pk=yc.pk, trang_thai=YC.DANG_TIM, gia_su__isnull=True).update(
                trang_thai=YC.DA_PHAN_CONG, gia_su=gia_su, phan_cong_luc=now, cap_nhat_luc=now)
            if n == 0:
                raise _DaCoNguoiNhan
            LoiMoi.objects.filter(yeu_cau=yc, trang_thai=LM.CHO).update(trang_thai=LM.VOIDED, phan_hoi_luc=now)
            ghi_nhat_ky(gia_su, "Nhận lớp (Accept)", str(yc), f"Gia sư {gia_su.ho_ten} được phân công")
    except _DaCoNguoiNhan:
        LoiMoi.objects.filter(pk=loi_moi.pk, trang_thai=LM.CHO).update(trang_thai=LM.VOIDED, phan_hoi_luc=now)
        raise ValidationError("Lớp này đã có gia sư khác nhận trước. Cảm ơn bạn đã phản hồi.")

    yc.refresh_from_db()
    if yc.tao_boi:
        gui_email(yc.tao_boi, f"{yc} đã có gia sư nhận",
                  f"Gia sư {gia_su.ho_ten} đã nhận lớp {yc.mon_hoc} ({yc.trinh_do}) của học viên {yc.hoc_vien}.\n"
                  "Bước tiếp theo: liên hệ phụ huynh để chốt học thử hoặc đăng ký chính thức.")
    return yc


def tu_choi(gia_su, loi_moi, ly_do=""):
    now = timezone.now()
    n = LoiMoi.objects.filter(pk=loi_moi.pk, gia_su=gia_su, trang_thai=LM.CHO, het_han_luc__gt=now).update(
        trang_thai=LM.REJECTED, phan_hoi_luc=now, ly_do_tu_choi=ly_do.strip()[:300])
    if n == 0:
        raise ValidationError("Lời mời không còn hiệu lực.")
    ghi_nhat_ky(gia_su, "Từ chối lời mời", str(loi_moi.yeu_cau), ly_do)


def dong_yeu_cau(nvts, yeu_cau, ly_do):
    if not ly_do.strip():
        raise ValidationError("Cần ghi lý do đóng yêu cầu.")
    now = timezone.now()
    with transaction.atomic():
        n = YeuCauHocTap.objects.filter(pk=yeu_cau.pk, trang_thai__in=[YC.MOI, YC.DANG_TIM]).update(
            trang_thai=YC.DONG, ly_do_dong=ly_do.strip()[:300], cap_nhat_luc=now)
        if n == 0:
            raise ValidationError("Chỉ đóng được yêu cầu chưa được phân công gia sư.")
        LoiMoi.objects.filter(yeu_cau=yeu_cau, trang_thai=LM.CHO).update(trang_thai=LM.VOIDED, phan_hoi_luc=now)
        ghi_nhat_ky(nvts, "Đóng yêu cầu học tập", str(yeu_cau), ly_do)
    yeu_cau.refresh_from_db()
