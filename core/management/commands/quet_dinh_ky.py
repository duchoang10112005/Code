"""Chạy định kỳ mỗi 5 phút (Task Scheduler / cron):  python manage.py quet_dinh_ky   (SD-36)

1. Hết hạn lời mời  2. Mở / kết thúc phòng Zoom  3. Nhắc & tự hủy buổi quá hạn xác nhận
4. Hậu kiểm (chấm 5 tiêu chí, bản ghi)  5. Nhắc việc, nhắc gia hạn, từ chối xin mở lại quá hạn
6. Hết hạn bản ghi  7. Hết tạm nghỉ của gia sư
"""

from django.core.management.base import BaseCommand

from core.services.dinh_ky import quet


class Command(BaseCommand):
    help = "Một lượt quét định kỳ (SD-36)."

    def handle(self, *args, **opts):
        kq = quet()
        loi = {k: v for k, v in kq.items() if k.startswith("loi_")}
        dong = ", ".join(f"{k}={v}" for k, v in kq.items() if not k.startswith("loi_"))
        self.stdout.write(self.style.SUCCESS(f"Quét xong: {dong}"))
        for k, v in loi.items():
            self.stderr.write(f"{k}: {v}")
