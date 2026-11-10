"""Đăng nhập bằng tên đăng nhập, email hoặc số điện thoại (màn Đăng nhập: "Email hoặc số điện thoại")."""

import re

from django.contrib.auth.backends import ModelBackend

from core.models import User


def _so(chuoi):
    """0905 123 456 / +84905123456 → 905123456 (bỏ đầu 0 / 84 để so khớp)."""
    so = re.sub(r"\D", "", chuoi or "")
    if so.startswith("84"):
        so = so[2:]
    return so.lstrip("0")


def tim_tai_khoan(dinh_danh):
    """Tìm đúng MỘT tài khoản theo tên đăng nhập / email / SĐT; mơ hồ (trùng) thì không trả về."""
    dinh_danh = (dinh_danh or "").strip()
    if not dinh_danh:
        return None
    u = User.objects.filter(username__iexact=dinh_danh).first()
    if u:
        return u
    if "@" in dinh_danh:
        ds = list(User.objects.filter(email__iexact=dinh_danh)[:2])
        return ds[0] if len(ds) == 1 else None
    so = _so(dinh_danh)
    if len(so) >= 8:
        ds = [x for x in User.objects.exclude(so_dien_thoai="").only("pk", "so_dien_thoai") if _so(x.so_dien_thoai) == so]
        if len(ds) == 1:
            return User.objects.get(pk=ds[0].pk)
    return None


class DangNhapLinhHoatBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        u = tim_tai_khoan(username)
        if u is None:
            User().set_password(password)  # tốn thời gian như nhau, tránh dò tài khoản theo thời gian phản hồi
            return None
        if u.check_password(password) and self.user_can_authenticate(u):
            return u
        return None
