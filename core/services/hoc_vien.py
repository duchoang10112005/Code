"""Học viên – tình trạng suy ra từ yêu cầu / khóa học (màn Tuyển sinh › Học viên)."""

from core.models import HocVien, KhoaHoc, YeuCauHocTap

YC = YeuCauHocTap.TrangThai
KH = KhoaHoc.TrangThai

# (khóa, nhãn, màu chip) – thứ tự = độ ưu tiên khi học viên có nhiều yêu cầu.
TINH_TRANG = [("dang_hoc", "Đang học", "xanh_la"), ("hoc_thu", "Học thử", "tim"),
              ("dang_tim", "Đang tìm gia sư", "cam"), ("tam_dung", "Tạm dừng", "do"),
              ("ket_thuc", "Đã kết thúc", "xam")]
_TT = {k: (k, n, m) for k, n, m in TINH_TRANG}


def _loai(yc):
    kh = getattr(yc, "khoa_hoc", None) if yc.trang_thai == YC.CHINH_THUC else None
    if kh:
        return {KH.DANG_HOC: "dang_hoc", KH.TAM_DUNG: "tam_dung"}.get(kh.trang_thai, "ket_thuc"), kh
    if yc.trang_thai in (YC.DA_PHAN_CONG, YC.HOC_THU_XONG):
        return "hoc_thu", None
    if yc.trang_thai in (YC.MOI, YC.DANG_TIM):
        return "dang_tim", None
    return "ket_thuc", None


def tinh_trang(hv):
    """→ dict(tt=(khóa, nhãn, màu), yc, kh): yêu cầu/khóa quyết định tình trạng (ưu tiên theo TINH_TRANG)."""
    thu_tu = [k for k, _, _ in TINH_TRANG]
    tot = None
    for yc in hv.yeu_cau.all():
        k, kh = _loai(yc)
        if tot is None or thu_tu.index(k) < thu_tu.index(tot[0]) or (
                k == tot[0] and yc.tao_luc > tot[1].tao_luc):
            tot = (k, yc, kh)
    if tot is None:
        return {"tt": _TT["ket_thuc"], "yc": None, "kh": None}
    return {"tt": _TT[tot[0]], "yc": tot[1], "kh": tot[2]}


def ds_hoc_vien(q="", mon=None, phu_trach=None):
    qs = HocVien.objects.select_related("tuyen_sinh_phu_trach").prefetch_related(
        "yeu_cau__mon_hoc", "yeu_cau__cap_do", "yeu_cau__gia_su", "yeu_cau__khoa_hoc__gia_su").order_by("ho_ten")
    if q:
        from django.db.models import Q
        from core.services.tien_ich import chuan_hoa_sdt
        dk = Q(ho_ten__icontains=q) | Q(ten_phu_huynh__icontains=q) | Q(sdt_phu_huynh__icontains=q)
        sdt = chuan_hoa_sdt(q)
        if sdt:
            dk |= Q(sdt_phu_huynh__icontains=sdt)
        qs = qs.filter(dk)
    if mon:
        qs = qs.filter(yeu_cau__mon_hoc=mon).distinct()
    if phu_trach:
        qs = qs.filter(tuyen_sinh_phu_trach=phu_trach)
    return [dict(hv=hv, **tinh_trang(hv)) for hv in qs]
