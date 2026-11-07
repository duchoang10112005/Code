# Chính sách giá 07/11/2026: không giảm giá theo gói; gói dài có quyền lợi không tốn tiền.

from decimal import Decimal

from django.db import migrations, models

QUYEN_LOI = {
    10: ["Học thử miễn phí trước khi đăng ký", "Giữ nguyên học phí suốt khóa"],
    20: ["Học thử miễn phí trước khi đăng ký", "Giữ nguyên học phí suốt khóa",
         "Ưu tiên giữ nguyên gia sư suốt khóa"],
    30: ["Học thử miễn phí trước khi đăng ký", "Giữ nguyên học phí suốt khóa",
         "Ưu tiên giữ nguyên gia sư suốt khóa", "Ưu tiên xếp khung giờ đẹp, dời lịch linh hoạt hơn"],
}


def ap_dung_chinh_sach_moi(apps, schema_editor):
    """Chỉ sửa các mức MẶC ĐỊNH (do migration tạo, tao_boi trống) – mức Admin tự đặt giữ nguyên."""
    GoiKhoaHoc = apps.get_model("core", "GoiKhoaHoc")
    GoiKhoaHoc.objects.filter(tao_boi__isnull=True).update(ty_le_giam=Decimal("0"))
    for goi in GoiKhoaHoc.objects.filter(quyen_loi=""):
        goi.quyen_loi = "\n".join(QUYEN_LOI.get(goi.so_buoi, []))
        goi.save(update_fields=["quyen_loi"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_bang_gia_mac_dinh"),
    ]

    operations = [
        migrations.AddField(
            model_name="goikhoahoc",
            name="quyen_loi",
            field=models.TextField(blank=True, help_text="Mỗi dòng một quyền lợi, hiện cho NV tuyển sinh khi báo giá.",
                                   verbose_name="Quyền lợi của gói"),
        ),
        migrations.RunPython(ap_dung_chinh_sach_moi, migrations.RunPython.noop),
    ]
