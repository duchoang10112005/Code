"""Bảng giá theo cấp độ học (07/11/2026) – Admin sửa được trên trang Bảng giá:
- Môn phổ thông: Cơ bản 70.000đ/giờ (giữ 8%), Nâng cao 130.000đ/giờ (giữ 10%)
- IELTS: Nền tảng 150.000đ/giờ (giữ 10%), Chuyên sâu – tăng band 200.000đ/giờ (giữ 10%)
Môn có mã IELTS thuộc loại IELTS, các môn khác thuộc Môn phổ thông.
Yêu cầu học tập đang có được gán cấp độ thấp nhất của loại môn tương ứng.
"""

from decimal import Decimal

from django.db import migrations

CAP_DO = {
    "Môn phổ thông": [
        ("Cơ bản", "Củng cố kiến thức trên lớp, lấy lại gốc", 1, 70_000, "8"),
        ("Nâng cao", "Ôn thi chuyển cấp, thi chuyên, học sinh giỏi", 2, 130_000, "10"),
    ],
    "IELTS": [
        ("Nền tảng", "Xây nền 4 kỹ năng, mục tiêu band 5.0–6.0", 1, 150_000, "10"),
        ("Chuyên sâu", "Tăng band (6.5+), luyện đề chuyên sâu", 2, 200_000, "10"),
    ],
}


def tao_mac_dinh(apps, schema_editor):
    LoaiMon = apps.get_model("core", "LoaiMon")
    CapDo = apps.get_model("core", "CapDo")
    MonHoc = apps.get_model("core", "MonHoc")
    YeuCauHocTap = apps.get_model("core", "YeuCauHocTap")

    loai = {}
    for ten_loai, ds in CAP_DO.items():
        loai[ten_loai], _ = LoaiMon.objects.get_or_create(ten=ten_loai)
        for ten, mo_ta, thu_tu, gia, tl in ds:
            CapDo.objects.get_or_create(loai_mon=loai[ten_loai], ten=ten, defaults={
                "mo_ta": mo_ta, "thu_tu": thu_tu, "don_gia_gio": gia, "ty_le_trung_tam": Decimal(tl)})

    MonHoc.objects.filter(loai_mon__isnull=True, ma__iexact="IELTS").update(loai_mon=loai["IELTS"])
    MonHoc.objects.filter(loai_mon__isnull=True).update(loai_mon=loai["Môn phổ thông"])

    for yc in YeuCauHocTap.objects.filter(cap_do__isnull=True).select_related("mon_hoc"):
        cap_thap_nhat = CapDo.objects.filter(loai_mon_id=yc.mon_hoc.loai_mon_id).order_by("thu_tu").first()
        if cap_thap_nhat:
            yc.cap_do = cap_thap_nhat
            yc.save(update_fields=["cap_do"])


class Migration(migrations.Migration):
    dependencies = [("core", "0009_cap_do_hoc")]
    operations = [migrations.RunPython(tao_mac_dinh, migrations.RunPython.noop)]
