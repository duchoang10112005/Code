"""Kiểm tra 3 khóa Zoom trong .env:  python manage.py thu_zoom

Tạo một phòng thử 30 phút sau 1 ngày, in link, rồi xóa ngay. Không ghi gì vào database.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.integrations.zoom import ZoomError, lay_zoom_client


class Command(BaseCommand):
    help = "Thử kết nối Zoom API: tạo rồi xóa một phòng thử."

    def handle(self, *args, **opts):
        self.stdout.write(f"Chế độ Zoom: {settings.ZOOM_MODE}")
        try:
            zoom = lay_zoom_client()
            phong = zoom.tao_phong(settings.ZOOM_HOST_EMAIL_MAC_DINH, "Phòng thử – Trung tâm Gia sư",
                                   timezone.now() + timedelta(days=1), 30, ghi_hinh=False)
            self.stdout.write(f"Đã tạo phòng {phong.meeting_id}\n  Link học viên: {phong.join_url}")
            zoom.xoa_phong(phong.meeting_id)
            self.stdout.write(self.style.SUCCESS("Đã xóa phòng thử. Kết nối Zoom hoạt động."))
        except ZoomError as exc:
            raise CommandError(str(exc))
