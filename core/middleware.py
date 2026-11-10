from django.contrib import messages
from django.contrib.auth import SESSION_KEY


class ChanTaiKhoanBiKhoaMiddleware:
    """Tài khoản bị khóa trong lúc đang đăng nhập → xóa phiên ngay ở request kế tiếp (PB-01).

    Django đã coi tài khoản is_active=False là "chưa đăng nhập"; middleware này dọn phiên cũ
    và báo cho người dùng biết lý do thay vì im lặng chuyển về trang đăng nhập.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if SESSION_KEY in request.session and not request.user.is_authenticated:
            request.session.flush()
            messages.error(request, "Phiên làm việc đã kết thúc: tài khoản bị khóa hoặc không còn tồn tại.")
        return self.get_response(request)


class BatDoiMatKhauMiddleware:
    """Tài khoản có cờ phai_doi_mat_khau (Admin vừa tạo / đặt lại mật khẩu) → mọi trang chuyển về
    trang đặt mật khẩu mới, trừ chính trang đó và đăng xuất (SD-02)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if u is not None and u.is_authenticated and getattr(u, "phai_doi_mat_khau", False):
            from django.conf import settings
            from django.shortcuts import redirect
            from django.urls import reverse
            cho_phep = (reverse("doi_mat_khau"), reverse("dang_xuat"))
            p = request.path
            if p not in cho_phep and not p.startswith(("/" + settings.STATIC_URL.lstrip("/"), "/media/")):
                if p.startswith("/api/"):
                    from core.api import tra_ve
                    return tra_ve(False, "Bạn cần đặt mật khẩu mới trước khi tiếp tục.", status=403)
                return redirect(f"{reverse('doi_mat_khau')}?bat_buoc=1")
        return self.get_response(request)
