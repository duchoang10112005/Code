"""Hậu kiểm buổi học (SD-20..22, Q1): hệ thống chấm 5 tiêu chí, Tuyển sinh người mời gia sư kết luận.

Nguyên tắc "Xác nhận trước, hậu kiểm sau": xác nhận hoàn tất không chờ Zoom, thù lao tạo ngay (Tạm tính).
Chỉ khi Tuyển sinh kết luận "Có vấn đề" thì buổi mới sang Đang xem xét và thù lao bị tạm giữ.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import BuoiHoc, HauKiemBuoi, ThuLao
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email

KL = HauKiemBuoi.KetLuan
TT = BuoiHoc.TrangThai
NV = settings.NGHIEP_VU

TAB = [("can_kiem", "Cần kiểm tra"), ("canh_bao", "Có cảnh báo"), ("co_van_de", "Có vấn đề"), ("da_kiem", "Đã kiểm tra")]


# =============================================================================
# SD-20 – chấm 5 tiêu chí
# =============================================================================
def tieu_chi(hk):
    """5 tiêu chí: dict(ten, dat True/False/None (không có dữ liệu), gia_tri)."""
    b = hk.buoi_hoc
    tre_max = NV.get("TRE_TOI_DA_PHUT", 5)
    nguong = round(NV["NGUONG_THAM_GIA"] * 100)
    nx_min = NV.get("DO_DAI_NHAN_XET_TOI_THIEU", 30)
    do_dai = len((b.danh_gia or "").strip())
    zalo = b.zalo_trang_thai == BuoiHoc.GuiZalo.DA_GUI

    def ty_le(v):
        return None if v is None else v >= nguong
    return [
        {"ten": f"Gia sư vào đúng giờ (trễ tối đa {tre_max} phút)",
         "dat": None if hk.tre_phut is None else hk.tre_phut <= tre_max,
         "gia_tri": "Không có dữ liệu" if hk.tre_phut is None else ("Đúng giờ" if hk.tre_phut <= 0 else f"Trễ {hk.tre_phut} phút")},
        {"ten": f"Gia sư tham gia từ {nguong}% thời lượng", "dat": ty_le(hk.ty_le_gia_su),
         "gia_tri": "Không có dữ liệu" if hk.ty_le_gia_su is None else f"{hk.ty_le_gia_su}%"},
        {"ten": f"Học viên tham gia từ {nguong}% thời lượng", "dat": ty_le(hk.ty_le_hoc_vien),
         "gia_tri": "Không có dữ liệu" if hk.ty_le_hoc_vien is None else f"{hk.ty_le_hoc_vien}%"},
        {"ten": f"Phiếu đánh giá đầy đủ (nhận xét từ {nx_min} ký tự)", "dat": do_dai >= nx_min,
         "gia_tri": "Đủ" if do_dai >= nx_min else f"{do_dai} ký tự"},
        {"ten": "Đã gửi nhận xét cho phụ huynh qua Zalo", "dat": zalo,
         "gia_tri": "Đã gửi" if zalo else b.get_zalo_trang_thai_display()},
    ]


def so_canh_bao(hk):
    return sum(1 for t in tieu_chi(hk) if t["dat"] is False)


def cham(hk, nguoi_tham_gia=None, co_du_lieu=True):
    """Ghi 3 chỉ số Zoom (nếu có) + độ dài nhận xét + Zalo, tính lại số cảnh báo. Không đổi trạng thái buổi."""
    b = hk.buoi_hoc
    if co_du_lieu and nguoi_tham_gia is not None:
        tl = b.thoi_luong_phut or 1

        def phut(ds):
            return sum((p.ra_luc - p.vao_luc).total_seconds() / 60 for p in ds if p.vao_luc and p.ra_luc)
        host = [p for p in nguoi_tham_gia if p.la_host]
        khach = [p for p in nguoi_tham_gia if not p.la_host]
        vao_dau = min((p.vao_luc for p in host if p.vao_luc), default=None)
        hk.tre_phut = int((vao_dau - b.bat_dau).total_seconds() // 60) if vao_dau else None
        hk.ty_le_gia_su = min(round(phut(host) * 100 / tl), 100)
        hk.ty_le_hoc_vien = min(round(phut(khach) * 100 / tl), 100)
    hk.do_dai_nhan_xet = len((b.danh_gia or "").strip())
    hk.da_gui_zalo = b.zalo_trang_thai == BuoiHoc.GuiZalo.DA_GUI
    hk.so_canh_bao = so_canh_bao(hk)
    hk.da_cham = True
    hk.save(update_fields=["tre_phut", "ty_le_gia_su", "ty_le_hoc_vien", "do_dai_nhan_xet", "da_gui_zalo",
                           "so_canh_bao", "da_cham"])
    return hk


# =============================================================================
# SD-21 – danh sách, quyền, kết luận
# =============================================================================
def pham_vi(user):
    """HauKiemBuoi mà user được xem: Tuyển sinh = của mình + gia sư chưa có người mời; QTV = tất cả."""
    qs = HauKiemBuoi.objects.select_related(
        "buoi_hoc__gia_su", "buoi_hoc__hoc_vien", "buoi_hoc__yeu_cau__mon_hoc", "buoi_hoc__yeu_cau__cap_do",
        "buoi_hoc__khoa_hoc", "buoi_hoc__thu_lao", "nguoi_phu_trach", "kiem_boi")
    if user.la_admin:
        return qs
    return qs.filter(Q(nguoi_phu_trach=user) | Q(nguoi_phu_trach__isnull=True))


def kiem_quyen(user, hk):
    if not user.la_tuyen_sinh:
        raise PermissionDenied("Chỉ Tuyển sinh phụ trách mới kết luận hậu kiểm.")
    if hk.nguoi_phu_trach_id and hk.nguoi_phu_trach_id != user.pk:
        raise PermissionDenied(f"Buổi này do {hk.nguoi_phu_trach.ho_ten} phụ trách hậu kiểm.")


def thuoc_tab(hk, tab, canh_bao=None):
    canh_bao = so_canh_bao(hk) if canh_bao is None else canh_bao
    if tab == "can_kiem":
        return hk.ket_luan == KL.CHUA_KIEM_TRA
    if tab == "canh_bao":
        return hk.ket_luan == KL.CHUA_KIEM_TRA and canh_bao > 0
    if tab == "co_van_de":
        return hk.ket_luan == KL.CO_VAN_DE
    return hk.ket_luan in (KL.HOP_LE, KL.DA_XU_LY_TINH, KL.DA_XU_LY_KHONG_TINH)


def _ket_luan_hop_le(user, hk, hang_loat=False, ghi_chu=""):
    now = timezone.now()
    n = HauKiemBuoi.objects.filter(pk=hk.pk, ket_luan=KL.CHUA_KIEM_TRA).update(
        ket_luan=KL.HOP_LE, kiem_boi=user, kiem_luc=now, hang_loat=hang_loat, ghi_chu=ghi_chu[:1000],
        nguoi_phu_trach=hk.nguoi_phu_trach or user)
    if n:
        BuoiHoc.objects.filter(pk=hk.buoi_hoc_id).update(kiem_tra=BuoiHoc.KiemTra.HOP_LE)
    return n


def ket_luan(user, hk, ket_qua, ly_do="", ghi_chu=""):
    kiem_quyen(user, hk)
    ghi_chu = (ghi_chu or "").strip()
    b = hk.buoi_hoc
    if ket_qua == KL.HOP_LE:
        if not _ket_luan_hop_le(user, hk, ghi_chu=ghi_chu):
            raise ValidationError("Buổi đã được kiểm tra.")
        ghi_nhat_ky(user, "Hậu kiểm: buổi hợp lệ", b.ma, ghi_chu)
        hk.refresh_from_db()
        return hk
    if ket_qua != KL.CO_VAN_DE:
        raise ValidationError("Kết luận không hợp lệ.")
    if ly_do not in HauKiemBuoi.LyDo.values:
        raise ValidationError({"ly_do": "Chọn lý do có vấn đề."})
    if not ghi_chu:
        raise ValidationError({"ghi_chu": "Ghi chú bắt buộc khi có vấn đề (gia sư sẽ đọc được)."})
    now = timezone.now()
    with transaction.atomic():
        n = HauKiemBuoi.objects.filter(pk=hk.pk, ket_luan=KL.CHUA_KIEM_TRA).update(
            ket_luan=KL.CO_VAN_DE, ly_do=ly_do, ghi_chu=ghi_chu[:1000], kiem_boi=user, kiem_luc=now,
            nguoi_phu_trach=hk.nguoi_phu_trach or user)
        if not n:
            raise ValidationError("Buổi đã được kiểm tra.")
        nhan = HauKiemBuoi.LyDo(ly_do).label
        BuoiHoc.objects.filter(pk=b.pk, trang_thai=TT.HOAN_TAT).update(
            trang_thai=TT.DANG_XEM_XET, kiem_tra=BuoiHoc.KiemTra.CO_VAN_DE,
            kiem_tra_ghi_chu=f"{nhan}: {ghi_chu}"[:1000], cap_nhat_luc=now)
        tam_giu = ThuLao.objects.filter(buoi_hoc=b, trang_thai=ThuLao.TrangThai.TAM_TINH).update(
            trang_thai=ThuLao.TrangThai.TAM_GIU)
        ghi_nhat_ky(user, "Hậu kiểm: buổi có vấn đề", b.ma, f"{nhan}. {ghi_chu}")
    gui_email(b.gia_su, f"Buổi học {b.ma} đang được xem xét",
              f"Buổi {b.yeu_cau.mon_hoc} với {b.hoc_vien.ho_ten} lúc {timezone.localtime(b.bat_dau):%H:%M %d/%m} "
              f"được hậu kiểm và ghi nhận có vấn đề: {nhan}.\nGhi chú: {ghi_chu}\n"
              + ("Thù lao buổi này tạm giữ cho tới khi trung tâm xử lý xong. " if tam_giu else "")
              + "Nếu có lý do (mất mạng, đổi thiết bị…), hãy phản hồi email này cho trung tâm.", buoi_hoc=b)
    hk.refresh_from_db()
    return hk


def duyet_hang_loat(user, ids, chi_buoi_sach=False):
    """→ (số đã duyệt, số bỏ qua). Bỏ qua buổi không thuộc quyền / đã kết luận / có cảnh báo (nếu chi_buoi_sach)."""
    if not user.la_tuyen_sinh:
        raise PermissionDenied("Chỉ Tuyển sinh phụ trách mới kết luận hậu kiểm.")
    ds = list(pham_vi(user).filter(pk__in=[int(i) for i in ids if str(i).isdigit()]))
    da, ma = 0, []
    for hk in ds:
        if chi_buoi_sach and so_canh_bao(hk) > 0:
            continue
        if _ket_luan_hop_le(user, hk, hang_loat=True):
            da += 1
            ma.append(hk.buoi_hoc.ma)
    if ma:
        ghi_nhat_ky(user, "Hậu kiểm hàng loạt", f"{da} buổi", ", ".join(ma)[:1000])
    return da, len(ids) - da


# =============================================================================
# SD-22 – xử lý buổi có vấn đề (vẫn tính / không tính)
# =============================================================================
def xu_ly(user, hk, tinh, ly_do):
    from core.services import ngoai_le
    from core.services.thu_lao import thang_ghi_nhan, them_dieu_chinh
    kiem_quyen(user, hk)
    if hk.ket_luan != KL.CO_VAN_DE:
        raise ValidationError("Chỉ xử lý buổi đang ở tab Có vấn đề.")
    b = hk.buoi_hoc
    now = timezone.now()
    if tinh:
        ngoai_le.xac_nhan_hop_le(user, b, ly_do)
        moi = KL.DA_XU_LY_TINH
    else:
        tl = ThuLao.objects.filter(buoi_hoc=b).first()
        if tl and tl.trang_thai == ThuLao.TrangThai.DA_DOI_SOAT:
            # Tháng đã chốt: trừ ở tháng mở kế tiếp, rồi hủy buổi (không đụng thù lao đã chốt).
            with transaction.atomic():
                them_dieu_chinh(user, b.gia_su, thang_ghi_nhan(b.gia_su, now.date()), -tl.so_tien,
                                f"Hậu kiểm không công nhận {b.ma}: {ly_do}", buoi_hoc=b)
                _huy_khong_thu_lao(user, b, ly_do)
        else:
            ngoai_le.huy_sau_xem_xet(user, b, ly_do)
        moi = KL.DA_XU_LY_KHONG_TINH
    HauKiemBuoi.objects.filter(pk=hk.pk).update(ket_luan=moi, kiem_boi=user, kiem_luc=now)
    hk.refresh_from_db()
    return hk


def _huy_khong_thu_lao(user, b, ly_do):
    from django.db.models import F
    from core.models import KhoaHoc
    n = BuoiHoc.objects.filter(pk=b.pk, trang_thai=TT.DANG_XEM_XET).update(
        trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.HAU_KIEM, kiem_tra=BuoiHoc.KiemTra.DA_XU_LY,
        cap_nhat_luc=timezone.now())
    if not n:
        raise ValidationError("Buổi học không còn ở trạng thái Đang xem xét.")
    if b.khoa_hoc_id:
        KhoaHoc.objects.filter(pk=b.khoa_hoc_id, so_buoi_da_dung__gt=0).update(so_buoi_da_dung=F("so_buoi_da_dung") - 1)
        KhoaHoc.objects.filter(pk=b.khoa_hoc_id, trang_thai=KhoaHoc.TrangThai.HOAN_THANH).update(
            trang_thai=KhoaHoc.TrangThai.DANG_HOC)
    ghi_nhat_ky(user, "Hậu kiểm: không công nhận buổi (tháng đã chốt, trừ tháng sau)", b.ma, ly_do)
    gui_email(b.gia_su, f"Buổi {b.ma} không được công nhận",
              f"Buổi {b.ma} không được công nhận. Thù lao đã chốt nên được trừ ở tháng kế tiếp.\nLý do: {ly_do}",
              buoi_hoc=b)


# =============================================================================
# Số liệu cho màn hình
# =============================================================================
def thong_ke(user, ds=None):
    ds = list(pham_vi(user)) if ds is None else ds
    now = timezone.localtime()
    dau_thang = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    thang = [h for h in ds if h.kiem_luc and h.kiem_luc >= dau_thang and h.ket_luan != KL.CHUA_KIEM_TRA]
    hop_le = sum(1 for h in thang if h.ket_luan in (KL.HOP_LE, KL.DA_XU_LY_TINH))
    return {"chua_kiem": sum(1 for h in ds if h.ket_luan == KL.CHUA_KIEM_TRA),
            "canh_bao": sum(1 for h in ds if h.ket_luan == KL.CHUA_KIEM_TRA and h.so_cb > 0),
            "co_van_de": sum(1 for h in ds if h.ket_luan == KL.CO_VAN_DE),
            "ty_le": round(hop_le * 100 / len(thang)) if thang else None, "thang": now.month}


def the_gia_su(user, ds):
    """Thẻ gia sư (người user mời): số buổi tuần này, % hợp lệ (đã kết luận), số buổi cần chú ý."""
    tu = timezone.now() - timedelta(days=timezone.localtime().weekday())
    nhom = {}
    for h in ds:
        gs = h.buoi_hoc.gia_su
        x = nhom.setdefault(gs.pk, {"gs": gs, "tuan": 0, "kl": 0, "hl": 0, "chu_y": 0})
        if h.buoi_hoc.bat_dau >= tu.replace(hour=0, minute=0, second=0):
            x["tuan"] += 1
        if h.ket_luan != KL.CHUA_KIEM_TRA:
            x["kl"] += 1
            x["hl"] += h.ket_luan in (KL.HOP_LE, KL.DA_XU_LY_TINH)
        if h.ket_luan == KL.CO_VAN_DE or (h.ket_luan == KL.CHUA_KIEM_TRA and h.so_cb > 0):
            x["chu_y"] += 1
    kq = sorted(nhom.values(), key=lambda x: (-x["chu_y"], x["gs"].ho_ten))
    for x in kq:
        x["ty_le"] = round(x["hl"] * 100 / x["kl"]) if x["kl"] else None
    return kq[:3]


def so_cho(user):
    """Badge menu: số buổi chưa kiểm tra trong phạm vi Tuyển sinh."""
    if not user.la_tuyen_sinh:
        return 0
    return pham_vi(user).filter(ket_luan=KL.CHUA_KIEM_TRA).count()
