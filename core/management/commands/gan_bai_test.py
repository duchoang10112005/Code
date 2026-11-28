"""Gắn link bài test (trang demo /bai-test/#<mã môn>) cho mọi môn chưa có link:  python manage.py gan_bai_test

Dùng SITE_URL trong .env làm tên miền. Điền luôn số câu, thời gian, điểm đạt nếu còn trống. Không ghi đè link Admin đã tự nhập.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import MonHoc


class Command(BaseCommand):
    help = "Gắn link bài test demo cho các môn chưa có link."

    def handle(self, *args, **opts):
        n = 0
        for m in MonHoc.objects.all():
            if m.bai_test_url:
                continue
            m.bai_test_url = f"{settings.SITE_URL}/bai-test/#{m.ma.lower()}"
            m.bai_test_so_cau = m.bai_test_so_cau or 30
            m.bai_test_phut = m.bai_test_phut or 45
            m.diem_dat = m.diem_dat or 7
            m.save(update_fields=["bai_test_url", "bai_test_so_cau", "bai_test_phut", "diem_dat"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Đã gắn link bài test cho {n} môn. Xem tại {settings.SITE_URL}/bai-test/"))
