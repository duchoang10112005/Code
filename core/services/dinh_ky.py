"""Tác vụ định kỳ (SD-36): một lượt quét gồm 7 bước độc lập, mỗi bước tự bắt lỗi.

Mọi cập nhật đều có điều kiện nên chạy chồng 2 lần cũng không gửi trùng. quet_han() và
quet_loi_moi_het_han() vẫn được gọi "lười" khi mở trang để demo không phụ thuộc lịch chạy.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from core.models import BuoiHoc, HoSoGiaSu, KhoaHoc, NhacViec, YeuCauXuLy
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import thong_bao

logger = logging.getLogger(__name__)
NV = settings.NGHIEP_VU
TT = BuoiHoc.TrangThai


def mo_dong_phong(now=None):
    """Bước 2: đánh dấu phòng mở (10 phút trước giờ học) và kết thúc phòng Zoom (5 phút sau giờ học)."""
    from core.integrations.zoom import ZoomError
    from core.services.buoi_hoc import lay_zoom_client
    now = now or timezone.now()
    mo = BuoiHoc.objects.filter(trang_thai__in=[TT.DA_LEN_LICH, TT.HOAN_TAT], phong_mo_luc__isnull=True,
                                bat_dau__lte=now + timedelta(minutes=NV.get("MO_PHONG_TRUOC_PHUT", 10)),
                                ket_thuc_luc__gt=now).update(phong_mo_luc=now)
    dong = 0
    zoom = lay_zoom_client()
    for b in BuoiHoc.objects.filter(phong_dong_luc__isnull=True, ket_thuc_luc__lte=now - timedelta(
            minutes=NV.get("DONG_PHONG_SAU_PHUT", 5)), ket_thuc_luc__gte=now - timedelta(days=1)).exclude(
            zoom_meeting_id="").exclude(trang_thai=TT.DA_HUY):
        try:
            zoom.ket_thuc_phong(b.zoom_meeting_id)
        except ZoomError as exc:
            logger.info("Không kết thúc được phòng %s: %s", b.ma, exc)
            continue
        dong += BuoiHoc.objects.filter(pk=b.pk, phong_dong_luc__isnull=True).update(phong_dong_luc=now)
    return {"mo_phong": mo, "dong_phong": dong}


def nhac_viec(now=None):
    """Bước 5: báo nhắc việc quá hạn (1 lần/ngày), tạo nhắc hỏi gia hạn, từ chối xin mở lại quá hạn."""
    now = now or timezone.now()
    dau_ngay = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    bao = 0
    for nv in NhacViec.objects.filter(han_luc__lte=now, xong_luc__isnull=True).exclude(
            da_bao_luc__gte=dau_ngay).select_related("nguoi_phu_trach", "khoa_hoc", "yeu_cau"):
        if NhacViec.objects.filter(pk=nv.pk).exclude(da_bao_luc__gte=dau_ngay).update(da_bao_luc=now):
            url = (reverse("khoa_hoc_chi_tiet", args=[nv.khoa_hoc_id]) if nv.khoa_hoc_id
                   else reverse("yeu_cau_chi_tiet", args=[nv.yeu_cau_id]) if nv.yeu_cau_id else "")
            thong_bao(nv.nguoi_phu_trach, f"Nhắc việc: {nv.get_loai_display()}", nv.noi_dung, url, "KHAC")
            bao += 1
    tao = 0
    for k in (KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC, tuyen_sinh_phu_trach__isnull=False)
              .annotate(con=F("so_buoi_dang_ky") - F("so_buoi_da_dung"))
              .filter(con__lte=NV.get("NGUONG_SAP_HET_BUOI", 2))
              .exclude(pk__in=NhacViec.objects.filter(loai=NhacViec.Loai.HOI_GIA_HAN, xong_luc__isnull=True,
                                                      khoa_hoc__isnull=False).values("khoa_hoc"))
              .select_related("hoc_vien")):
        NhacViec.objects.create(nguoi_phu_trach=k.tuyen_sinh_phu_trach, loai=NhacViec.Loai.HOI_GIA_HAN, khoa_hoc=k,
                                noi_dung=f"{k.ma} · {k.hoc_vien.ho_ten} còn {k.con} buổi", han_luc=now + timedelta(days=1))
        tao += 1
    tu_choi = 0
    for y in YeuCauXuLy.objects.filter(loai=YeuCauXuLy.Loai.MO_LAI, trang_thai=YeuCauXuLy.TrangThai.CHO_XU_LY,
                                       han_xu_ly__lt=now).select_related("nguoi_gui", "buoi_hoc"):
        if YeuCauXuLy.objects.filter(pk=y.pk, trang_thai=YeuCauXuLy.TrangThai.CHO_XU_LY).update(
                trang_thai=YeuCauXuLy.TrangThai.TU_CHOI, xu_ly_luc=now,
                ket_qua=f"Quá {NV['NGAY_MO_LAI_TOI_DA']} ngày, hệ thống tự từ chối"):
            tu_choi += 1
            if y.nguoi_gui:
                thong_bao(y.nguoi_gui, f"Yêu cầu mở lại {y.buoi_hoc.ma} đã hết hạn",
                          f"Quá {NV['NGAY_MO_LAI_TOI_DA']} ngày chưa được xử lý.", "", "BUOI_HOC")
    return {"bao_nhac_viec": bao, "nhac_gia_han": tao, "tu_choi_mo_lai": tu_choi}


def het_han_ban_ghi(now=None):
    now = now or timezone.now()
    return {"ban_ghi_het_han": BuoiHoc.objects.filter(ban_ghi_trang_thai=BuoiHoc.BanGhi.SAN_SANG,
                                                      ban_ghi_het_han__lt=now).update(
        ban_ghi_trang_thai=BuoiHoc.BanGhi.HET_HAN)}


def tam_nghi_het_han(now=None):
    hom_nay = timezone.localdate(now or timezone.now())
    return {"het_tam_nghi": HoSoGiaSu.objects.filter(tam_nghi_den__lt=hom_nay).update(tam_nghi_den=None)}


def quet(now=None):
    """Một lượt quét đầy đủ. → dict số liệu từng bước (bước lỗi ghi 'loi')."""
    from core.services.buoi_hoc import hau_kiem, quet_han
    from core.services.yeu_cau import quet_loi_moi_het_han
    now = now or timezone.now()
    buoc = [("loi_moi", lambda: {"het_han_loi_moi": quet_loi_moi_het_han()}),
            ("phong", lambda: mo_dong_phong(now)),
            ("han", lambda: {"tu_huy": quet_han(now)}),
            ("hau_kiem", lambda: {"hau_kiem": hau_kiem(now)}),
            ("nhac_viec", lambda: nhac_viec(now)),
            ("ban_ghi", lambda: het_han_ban_ghi(now)),
            ("tam_nghi", lambda: tam_nghi_het_han(now))]
    kq = {}
    for ten, ham in buoc:
        try:
            r = ham() or {}
            kq.update({k: (v if isinstance(v, int) else 0) for k, v in r.items()})
        except Exception as exc:  # noqa: BLE001 – một bước lỗi không chặn bước sau
            logger.exception("Quét định kỳ: bước %s lỗi", ten)
            kq[f"loi_{ten}"] = str(exc)[:200]
    co_doi = {k: v for k, v in kq.items() if v}
    if co_doi:
        ghi_nhat_ky(None, "Quét định kỳ", "", ", ".join(f"{k}={v}" for k, v in co_doi.items())[:1000],
                    loai="HE_THONG")
    return kq
