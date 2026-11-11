"""Kết nối Zalo OA một lần (OAuth v4 + PKCE):  python manage.py zalo_ket_noi

1. Lệnh in ra link cấp quyền -> mở bằng trình duyệt đã đăng nhập Zalo của quản trị viên OA -> bấm Cho phép.
2. Zalo chuyển tới ZALO_REDIRECT_URI kèm ?code=... -> chép giá trị code dán vào lệnh.
3. Hệ thống lưu access token + refresh token vào bảng TokenZalo và từ đó tự làm mới.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.integrations.zalo import LoiZalo, doi_code_lay_token, tao_link_cap_quyen


class Command(BaseCommand):
    help = "Kết nối Zalo OA: lấy access token + refresh token lần đầu."

    def handle(self, *args, **opts):
        if not (settings.ZALO_APP_ID and settings.ZALO_SECRET_KEY and settings.ZALO_REDIRECT_URI):
            raise CommandError("Điền ZALO_APP_ID, ZALO_SECRET_KEY, ZALO_REDIRECT_URI trong .env trước.")
        url, verifier = tao_link_cap_quyen()
        self.stdout.write("Mở link sau bằng trình duyệt (đăng nhập Zalo của quản trị viên OA), bấm Cho phép:\n")
        self.stdout.write(url + "\n")
        code = input("Dán giá trị code trên thanh địa chỉ (phần sau 'code=' tới trước '&'): ").strip()
        if not code:
            raise CommandError("Chưa nhập code.")
        try:
            t = doi_code_lay_token(code, verifier)
        except LoiZalo as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f"Đã kết nối Zalo OA. Token hết hạn {t.het_han_luc:%H:%M %d/%m} – hệ thống sẽ tự làm mới."))
