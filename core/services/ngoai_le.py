"""Xử lý ngoại lệ (Phần 5b): Admin xem xét buổi học, sửa dữ liệu đã khóa, gán thẳng gia sư; đổi gia sư.

Nguyên tắc phân vai (docs/phan_vai.md):
- NV tuyển sinh chăm khách: đổi gia sư do NVTS thực hiện; từ lần thứ 2 trong cùng khóa cần Admin duyệt.
- Admin giữ luật: chỉ ra tay khi có ngoại lệ; MỌI thao tác bắt buộc ghi lý do và vào nhật ký.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import BuoiHoc, DoiGiaSu, KhoaHoc, LoiMoi, ThuLao, YeuCauHocTap, YeuCauXuLy
from core.services.buoi_hoc import _xoa_zoom
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email
from core.services.yeu_cau import chap_nhan, la_du_dieu_kien

TT = BuoiHoc.TrangThai
KH = KhoaHoc.TrangThai
YC = YeuCauHocTap.TrangThai
NV = settings.NGHIEP_VU


def _ly_do(ly_do):
    ly_do = (ly_do or "").strip()[:300]
    if not ly_do:
        raise ValidationError("Cần ghi lý do cho thao tác này.")
    return ly_do


def _gio(b):
    return f"{timezone.localtime(b.bat_dau):%H:%M %d/%m}"


# =============================================================================
# 1. Buổi đang xem xét
# =============================================================================
def ds_can_xem_xet():
    """Buổi hậu kiểm có vấn đề + buổi tự hủy vì quá hạn còn trong thời gian được mở lại."""
    tu = timezone.now() - timedelta(days=NV["NGAY_MO_LAI_TOI_DA"])
    return (BuoiHoc.objects.filter(trang_thai=TT.DANG_XEM_XET) |
            BuoiHoc.objects.filter(trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN, han_xac_nhan__gte=tu)
            ).select_related("gia_su", "hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc").order_by("bat_dau")


def xac_nhan_hop_le(admin, buoi, ly_do):
    ly_do = _ly_do(ly_do)
    with transaction.atomic():
        n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai=TT.DANG_XEM_XET).update(
            trang_thai=TT.HOAN_TAT, kiem_tra=BuoiHoc.KiemTra.DA_XU_LY, cap_nhat_luc=timezone.now())
        if n == 0:
            raise ValidationError("Buổi học không còn ở trạng thái Đang xem xét.")
        ThuLao.objects.filter(buoi_hoc=buoi, trang_thai=ThuLao.TrangThai.TAM_GIU).update(
            trang_thai=ThuLao.TrangThai.TAM_TINH)
        ghi_nhat_ky(admin, "Xem xét: công nhận buổi học hợp lệ", buoi.ma, ly_do)
    gui_email(buoi.gia_su, f"Buổi {buoi.ma} được công nhận",
              f"Trung tâm đã xem xét buổi {buoi.yeu_cau.mon_hoc} lúc {_gio(buoi)} và công nhận hợp lệ. "
              f"Thù lao buổi này được tính bình thường.\nGhi chú: {ly_do}", buoi_hoc=buoi)


def huy_sau_xem_xet(admin, buoi, ly_do):
    """Không công nhận buổi: trả lại 1 buổi cho khóa, hủy thù lao (nếu tháng chưa chốt)."""
    ly_do = _ly_do(ly_do)
    tl = ThuLao.objects.filter(buoi_hoc=buoi).first()
    if tl and tl.trang_thai == ThuLao.TrangThai.DA_DOI_SOAT:
        raise ValidationError("Thù lao buổi này đã chốt đối soát. Hãy tạo khoản điều chỉnh trừ ở tháng sau.")
    with transaction.atomic():
        n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai=TT.DANG_XEM_XET).update(
            trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.HAU_KIEM, kiem_tra=BuoiHoc.KiemTra.DA_XU_LY,
            cap_nhat_luc=timezone.now())
        if n == 0:
            raise ValidationError("Buổi học không còn ở trạng thái Đang xem xét.")
        if buoi.khoa_hoc_id:
            KhoaHoc.objects.filter(pk=buoi.khoa_hoc_id, so_buoi_da_dung__gt=0).update(
                so_buoi_da_dung=F("so_buoi_da_dung") - 1)
            KhoaHoc.objects.filter(pk=buoi.khoa_hoc_id, trang_thai=KH.HOAN_THANH).update(trang_thai=KH.DANG_HOC)
        if tl:
            ThuLao.objects.filter(pk=tl.pk).update(trang_thai=ThuLao.TrangThai.HUY)
        ghi_nhat_ky(admin, "Xem xét: không công nhận buổi học", buoi.ma, ly_do)
    gui_email(buoi.gia_su, f"Buổi {buoi.ma} không được công nhận",
              f"Sau khi xem xét, buổi {buoi.yeu_cau.mon_hoc} lúc {_gio(buoi)} không được công nhận và không tính thù lao. "
              f"Số buổi đã được trả lại cho khóa học.\nLý do: {ly_do}", buoi_hoc=buoi)


def mo_lai(admin, buoi, ly_do):
    """Mở lại buổi bị tự hủy vì quá hạn (≤ NGAY_MO_LAI_TOI_DA ngày): gia sư có thêm GIO_XAC_NHAN_KHI_MO_LAI giờ."""
    ly_do = _ly_do(ly_do)
    now = timezone.now()
    if buoi.trang_thai != TT.DA_HUY or buoi.ly_do_huy != BuoiHoc.LyDoHuy.QUA_HAN:
        raise ValidationError("Chỉ mở lại được buổi bị hệ thống tự hủy vì quá hạn xác nhận.")
    if not buoi.han_xac_nhan or buoi.han_xac_nhan < now - timedelta(days=NV["NGAY_MO_LAI_TOI_DA"]):
        raise ValidationError(f"Buổi đã hủy quá {NV['NGAY_MO_LAI_TOI_DA']} ngày, không mở lại được nữa.")
    if buoi.khoa_hoc_id:
        k = KhoaHoc.objects.get(pk=buoi.khoa_hoc_id)
        if k.trang_thai == KH.HUY:
            raise ValidationError("Khóa học đã hủy, không mở lại buổi được.")
        if k.so_buoi_co_the_xep <= 0:
            raise ValidationError(f"Khóa không còn chỗ: đã học {k.so_buoi_da_dung}, đang lên lịch "
                                  f"{k.so_buoi_dang_len_lich} / {k.so_buoi_dang_ky} buổi. "
                                  "Hủy bớt buổi sắp tới hoặc sửa số buổi đăng ký trước.")
    han_moi = now + timedelta(hours=NV["GIO_XAC_NHAN_KHI_MO_LAI"])
    n = BuoiHoc.objects.filter(pk=buoi.pk, trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN).update(
        trang_thai=TT.DA_LEN_LICH, ly_do_huy="", han_xac_nhan=han_moi, da_nhac_han=False, mo_lai_luc=now,
        cap_nhat_luc=now)
    if n == 0:
        raise ValidationError("Buổi học vừa thay đổi, vui lòng tải lại trang.")
    ghi_nhat_ky(admin, "Mở lại buổi học quá hạn", buoi.ma, ly_do)
    YeuCauXuLy.objects.filter(buoi_hoc=buoi, loai=YeuCauXuLy.Loai.MO_LAI, trang_thai=YeuCauXuLy.TrangThai.CHO_XU_LY) \
        .update(trang_thai=YeuCauXuLy.TrangThai.DA_XU_LY, xu_ly_boi=admin, xu_ly_luc=now, ket_qua=ly_do[:300])
    from django.urls import reverse
    from core.services.thong_bao import thong_bao
    thong_bao(buoi.gia_su, f"Buổi {buoi.ma} đã được mở lại",
              f"Xác nhận trước {timezone.localtime(han_moi):%H:%M %d/%m}", reverse("buoi_chi_tiet", args=[buoi.pk]),
              "BUOI_HOC")
    gui_email(buoi.gia_su, f"Buổi {buoi.ma} đã được mở lại",
              f"Trung tâm đã mở lại buổi {buoi.yeu_cau.mon_hoc} lúc {_gio(buoi)}. Bạn có tới "
              f"{timezone.localtime(han_moi):%H:%M %d/%m} để vào mục Buổi học của tôi và xác nhận.\nGhi chú: {ly_do}",
              buoi_hoc=buoi)


# =============================================================================
# 1b. Gia sư gửi yêu cầu xử lý: xin mở lại buổi tự hủy (SD-19), báo sự cố (SD-34)
# =============================================================================
def gui_yeu_cau_xu_ly(gia_su, buoi, loai, noi_dung, minh_chung_url=""):
    noi_dung = (noi_dung or "").strip()
    minh_chung_url = (minh_chung_url or "").strip()
    now = timezone.now()
    if buoi.gia_su_id != gia_su.pk:
        raise ValidationError("Đây không phải buổi học của bạn.")
    if loai not in YeuCauXuLy.Loai.values:
        raise ValidationError("Loại yêu cầu không hợp lệ.")
    if len(noi_dung) < 10:
        raise ValidationError({"noi_dung": "Hãy mô tả ngắn gọn lý do (ít nhất 10 ký tự)."})
    if minh_chung_url and not minh_chung_url.startswith("https://"):
        raise ValidationError({"minh_chung_url": "Link minh chứng phải bắt đầu bằng https://"})
    han = None
    if loai == YeuCauXuLy.Loai.MO_LAI:
        if buoi.trang_thai != TT.DA_HUY or buoi.ly_do_huy != BuoiHoc.LyDoHuy.QUA_HAN:
            raise ValidationError("Chỉ xin mở lại buổi bị hệ thống tự hủy vì quá hạn xác nhận.")
        han = buoi.han_xac_nhan + timedelta(days=NV["NGAY_MO_LAI_TOI_DA"])
        if han < now:
            raise ValidationError(f"Buổi đã hủy quá {NV['NGAY_MO_LAI_TOI_DA']} ngày, không mở lại được nữa.")
    if YeuCauXuLy.objects.filter(buoi_hoc=buoi, loai=loai, trang_thai=YeuCauXuLy.TrangThai.CHO_XU_LY).exists():
        raise ValidationError("Bạn đã gửi yêu cầu cho buổi này, đang chờ Quản trị viên xử lý.")
    yc = YeuCauXuLy.objects.create(loai=loai, buoi_hoc=buoi, nguoi_gui=gia_su, noi_dung=noi_dung[:2000],
                                   minh_chung_url=minh_chung_url, han_xu_ly=han or buoi.han_xac_nhan)
    ghi_nhat_ky(gia_su, "Xin mở lại buổi học" if loai == YeuCauXuLy.Loai.MO_LAI else "Báo sự cố buổi học",
                buoi.ma, noi_dung[:300])
    from django.urls import reverse
    from core.services.thong_bao import thong_bao_quan_tri
    thong_bao_quan_tri(f"{yc.get_loai_display()}: {buoi.ma}", f"{gia_su.ho_ten}: {noi_dung[:120]}",
                       reverse("xem_xet") + f"?q={buoi.ma}")
    return yc


# =============================================================================
# 2. Admin sửa dữ liệu đã khóa
# =============================================================================
def sua_so_buoi(admin, khoa, so_moi, ly_do):
    ly_do = _ly_do(ly_do)
    khoa.refresh_from_db()
    toi_thieu = khoa.so_buoi_da_dung + khoa.so_buoi_dang_len_lich
    if so_moi < max(toi_thieu, 1):
        raise ValidationError(f"Số buổi đăng ký phải ít nhất {max(toi_thieu, 1)} "
                              f"(đã học {khoa.so_buoi_da_dung}, đang lên lịch {khoa.so_buoi_dang_len_lich}).")
    cu = khoa.so_buoi_dang_ky
    trang_thai = khoa.trang_thai
    if trang_thai == KH.HOAN_THANH and so_moi > khoa.so_buoi_da_dung:
        trang_thai = KH.DANG_HOC
    elif trang_thai == KH.DANG_HOC and so_moi == khoa.so_buoi_da_dung:
        trang_thai = KH.HOAN_THANH
    KhoaHoc.objects.filter(pk=khoa.pk).update(so_buoi_dang_ky=so_moi, trang_thai=trang_thai)
    ghi_nhat_ky(admin, "Admin sửa số buổi đăng ký", khoa.ma, f"{cu} → {so_moi}. {ly_do}")
    khoa.refresh_from_db()
    return khoa


# =============================================================================
# 3. Đổi gia sư (NVTS thực hiện, Admin duyệt từ lần thứ 2)
# =============================================================================
def de_nghi_doi_gia_su(nguoi, khoa, ly_do, ghi_chu=""):
    if ly_do not in DoiGiaSu.LyDo.values:
        raise ValidationError("Chọn lý do đổi gia sư.")
    ghi_chu = (ghi_chu or "").strip()[:300]
    if ly_do == DoiGiaSu.LyDo.KHAC and not ghi_chu:
        raise ValidationError("Lý do khác: cần ghi rõ ở ô ghi chú.")
    khoa.refresh_from_db()
    if khoa.trang_thai not in (KH.DANG_HOC, KH.TAM_DUNG) or khoa.yeu_cau.trang_thai != YC.CHINH_THUC:
        raise ValidationError("Chỉ đổi gia sư cho khóa đang học hoặc tạm dừng.")
    if khoa.lich_su_doi_gia_su.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET).exists():
        raise ValidationError("Khóa này đang có đề nghị đổi gia sư chờ Admin duyệt.")
    da_doi = khoa.lich_su_doi_gia_su.filter(trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN).count()
    can_duyet = da_doi >= 1 and not nguoi.la_admin
    dn = DoiGiaSu.objects.create(khoa_hoc=khoa, gia_su_cu=khoa.gia_su, ly_do=ly_do, ghi_chu=ghi_chu, tao_boi=nguoi,
                                 trang_thai=DoiGiaSu.TrangThai.CHO_DUYET if can_duyet else DoiGiaSu.TrangThai.DA_THUC_HIEN)
    if can_duyet:
        ghi_nhat_ky(nguoi, "Đề nghị đổi gia sư (chờ Admin duyệt)", khoa.ma, f"Lần đổi thứ {da_doi + 1}. {dn.get_ly_do_display()}")
        return dn
    _thuc_hien_doi(nguoi, dn)
    return dn


def duyet_doi_gia_su(admin, dn, dong_y, ghi_chu=""):
    if dn.trang_thai != DoiGiaSu.TrangThai.CHO_DUYET:
        raise ValidationError("Đề nghị này đã được xử lý.")
    now = timezone.now()
    if not dong_y:
        ghi_chu = _ly_do(ghi_chu)
        DoiGiaSu.objects.filter(pk=dn.pk).update(trang_thai=DoiGiaSu.TrangThai.TU_CHOI, duyet_boi=admin, duyet_luc=now)
        ghi_nhat_ky(admin, "Từ chối đề nghị đổi gia sư", dn.khoa_hoc.ma, ghi_chu)
        if dn.tao_boi:
            gui_email(dn.tao_boi, f"Đề nghị đổi gia sư {dn.khoa_hoc.ma} bị từ chối", f"Lý do: {ghi_chu}")
        return dn
    DoiGiaSu.objects.filter(pk=dn.pk).update(duyet_boi=admin, duyet_luc=now)
    dn.refresh_from_db()
    _thuc_hien_doi(admin, dn)
    return dn


def _thuc_hien_doi(nguoi, dn):
    """Hủy buổi tương lai của gia sư cũ, tạm dừng khóa, đưa yêu cầu về Đang tìm (giữ nguyên số buổi còn lại)."""
    khoa, gs_cu, now = dn.khoa_hoc, dn.gia_su_cu, timezone.now()
    with transaction.atomic():
        tuong_lai = list(khoa.buoi_hoc.filter(gia_su=gs_cu, trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=now))
        BuoiHoc.objects.filter(pk__in=[b.pk for b in tuong_lai]).update(
            trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.ADMIN_HUY, kiem_tra_ghi_chu="Đổi gia sư")
        KhoaHoc.objects.filter(pk=khoa.pk).update(trang_thai=KH.TAM_DUNG, ghi_chu=f"Đổi gia sư: {dn.get_ly_do_display()}")
        YeuCauHocTap.objects.filter(pk=khoa.yeu_cau_id).update(trang_thai=YC.DANG_TIM, gia_su=None, phan_cong_luc=None,
                                                             cap_nhat_luc=now)
        DoiGiaSu.objects.filter(pk=dn.pk).update(trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN)
        ghi_nhat_ky(nguoi, "Đổi gia sư", khoa.ma,
                    f"Gia sư cũ {gs_cu.ho_ten}; {dn.get_ly_do_display()}. {dn.ghi_chu}".strip()
                    + f"; hủy {len(tuong_lai)} buổi sắp tới")
        transaction.on_commit(lambda: [_xoa_zoom(b) for b in tuong_lai])
    gui_email(gs_cu, f"Thay đổi gia sư khóa {khoa.ma}",
              f"Trung tâm đã chuyển khóa {khoa.yeu_cau.mon_hoc} của học viên {khoa.hoc_vien} sang gia sư khác. "
              f"Các buổi đã dạy vẫn được tính thù lao bình thường; {len(tuong_lai)} buổi sắp tới đã được hủy.\n"
              "Cảm ơn bạn đã đồng hành cùng học viên.")


def nhan_lai_khoa(gia_su_moi, yc):
    """Gọi sau khi gia sư mới Accept một yêu cầu đã có khóa: chuyển khóa sang gia sư mới, học tiếp."""
    khoa = KhoaHoc.objects.filter(yeu_cau=yc).first()
    if not khoa:
        return None
    now = timezone.now()
    # Chỉ khóa đang tạm dừng vì đổi gia sư mới được nhận lại (khóa đã hủy / hoàn thành thì không).
    if not KhoaHoc.objects.filter(pk=khoa.pk, trang_thai=KH.TAM_DUNG).update(
            gia_su=gia_su_moi, trang_thai=KH.DANG_HOC, ghi_chu=""):
        raise ValidationError("Khóa học của lớp này không còn chờ gia sư mới.")
    khoa.refresh_from_db()
    YeuCauHocTap.objects.filter(pk=yc.pk).update(trang_thai=YC.CHINH_THUC, cap_nhat_luc=now)
    DoiGiaSu.objects.filter(khoa_hoc=khoa, trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN, gia_su_moi__isnull=True).update(
        gia_su_moi=gia_su_moi)
    ghi_nhat_ky(gia_su_moi, "Nhận lại khóa sau đổi gia sư", khoa.ma, f"Còn {khoa.so_buoi_con_lai} buổi")
    return khoa


# =============================================================================
# 4. Admin gán thẳng gia sư (yêu cầu chờ lâu)
# =============================================================================
def ds_cho_lau(gio=24):
    """Yêu cầu Mới/Đang tìm đã quá `gio` giờ kể từ khi tiếp nhận."""
    moc = timezone.now() - timedelta(hours=gio)
    return (YeuCauHocTap.objects.filter(trang_thai__in=[YC.MOI, YC.DANG_TIM], tao_luc__lt=moc)
            .select_related("hoc_vien", "mon_hoc").order_by("tao_luc"))


def gan_thang(admin, yc, gia_su, ly_do):
    """Vận hành chốt: tạo lời mời và nhận thay ngay cho gia sư (tái dùng 'Accept hợp lệ đầu tiên thắng')."""
    ly_do = _ly_do(ly_do)
    if yc.trang_thai not in (YC.MOI, YC.DANG_TIM):
        raise ValidationError("Chỉ gán thẳng cho yêu cầu đang Mới hoặc Đang mời gia sư.")
    if not la_du_dieu_kien(gia_su, yc.mon_hoc):
        raise ValidationError(f"{gia_su.ho_ten} chưa đủ điều kiện dạy môn {yc.mon_hoc}.")
    with transaction.atomic():
        YeuCauHocTap.objects.filter(pk=yc.pk, trang_thai=YC.MOI).update(trang_thai=YC.DANG_TIM)
        LoiMoi.objects.filter(yeu_cau=yc, gia_su=gia_su, trang_thai=LoiMoi.TrangThai.CHO).update(
            trang_thai=LoiMoi.TrangThai.VOIDED, phan_hoi_luc=timezone.now())
        lm = LoiMoi.objects.create(yeu_cau=yc, gia_su=gia_su, gui_boi=admin)
        yc.refresh_from_db()
        chap_nhan(gia_su, lm)
        ghi_nhat_ky(admin, "Vận hành gán thẳng gia sư", yc.ma, f"{gia_su.ho_ten}. {ly_do}")
    gui_email(gia_su, f"Bạn được phân công lớp {yc.mon_hoc}",
              f"Trung tâm đã phân công bạn dạy lớp {yc.mon_hoc} ({yc.trinh_do}) của học viên {yc.hoc_vien}. "
              "Vào mục Lớp của tôi để xem chi tiết.")
    yc.refresh_from_db()
    return yc
