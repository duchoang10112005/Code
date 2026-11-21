"""Mở / đóng phòng Zoom đúng giờ:  python manage.py dong_phong   (chạy mỗi PHÚT bằng cron)

Zoom không tự ngắt phòng khi hết thời lượng đã đặt, nên lệnh này gọi API "kết thúc phòng" ngay khi buổi học hết giờ.
Nhẹ hơn quet_dinh_ky (không hậu kiểm, không gửi mail) nên chạy mỗi phút được.
"""

from django.core.management.base import BaseCommand

from core.services.dinh_ky import mo_dong_phong


class Command(BaseCommand):
    help = "Đánh dấu phòng mở và kết thúc phòng Zoom của các buổi đã hết giờ."

    def handle(self, *args, **opts):
        kq = mo_dong_phong()
        if kq["mo_phong"] or kq["dong_phong"]:
            self.stdout.write(f"mở {kq['mo_phong']} · đóng {kq['dong_phong']}")
