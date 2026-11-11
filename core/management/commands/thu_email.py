"""Gửi thử 1 email đánh giá buổi học mẫu:  python manage.py thu_email ten@gmail.com

Kiểm tra cấu hình SMTP trong .env (EMAIL_MODE=smtp). Không ghi gì vào database.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Gửi thử một email đánh giá buổi học."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, email, **opts):
        self.stdout.write(f"Gửi bằng: {settings.EMAIL_BACKEND.rsplit('.', 2)[-2]} · từ {settings.DEFAULT_FROM_EMAIL}")
        m = EmailMultiAlternatives("Thử email đánh giá buổi học – Gia Sư Online",
                                   "Đây là email thử. Nếu bạn nhận được, hệ thống đã gửi email cho phụ huynh được.",
                                   settings.DEFAULT_FROM_EMAIL, [email])
        try:
            m.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Gửi thất bại: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Đã gửi tới {email}. Kiểm tra hộp thư (cả mục Spam)."))
