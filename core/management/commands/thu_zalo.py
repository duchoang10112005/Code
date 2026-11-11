"""Gửi thử 1 tin ZNS đánh giá buổi học:  python manage.py thu_zalo 0905123456

Dùng dữ liệu mẫu, không ghi gì vào database. Mỗi tin ZNS thật bị trừ phí trong Zalo Cloud Account.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.integrations.zalo import lay_zalo_client
from core.services.tien_ich import chuan_hoa_sdt


class Command(BaseCommand):
    help = "Gửi thử một tin ZNS tới số điện thoại chỉ định."

    def add_arguments(self, parser):
        parser.add_argument("sdt", help="Số điện thoại nhận (VD 0905123456)")

    def handle(self, *args, sdt, **opts):
        so = chuan_hoa_sdt(sdt)
        if not so:
            raise CommandError("Số điện thoại không hợp lệ.")
        self.stdout.write(f"Chế độ Zalo: {settings.ZALO_MODE}{' (development)' if settings.ZALO_ZNS_DEV else ''}")
        kq = lay_zalo_client().gui_zns(so, {
            "ten_hoc_vien": "Học viên thử", "mon_hoc": "Toán", "thoi_gian": "19:00 11/11/2026",
            "gia_su": "Gia sư thử", "noi_dung": "Phương trình bậc hai", "danh_gia": "Tiếp thu tốt",
            "nhan_xet": "Em làm bài tốt, nắm chắc công thức nghiệm."})
        if not kq.thanh_cong:
            raise CommandError(kq.phan_hoi)
        self.stdout.write(self.style.SUCCESS(f"Đã gửi ZNS tới {so}: {kq.phan_hoi}"))
