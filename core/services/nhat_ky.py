"""Ghi nhật ký thao tác quan trọng vào D9 (PB-23). Nhật ký chỉ thêm, không sửa, không xóa."""

import re

from core.models import NhatKy

_MA = re.compile(r"\b(YC-\d{4,}|KH-\d{4,}|BH-\d{5,})\b")
_LOAI_THEO_MA = {"YC": NhatKy.LoaiDoiTuong.YEU_CAU, "KH": NhatKy.LoaiDoiTuong.KHOA_HOC,
                 "BH": NhatKy.LoaiDoiTuong.BUOI_HOC}


def ghi_nhat_ky(nguoi, hanh_dong, doi_tuong="", chi_tiet="", *, loai=None, ma=None,
                cu=None, moi=None, ip=None):
    """Tham số sau dấu * là tùy chọn (không phá lời gọi cũ). Không truyền `ma` thì tự tìm mã
    YC-/KH-/BH- trong `doi_tuong` để trang Nhật ký lọc được theo mã."""
    doi_tuong = str(doi_tuong)[:200]
    if ma is None:
        tim = _MA.search(doi_tuong)
        ma = tim.group(1) if tim else ""
    if loai is None and ma:
        loai = _LOAI_THEO_MA.get(ma[:2], "")
    return NhatKy.objects.create(
        nguoi_thuc_hien=nguoi if getattr(nguoi, "is_authenticated", False) else None,
        hanh_dong=hanh_dong, doi_tuong=doi_tuong, chi_tiet=chi_tiet,
        loai_doi_tuong=loai or "", ma_doi_tuong=(ma or "")[:30], gia_tri_cu=cu, gia_tri_moi=moi, ip=ip,
    )
