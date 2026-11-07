"""Ghi nhật ký thao tác quan trọng vào D9 (PB-23)."""

from core.models import NhatKy


def ghi_nhat_ky(nguoi, hanh_dong, doi_tuong="", chi_tiet=""):
    return NhatKy.objects.create(
        nguoi_thuc_hien=nguoi if getattr(nguoi, "is_authenticated", False) else None,
        hanh_dong=hanh_dong,
        doi_tuong=str(doi_tuong)[:200],
        chi_tiet=chi_tiet,
    )
