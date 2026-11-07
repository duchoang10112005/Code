"""Tạo dữ liệu demo: `python manage.py seed_demo`

Chạy lại nhiều lần không bị trùng (dùng get_or_create). Phần 3–6 sẽ bổ sung thêm
yêu cầu, khóa học, buổi học mẫu ở đủ các trạng thái.
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import HoSoGiaSu, LichRanh, MonGiaSu, MonHoc, User

MAT_KHAU_DEMO = "Demo@2026"

MON_HOC = [
    ("TOAN", "Toán"), ("ANH", "Tiếng Anh"), ("LY", "Vật lý"),
    ("HOA", "Hóa học"), ("VAN", "Ngữ văn"), ("IELTS", "IELTS"),
]

TAI_KHOAN = [
    # username, họ tên, vai trò, email
    ("admin", "Hoàng Trung Đức", User.VaiTro.ADMIN, "admin@giasu.local"),
    ("tuyensinh", "Trần Đình Phước Hưng", User.VaiTro.TUYEN_SINH, "tuyensinh@giasu.local"),
    ("giasu1", "Nguyễn Minh Anh", User.VaiTro.GIA_SU, "giasu1@giasu.local"),
    ("giasu2", "Lê Hoàng Nam", User.VaiTro.GIA_SU, "giasu2@giasu.local"),
    ("giasu3", "Phạm Thu Trang", User.VaiTro.GIA_SU, "giasu3@giasu.local"),
]

# Gia sư → [(mã môn, cấp độ, trạng thái duyệt)], lịch rảnh [(thứ, từ, đến)], trạng thái hồ sơ
GIA_SU = {
    "giasu1": ([("TOAN", "Lớp 6–12", "DA_DUYET"), ("LY", "Lớp 10–12", "DA_DUYET")],
               [(0, time(18), time(21)), (2, time(18), time(21)), (5, time(8), time(11))], "HOAT_DONG"),
    "giasu2": ([("ANH", "Lớp 1–9", "DA_DUYET"), ("IELTS", "Band 5.0–6.5", "CHO_DUYET")],
               [(1, time(19), time(21)), (3, time(19), time(21))], "HOAT_DONG"),
    "giasu3": ([("TOAN", "Lớp 1–5", "DA_DUYET"), ("VAN", "Lớp 6–9", "DA_DUYET")],
               [(4, time(17), time(20)), (6, time(8), time(12))], "HOAT_DONG"),
}


class Command(BaseCommand):
    help = "Tạo tài khoản và dữ liệu mẫu để demo."

    @transaction.atomic
    def handle(self, *args, **options):
        mon = {}
        for ma, ten in MON_HOC:
            mon[ma], _ = MonHoc.objects.get_or_create(ma=ma, defaults={"ten": ten})

        admin_user = None
        for username, ho_ten, vai_tro, email in TAI_KHOAN:
            u, tao_moi = User.objects.get_or_create(
                username=username,
                defaults={"ho_ten": ho_ten, "vai_tro": vai_tro, "email": email,
                          "is_staff": vai_tro == User.VaiTro.ADMIN,
                          "is_superuser": vai_tro == User.VaiTro.ADMIN},
            )
            if tao_moi:
                u.set_password(MAT_KHAU_DEMO)
                u.save()
            if vai_tro == User.VaiTro.ADMIN:
                admin_user = u
            self.stdout.write(f"  {'+' if tao_moi else '='} {username:<10} {u.get_vai_tro_display()}")

        for username, (ds_mon, ds_lich, trang_thai) in GIA_SU.items():
            ho_so, _ = HoSoGiaSu.objects.get_or_create(user=User.objects.get(username=username))
            ho_so.trang_thai = trang_thai
            ho_so.kinh_nghiem = ho_so.kinh_nghiem or "3 năm dạy kèm trực tuyến."
            ho_so.save()
            for ma, cap_do, tt in ds_mon:
                MonGiaSu.objects.get_or_create(
                    ho_so=ho_so, mon_hoc=mon[ma],
                    defaults={"cap_do": cap_do, "trang_thai": tt,
                              "duyet_boi": admin_user if tt == "DA_DUYET" else None,
                              "duyet_luc": timezone.now() if tt == "DA_DUYET" else None},
                )
            if not ho_so.lich_ranh.exists():
                LichRanh.objects.bulk_create(
                    [LichRanh(ho_so=ho_so, thu=t, tu_gio=a, den_gio=b) for t, a, b in ds_lich]
                )

        self.stdout.write(self.style.SUCCESS(
            "Xong. Mật khẩu chung của các tài khoản demo xem trong README_DEMO.md."
        ))
