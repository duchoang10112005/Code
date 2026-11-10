"""Danh mục cấp độ mặc định cho các môn đang có (Quản trị viên sửa / thêm trong trang quản trị)."""
from django.db import migrations

PHO_THONG = ["Lớp 1–5", "Lớp 6–7", "Lớp 8–9", "Ôn thi vào 10", "Lớp 10–11", "Lớp 12 · Luyện thi THPT"]
THEO_MA = {
    "IELTS": ["IELTS 4.0–5.0", "IELTS 5.0–6.5", "IELTS 6.5–7.5"],
    "ANH": ["Tiếng Anh tiểu học", "Tiếng Anh THCS", "Ôn thi vào 10", "Tiếng Anh THPT", "Giao tiếp"],
}


def tien(apps, schema_editor):
    MonHoc = apps.get_model("core", "MonHoc")
    CapDo = apps.get_model("core", "CapDo")
    for mon in MonHoc.objects.all():
        if CapDo.objects.filter(mon_hoc=mon).exists():
            continue
        for i, ten in enumerate(THEO_MA.get(mon.ma, PHO_THONG)):
            CapDo.objects.create(mon_hoc=mon, ten=ten, thu_tu=i)


class Migration(migrations.Migration):
    dependencies = [("core", "0018_dien_du_lieu_giao_dien_moi")]
    operations = [migrations.RunPython(tien, migrations.RunPython.noop)]
