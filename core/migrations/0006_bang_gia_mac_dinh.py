"""Bảng giá mặc định theo quy định của trung tâm (Admin sửa được trên trang Bảng giá):
- Môn thường: 70.000đ/giờ, trung tâm giữ 8%
- IELTS: 130.000đ/giờ, trung tâm giữ 10%
- Gói 10 / 20 / 30 buổi: giảm 0% / 3% / 5% (áp dụng từ ngày chạy migration)
"""

from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def tao_mac_dinh(apps, schema_editor):
    NhomGia = apps.get_model("core", "NhomGia")
    MonHoc = apps.get_model("core", "MonHoc")
    GoiKhoaHoc = apps.get_model("core", "GoiKhoaHoc")

    thuong, _ = NhomGia.objects.get_or_create(
        ten="Môn thường", defaults={"don_gia_gio": 70_000, "ty_le_trung_tam": Decimal("8")})
    ielts, _ = NhomGia.objects.get_or_create(
        ten="IELTS", defaults={"don_gia_gio": 130_000, "ty_le_trung_tam": Decimal("10")})
    MonHoc.objects.filter(nhom_gia__isnull=True, ma__iexact="IELTS").update(nhom_gia=ielts)
    MonHoc.objects.filter(nhom_gia__isnull=True).update(nhom_gia=thuong)

    hom_nay = timezone.localdate()
    for so_buoi, giam in ((10, "0"), (20, "3"), (30, "5")):
        if not GoiKhoaHoc.objects.filter(so_buoi=so_buoi).exists():
            GoiKhoaHoc.objects.create(so_buoi=so_buoi, ty_le_giam=Decimal(giam), hieu_luc_tu=hom_nay)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_bang_gia")]
    operations = [migrations.RunPython(tao_mac_dinh, migrations.RunPython.noop)]
