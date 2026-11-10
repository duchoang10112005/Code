"""API JSON nhỏ cho phần tương tác của giao diện mới (01 · mục 3).

Trả về {ok, message, data, errors}. Lỗi nghiệp vụ (ValidationError) → HTTP 200, ok=false.
Mỗi API gọi đúng hàm service như view HTML để hai đường dùng chung quy tắc.
"""

import json
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse


def tra_ve(ok=True, message="", data=None, errors=None, status=200):
    return JsonResponse({"ok": ok, "message": message, "data": data or {}, "errors": errors or {}}, status=status)


def doc_du_lieu(request):
    """Đọc body JSON hoặc form POST thành dict."""
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or b"{}")
        except ValueError:
            return {}
    return request.POST.dict()


def loi_nghiep_vu(exc):
    if hasattr(exc, "error_dict"):
        errors = {k: [str(m) for e in v for m in e.messages] for k, v in exc.error_dict.items()}
        msg = next(iter(errors.values()))[0] if errors else "Dữ liệu chưa hợp lệ."
        return tra_ve(False, msg, errors=errors)
    return tra_ve(False, " ".join(exc.messages))


def api(vai_tro=None, phuong_thuc=("GET",)):
    """Decorator: bắt đăng nhập, vai trò, phương thức; đổi lỗi thành JSON đúng quy ước."""
    def boc(view):
        @wraps(view)
        def ham(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return tra_ve(False, "Phiên đăng nhập đã hết, vui lòng đăng nhập lại.", status=401)
            if request.method not in phuong_thuc:
                return tra_ve(False, "Phương thức không được hỗ trợ.", status=405)
            if vai_tro and request.user.vai_tro not in vai_tro:
                return tra_ve(False, "Bạn không có quyền thực hiện thao tác này.", status=403)
            try:
                return view(request, *args, **kwargs)
            except ValidationError as exc:
                return loi_nghiep_vu(exc)
            except PermissionDenied as exc:
                return tra_ve(False, str(exc) or "Bạn không có quyền thực hiện thao tác này.", status=403)
            except Http404:
                return tra_ve(False, "Không tìm thấy dữ liệu.", status=404)
        return ham
    return boc
