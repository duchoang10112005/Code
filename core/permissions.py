"""Phân quyền theo vai trò (PB-01, PB-24)."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import User

ADMIN = User.VaiTro.ADMIN
TUYEN_SINH = User.VaiTro.TUYEN_SINH
GIA_SU = User.VaiTro.GIA_SU


def vai_tro_required(*vai_tro_cho_phep):
    """Chỉ cho các vai trò được liệt kê truy cập view; chưa đăng nhập thì chuyển sang trang đăng nhập.

    Ví dụ:  @vai_tro_required(ADMIN)  hoặc  @vai_tro_required(ADMIN, TUYEN_SINH)
    """

    def decorator(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.vai_tro not in vai_tro_cho_phep:
                raise PermissionDenied("Bạn không có quyền truy cập chức năng này.")
            return view(request, *args, **kwargs)

        return _wrapped

    return decorator
