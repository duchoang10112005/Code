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
