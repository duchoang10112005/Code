"""Nghiệp vụ yêu cầu học tập & lời mời nhận lớp – tiến trình 3.0 trên DFD (3.1–3.4).

Backlog: PB-02, PB-03, PB-05, PB-06, PB-22, PB-30. Quy tắc: BRULE-11, BRULE-12.

Trạng thái yêu cầu:  MOI →(gửi lời mời)→ DANG_TIM →(Accept hợp lệ đầu tiên)→ DA_PHAN_CONG ; MOI/DANG_TIM → DONG
Trạng thái lời mời:  CHO → ACCEPTED | REJECTED | VOIDED | HET_HAN

"Accept hợp lệ đầu tiên thắng" dùng CẬP NHẬT CÓ ĐIỀU KIỆN (UPDATE … WHERE trang_thai = …):
database chỉ cho đúng một câu UPDATE khớp điều kiện, nên hai gia sư bấm cùng lúc
cũng chỉ một người được phân công — kể cả trên SQLite (không có khóa dòng).
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from core.models import BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, LoiMoi, MonGiaSu, User, YeuCauHocTap
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email

YC = YeuCauHocTap.TrangThai
LM = LoiMoi.TrangThai
KQ = YeuCauHocTap.KetQuaHocThu


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


def huy_loi_moi_cua_gia_su(user, ly_do, mon_hoc=None):
    """Gia sư không còn đủ điều kiện (bị khóa, đổi vai trò, hồ sơ tạm ngừng, bị thu hồi môn)
    → hủy ngay các lời mời đang chờ, để NVTS thấy yêu cầu "Cần mời thêm" thay vì chờ 24h."""
    qs = LoiMoi.objects.filter(gia_su=user, trang_thai=LM.CHO)
    if mon_hoc is not None:
        qs = qs.filter(yeu_cau__mon_hoc=mon_hoc)
    n = qs.update(trang_thai=LM.VOIDED, phan_hoi_luc=timezone.now(), ly_do_tu_choi=ly_do[:300])
    if n:
        ghi_nhat_ky(None, "Hủy lời mời đang chờ", user.username, f"{n} lời mời – {ly_do}")

    # Lớp đã nhận nhưng chưa mở khóa → gỡ phân công, đưa về Đang tìm gia sư để NVTS mời người khác.
    lop = YeuCauHocTap.objects.filter(gia_su=user, trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG])
    if mon_hoc is not None:
        lop = lop.filter(mon_hoc=mon_hoc)
    ds = list(lop)
    ds_ma = [yc.ma for yc in ds]
    if ds_ma:
        BuoiHoc.objects.filter(yeu_cau__in=ds, gia_su=user, loai=BuoiHoc.Loai.HOC_THU,
                               trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO).update(
            trang_thai=BuoiHoc.TrangThai.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.ADMIN_HUY)
        YeuCauHocTap.objects.filter(pk__in=[yc.pk for yc in ds]).update(trang_thai=YC.DANG_TIM, gia_su=None, phan_cong_luc=None, ket_qua_hoc_thu="",
                   cap_nhat_luc=timezone.now())
        ghi_nhat_ky(None, "Gỡ phân công gia sư", user.username, f"{', '.join(ds_ma)} – {ly_do}")
    return n


# =============================================================================
# 3.1 Tiếp nhận yêu cầu
# =============================================================================
@transaction.atomic
def tao_yeu_cau(nvts, hoc_vien, du_lieu):
    """hoc_vien: HocVien đã lưu (mới hoặc có sẵn). du_lieu: cleaned_data của YeuCauForm (SD-05)."""
    if hoc_vien.tuyen_sinh_phu_trach_id is None:
        HocVien.objects.filter(pk=hoc_vien.pk).update(tuyen_sinh_phu_trach=nvts)
    yc = YeuCauHocTap.objects.create(hoc_vien=hoc_vien, tao_boi=nvts, trang_thai=YC.MOI, **du_lieu)
    ghi_nhat_ky(nvts, "Tiếp nhận yêu cầu học tập", str(yc), f"Học viên {hoc_vien}, môn {yc.mon_hoc}")
    return yc


# =============================================================================
# 3.2 Đề xuất gia sư phù hợp (theo quy tắc, không dùng AI – PB-05)
# =============================================================================
def _ds_ung_vien(mon_hoc):
    return (gia_su_du_dieu_kien(mon_hoc)
            .annotate(so_khoa=Count("user__khoa_hoc_phu_trach",
                                    filter=Q(user__khoa_hoc_phu_trach__trang_thai=KhoaHoc.TrangThai.DANG_HOC),
                                    distinct=True))
            .prefetch_related("lich_ranh", "mon_day__mon_hoc", "mon_day__cap_do_duyet"))


def cham_diem(hs, mon_hoc_id, cap_do_id, khung_can, thu_can):
    """Điểm khớp 0–100 (chỉ để sắp xếp / giải thích, không phải AI – PB-05):
    40 đúng môn + 20 đúng cấp độ + 30 × tỉ lệ khung giờ trùng + 10 nếu còn chỗ nhận lớp."""
    mon = next(m for m in hs.mon_day.all() if m.mon_hoc_id == mon_hoc_id)
    duyet = {c.pk for c in mon.cap_do_duyet.all()}
    dung_cap_do = True if not cap_do_id or not duyet else cap_do_id in duyet
    ranh_khung = {f"{l.thu}-{l.khung}" for l in hs.lich_ranh.all() if l.khung}
    thu_ranh = {l.thu for l in hs.lich_ranh.all()}
    if khung_can:
        trung, can = len(set(khung_can) & ranh_khung), len(set(khung_can))
    else:
        trung, can = len(set(thu_can) & thu_ranh), len(set(thu_can))
    con_cho = hs.so_khoa < (hs.so_lop_toi_da or 4)
    diem = 40 + (20 if dung_cap_do else 0) + (round(30 * trung / can) if can else 0) + (10 if con_cho else 0)
    return {"mon": mon, "diem": diem, "vong": round(88 * (1 - diem / 100), 1), "trung": trung, "can": can, "dung_cap_do": dung_cap_do, "con_cho": con_cho,
            "thu_trung": sorted(thu_ranh & set(thu_can)), "tam_nghi": hs.dang_tam_nghi,
            "chi_tiet": {"dung_mon": True, "dung_cap_do": dung_cap_do, "trung_gio": f"{trung}/{can}",
                         "dang_nhan_lop": con_cho}}


def de_xuat_gia_su(yeu_cau):
    """SD-06: danh sách gia sư đủ điều kiện kèm điểm khớp, sắp giảm dần (tạm nghỉ vẫn hiện, gắn cờ, xếp cuối)."""
    quet_loi_moi_het_han()
    loi_moi = {lm.gia_su_id: lm for lm in yeu_cau.loi_moi.order_by("gui_luc")}  # lời mời gần nhất mỗi gia sư
    ket_qua = []
    for hs in _ds_ung_vien(yeu_cau.mon_hoc):
        d = cham_diem(hs, yeu_cau.mon_hoc_id, yeu_cau.cap_do_id, yeu_cau.khung_mong_muon, yeu_cau.thu_mong_muon or [])
        lm = loi_moi.get(hs.user_id)
        d.update({"ho_so": hs, "lich_ranh": list(hs.lich_ranh.all()), "so_khoa": hs.so_khoa, "loi_moi": lm,
                  "dang_cho": bool(lm and lm.trang_thai == LM.CHO)})
        ket_qua.append(d)
    ket_qua.sort(key=lambda x: (x["tam_nghi"], -x["diem"], x["so_khoa"], x["ho_so"].user.ho_ten))
    if ket_qua and not ket_qua[0]["tam_nghi"]:
        ket_qua[0]["khop_nhat"] = True
    return ket_qua


def dem_gia_su_phu_hop(mon_hoc, cap_do_id=None, khung=None):
    """Đếm nhanh cho khung "Xem trước" khi tạo yêu cầu: (đủ điều kiện, trùng ≥ 1 khung giờ)."""
    ds = [cham_diem(hs, mon_hoc.pk, cap_do_id, khung or [], []) for hs in _ds_ung_vien(mon_hoc) if not hs.dang_tam_nghi]
    return len(ds), sum(1 for d in ds if d["trung"] and d["dung_cap_do"])


# =============================================================================
# 3.3 Gửi lời mời nhận lớp
# =============================================================================
def gui_email_loi_moi(lm):
    """Email mời nhận lớp (HTML) – nút "Xem lời mời" mở thẳng lời mời này để Nhận lớp / Từ chối.
    Chưa đăng nhập thì hệ thống đưa qua trang đăng nhập rồi quay lại đúng lời mời."""
    from django.template.loader import render_to_string
    yc = lm.yeu_cau
    hv = yc.hoc_vien
    url = f"{settings.SITE_URL}{reverse('loi_moi_cua_toi')}?chon={lm.pk}"
    het = timezone.localtime(lm.het_han_luc)
    lich = yc.lich_mong_muon or yc.ten_thu_mong_muon
    dong = [("Mã lớp", yc.ma),
            ("Môn", f"{yc.mon_hoc}" + (f" · {yc.cap_do.ten}" if yc.cap_do_id else "") + (f" · {yc.trinh_do}" if yc.trinh_do else "")),
            ("Thù lao dự kiến", f"{yc.thu_lao_du_kien:,}đ/buổi".replace(",", ".") if yc.thu_lao_du_kien else "Thỏa thuận khi mở khóa"),
            ("Thời gian mong muốn", lich),
            ("Học viên", hv.ho_ten + (f" · {hv.get_gioi_tinh_display()}" if hv.gioi_tinh else "") + (f" · {hv.lop}" if hv.lop else "")),
            ("Mục tiêu", yc.muc_tieu),
            ("Ghi chú", yc.ghi_chu or "—"),
            ("Hạn phản hồi", f"{het:%H:%M} ngày {het:%d/%m/%Y}")]
    van_ban = (f"Chào {lm.gia_su.ho_ten},\n\nTrung tâm có lớp mới phù hợp với bạn:\n"
               + "\n".join(f"{k}: {v}" for k, v in dong)
               + f"\n\nXem và Nhận lớp / Từ chối tại: {url}\n"
               "Người nhận hợp lệ đầu tiên được lớp.\n\nTrung tâm Gia sư Trực tuyến")
    html = render_to_string("email/loi_moi.html", {"gs": lm.gia_su, "dong": dong, "url": url, "het": het})
    gui_email(lm.gia_su, f"Lời mời nhận lớp {yc.mon_hoc} {yc.trinh_do} – {yc.ma}", van_ban, html=html)


def gui_loi_moi(nvts, yeu_cau, ds_user_id):
    ds_user_id = set(ds_user_id)  # bỏ id trùng trong POST
    if not ds_user_id:
        raise ValidationError("Hãy chọn ít nhất một gia sư.")
    quet_loi_moi_het_han()

    hop_le = [hs for hs in _ds_ung_vien(yeu_cau.mon_hoc).filter(user_id__in=ds_user_id) if not hs.dang_tam_nghi]
    moi = []
    with transaction.atomic():
        # Kiểm tra lại trạng thái NGAY trong transaction (đối tượng truyền vào có thể đã cũ:
        # yêu cầu vừa được Accept hoặc bị đóng ở một request khác).
        if not YeuCauHocTap.objects.filter(pk=yeu_cau.pk, trang_thai__in=[YC.MOI, YC.DANG_TIM]).exists():
            raise ValidationError("Chỉ gửi lời mời cho yêu cầu đang Mới hoặc Đang mời gia sư.")
        da_moi = set(yeu_cau.loi_moi.filter(trang_thai=LM.CHO).values_list("gia_su_id", flat=True))
        for hs in hop_le:
            if hs.user_id in da_moi:
                continue
            try:
                with transaction.atomic():  # savepoint: hai NVTS gửi cùng lúc → ràng buộc DB chặn bản thứ hai
                    d = cham_diem(hs, yeu_cau.mon_hoc_id, yeu_cau.cap_do_id, yeu_cau.khung_mong_muon,
                                  yeu_cau.thu_mong_muon or [])
                    moi.append(LoiMoi.objects.create(yeu_cau=yeu_cau, gia_su=hs.user, gui_boi=nvts,
                                                     diem_khop=d["diem"], chi_tiet_khop=d["chi_tiet"]))
            except IntegrityError:
                continue
        if moi:
            YeuCauHocTap.objects.filter(pk=yeu_cau.pk, trang_thai=YC.MOI).update(
                trang_thai=YC.DANG_TIM, cap_nhat_luc=timezone.now())
            ghi_nhat_ky(nvts, "Gửi lời mời nhận lớp", str(yeu_cau),
                        "Gửi tới: " + ", ".join(lm.gia_su.ho_ten for lm in moi))
    from core.services.thong_bao import thong_bao
    for lm in moi:
        thong_bao(lm.gia_su, f"Lời mời mới: {yeu_cau.mon_hoc} {yeu_cau.trinh_do}",
                  f"{yeu_cau.hoc_vien.ho_ten} · hết hạn sau {settings.NGHIEP_VU['HAN_LOI_MOI_GIO']} giờ",
                  reverse("loi_moi_cua_toi") + f"?chon={lm.pk}", "LOI_MOI")
        gui_email_loi_moi(lm)
    yeu_cau.refresh_from_db()
    bo_qua = len(ds_user_id) - len(moi)
    return moi, bo_qua


# =============================================================================
# 3.4 Xử lý phản hồi nhận lớp
# =============================================================================
class _DaCoNguoiNhan(Exception):
    pass


def chap_nhan(gia_su, loi_moi, cam_ket=True, ghi_chu=""):
    """Accept hợp lệ đầu tiên thắng (BRULE-12, PB-22, SD-08). Giao diện bắt buộc tick cam kết."""
    now = timezone.now()
    yc = loi_moi.yeu_cau
    if loi_moi.gia_su_id != gia_su.pk:
        raise ValidationError("Lời mời này không phải của bạn.")
    if not cam_ket:
        raise ValidationError({"cam_ket": "Đánh dấu xác nhận để nhận lớp."})
    if not la_du_dieu_kien(gia_su, yc.mon_hoc):
        raise ValidationError("Bạn chưa đủ điều kiện nhận lớp môn này "
                              "(hồ sơ đang tạm ngừng hoặc môn chưa được duyệt).")
    try:
        with transaction.atomic():
            n = LoiMoi.objects.filter(pk=loi_moi.pk, trang_thai=LM.CHO, het_han_luc__gt=now).update(
                trang_thai=LM.ACCEPTED, phan_hoi_luc=now, cam_ket=True, ghi_chu_gia_su=(ghi_chu or "").strip()[:300])
            if n == 0:
                raise ValidationError("Lời mời không còn hiệu lực (đã hết hạn, đã phản hồi hoặc đã bị hủy).")
            n = YeuCauHocTap.objects.filter(pk=yc.pk, trang_thai=YC.DANG_TIM, gia_su__isnull=True).update(
                trang_thai=YC.DA_PHAN_CONG, gia_su=gia_su, phan_cong_luc=now, cap_nhat_luc=now)
            if n == 0:
                raise _DaCoNguoiNhan
            LoiMoi.objects.filter(yeu_cau=yc, trang_thai=LM.CHO).update(trang_thai=LM.VOIDED, phan_hoi_luc=now)
            ghi_nhat_ky(gia_su, "Nhận lớp (Accept)", str(yc), f"Gia sư {gia_su.ho_ten} được phân công")
            # Yêu cầu đã có khóa (đang đổi gia sư) → gia sư mới nhận lại khóa, học tiếp số buổi còn lại.
            from core.services.ngoai_le import nhan_lai_khoa
            khoa = nhan_lai_khoa(gia_su, yc)
    except _DaCoNguoiNhan:
        LoiMoi.objects.filter(pk=loi_moi.pk, trang_thai=LM.CHO).update(trang_thai=LM.VOIDED, phan_hoi_luc=now)
        yc.refresh_from_db()
        luc = f" (lúc {timezone.localtime(yc.phan_cong_luc):%H:%M})" if yc.phan_cong_luc else ""
        raise ValidationError(f"Lời mời đã vô hiệu. Một gia sư khác đã nhận lớp này trước{luc}.")

    yc.refresh_from_db()
    from django.urls import reverse
    from core.services.thong_bao import thong_bao
    thong_bao(yc.tao_boi, f"{yc.ma} đã có gia sư nhận",
              f"{gia_su.ho_ten} nhận lớp {yc.mon_hoc} – {yc.hoc_vien}"
              + (f". Lời nhắn: {ghi_chu.strip()[:120]}" if (ghi_chu or "").strip() else ""),
              reverse("yeu_cau_chi_tiet", args=[yc.pk]), "YEU_CAU")
    if yc.tao_boi and khoa:
        gui_email(yc.tao_boi, f"{khoa.ma} đã có gia sư mới",
                  f"Gia sư {gia_su.ho_ten} đã nhận khóa {yc.mon_hoc} của học viên {yc.hoc_vien}. "
                  f"Khóa đã tự học tiếp với {khoa.so_buoi_con_lai} buổi còn lại.\n"
                  "Bước tiếp theo: báo phụ huynh tên gia sư mới và lập nhóm Zalo mới.")
    elif yc.tao_boi:
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
    yc = loi_moi.yeu_cau
    ghi_nhat_ky(gia_su, "Từ chối lời mời", str(yc), ly_do)
    if yc.trang_thai == YC.DANG_TIM and not LoiMoi.objects.filter(yeu_cau=yc, trang_thai=LM.CHO).exists():
        from django.urls import reverse
        from core.services.thong_bao import thong_bao
        thong_bao(yc.tao_boi, f"{yc.ma} cần mời thêm gia sư",
                  f"{gia_su.ho_ten} đã từ chối ({ly_do.strip()[:80] or 'không ghi lý do'}); không còn lời mời nào đang chờ.",
                  reverse("yeu_cau_chi_tiet", args=[yc.pk]), "YEU_CAU")


# =============================================================================
# Lưới khớp giờ (dùng cho Lời mời nhận lớp và Đề xuất gia sư)
# =============================================================================
KHUNG = ["SANG", "CHIEU", "TOI_SOM", "TOI"]


def khung_ranh(ho_so):
    """Tập "<thu>-<khung>" gia sư đã đăng ký rảnh."""
    if ho_so is None:
        return set()
    return {f"{t}-{k}" for t, k in ho_so.lich_ranh.exclude(khung="").values_list("thu", "khung")}


def luoi_khop(ho_so, khung_mong_muon):
    """Lưới 4 khung × 7 ngày: mỗi ô "khop" (cần + rảnh), "thieu" (cần, chưa rảnh), "ranh" (rảnh khác), "".

    Trả về (hàng, số khớp, tổng cần, danh sách ô thiếu dạng "CN sáng").
    """
    from core.models import LichRanh
    ranh = khung_ranh(ho_so)
    can = set(khung_mong_muon or [])
    nhan_khung = dict(LichRanh.Khung.choices)
    thu_ngan = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    hang, thieu = [], []
    for k in KHUNG:
        o = []
        for t in range(7):
            ma = f"{t}-{k}"
            if ma in can and ma in ranh:
                o.append("khop")
            elif ma in can:
                o.append("thieu")
                thieu.append(f"{thu_ngan[t]} {nhan_khung[k].split()[0].lower()}"
                             + (" sớm" if k == "TOI_SOM" else ""))
            elif ma in ranh:
                o.append("ranh")
            else:
                o.append("")
        ten, gio = nhan_khung[k].rsplit(" ", 1)
        hang.append({"ma": k, "ten": ten, "gio": LichRanh.GIO_KHUNG[k], "o": o})
    return hang, len(can & ranh), len(can), thieu


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


# =============================================================================
# Cột "Bước tiếp theo" trên danh sách / trang chủ Tuyển sinh
# =============================================================================
def _con(td):
    phut = max(int(td.total_seconds() // 60), 0)
    g, p = divmod(phut, 60)
    return f"{g} giờ {p} phút" if g and p else (f"{g} giờ" if g else f"{p} phút")


def buoc_tiep_theo(yc, now=None):
    """dict: chu, icon, mau (xanh|cam|do|xanh_la|xam), url (tùy chọn) – việc kế tiếp Tuyển sinh cần làm."""
    from django.urls import reverse
    now = now or timezone.now()
    ct = reverse("yeu_cau_chi_tiet", args=[yc.pk])
    if yc.trang_thai == YC.MOI:
        n = gia_su_du_dieu_kien(yc.mon_hoc).count()
        return {"chu": f"Tìm gia sư · có {n} gia sư phù hợp" if n else "Chưa có gia sư đủ điều kiện môn này",
                "icon": "bi-arrow-right-circle", "mau": "xanh" if n else "do", "url": ct}
    if yc.trang_thai == YC.DANG_TIM:
        cho = [lm.het_han_luc for lm in yc.loi_moi.all() if lm.trang_thai == LM.CHO and lm.het_han_luc > now]
        if cho:
            con = min(cho) - now
            return {"chu": f"Chờ gia sư nhận · còn {_con(con)}", "icon": "bi-stopwatch",
                    "mau": "cam" if con < timedelta(hours=6) else "xam"}
        het = sum(1 for lm in yc.loi_moi.all() if lm.trang_thai in (LM.HET_HAN, LM.REJECTED))
        return {"chu": f"Mời lại · {het} lời mời đã hết hạn / từ chối" if het else "Mời thêm gia sư",
                "icon": "bi-exclamation-circle", "mau": "do", "url": ct}
    if yc.trang_thai == YC.DA_PHAN_CONG:
        if yc.dang_ky_thang:
            return {"chu": "Mở khóa học (đăng ký thẳng)", "icon": "bi-arrow-right-circle", "mau": "xanh", "url": ct}
        if yc.ket_qua_hoc_thu == KQ.CAN_THEM_THOI_GIAN and yc.nhac_goi_lai_luc:
            return {"chu": f"Gọi lại phụ huynh · hạn {timezone.localtime(yc.nhac_goi_lai_luc):%d/%m}",
                    "icon": "bi-telephone", "mau": "do" if yc.nhac_goi_lai_luc < now else "cam", "url": ct}
        thu = [b for b in yc.buoi_hoc.all() if b.loai == BuoiHoc.Loai.HOC_THU and b.gia_su_id == yc.gia_su_id
               and b.trang_thai != BuoiHoc.TrangThai.DA_HUY]
        if any(b.trang_thai == BuoiHoc.TrangThai.HOAN_TAT for b in thu):
            return {"chu": "Ghi kết quả học thử", "icon": "bi-arrow-right-circle", "mau": "xanh", "url": ct}
        if thu:
            bd = timezone.localtime(min(thu, key=lambda b: b.bat_dau).bat_dau)
            return {"chu": f"Học thử {['T2','T3','T4','T5','T6','T7','CN'][bd.weekday()]} {bd:%d/%m %H:%M}",
                    "icon": "bi-calendar3", "mau": "xam"}
        return {"chu": "Chờ gia sư tạo buổi học thử", "icon": "bi-calendar3", "mau": "xam"}
    if yc.trang_thai == YC.HOC_THU_XONG:
        return {"chu": "Mở khóa học", "icon": "bi-arrow-right-circle", "mau": "xanh", "url": ct}
    if yc.trang_thai == YC.CHINH_THUC:
        k = getattr(yc, "khoa_hoc", None)
        return {"chu": f"Đã mở {k.ma}" if k else "Đã mở khóa", "icon": "bi-check-circle", "mau": "xanh_la",
                "url": reverse("khoa_hoc_chi_tiet", args=[k.pk]) if k else None}
    return {"chu": f"Đóng: {yc.ly_do_dong[:60]}" if yc.ly_do_dong else "Đã đóng", "icon": "bi-dot", "mau": "xam"}


MAU_TRANG_THAI_YC = {"MOI": "xanh", "DANG_TIM": "cam", "DA_PHAN_CONG": "xanh_la", "HOC_THU_XONG": "tim",
                     "CHINH_THUC": "xanh_la", "DONG": "xam"}
LY_DO_DONG = ["Phụ huynh không còn nhu cầu", "Không tìm được gia sư phù hợp", "Học phí chưa phù hợp",
              "Phụ huynh không liên lạc được", "Trùng yêu cầu khác", "Lý do khác"]
