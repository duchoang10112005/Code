"""Chạy định kỳ (Windows Task Scheduler, mỗi 15 phút):  python manage.py quet_dinh_ky

- Nhắc gia sư sắp hết hạn xác nhận, tự hủy buổi quá hạn (cũng chạy nhẹ mỗi khi mở trang).
- Hậu kiểm Zoom: lấy người tham gia + bản ghi cho các buổi đã xác nhận.
- Hết hạn lời mời nhận lớp.
"""

from django.core.management.base import BaseCommand

from core.services.buoi_hoc import hau_kiem, quet_han
from core.services.yeu_cau import quet_loi_moi_het_han


class Command(BaseCommand):
    help = "Quét hạn xác nhận buổi học, hậu kiểm Zoom, hết hạn lời mời."

    def handle(self, *args, **opts):
        n_huy = quet_han()
        quet_loi_moi_het_han()
        n_kiem = hau_kiem()
        self.stdout.write(self.style.SUCCESS(f"Đã tự hủy {n_huy} buổi quá hạn, hậu kiểm {n_kiem} buổi."))
