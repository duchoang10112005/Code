"""Điền dữ liệu cho các cột mới (02 · mục 7, đợt 2–3–5)."""
from datetime import timedelta

from django.db import migrations
from django.db.models import F

GIO_KHUNG = {"SANG": (480, 660), "CHIEU": (840, 1020), "TOI_SOM": (1050, 1140), "TOI": (1140, 1260)}


def _khung(tu, den):
    a, b = tu.hour * 60 + tu.minute, den.hour * 60 + den.minute
    tot, best = 0, ""
    for k, (x, y) in GIO_KHUNG.items():
        giao = min(y, b) - max(x, a)
        if giao > tot:
            tot, best = giao, k
    return best


def tien(apps, schema_editor):
    KhoaHoc = apps.get_model("core", "KhoaHoc")
    HocVien = apps.get_model("core", "HocVien")
    HoSoGiaSu = apps.get_model("core", "HoSoGiaSu")
    LoiMoi = apps.get_model("core", "LoiMoi")
    BuoiHoc = apps.get_model("core", "BuoiHoc")
    LichRanh = apps.get_model("core", "LichRanh")
    YeuCau = apps.get_model("core", "YeuCauHocTap")
    HauKiem = apps.get_model("core", "HauKiemBuoi")

    for kh in KhoaHoc.objects.all():
        kh.ma_lop = kh.ma_lop or f"KH-{kh.pk:04d}"
        kh.tuyen_sinh_phu_trach_id = kh.tuyen_sinh_phu_trach_id or kh.tao_boi_id
        kh.save(update_fields=["ma_lop", "tuyen_sinh_phu_trach"])
    HocVien.objects.filter(tuyen_sinh_phu_trach__isnull=True).update(
        tuyen_sinh_phu_trach=F("tao_boi"))

    for hs in HoSoGiaSu.objects.filter(nguoi_moi__isnull=True):
        lm = LoiMoi.objects.filter(gia_su_id=hs.user_id, gui_boi__isnull=False).order_by("gui_luc").first()
        if lm:
            hs.nguoi_moi_id = lm.gui_boi_id
            hs.save(update_fields=["nguoi_moi"])

    for b in BuoiHoc.objects.all():
        b.ket_thuc_luc = b.bat_dau + timedelta(minutes=b.thoi_luong_phut)
        b.save(update_fields=["ket_thuc_luc"])

    da_co = set()
    for lr in LichRanh.objects.order_by("ho_so_id", "thu", "tu_gio"):
        k = _khung(lr.tu_gio, lr.den_gio)
        if k and (lr.ho_so_id, lr.thu, k) not in da_co:
            da_co.add((lr.ho_so_id, lr.thu, k))
            lr.khung = k
            lr.save(update_fields=["khung"])

    YeuCau.objects.filter(ket_qua_hoc_thu="TIEP_TUC").update(ket_qua_hoc_thu="DONG_Y")
    YeuCau.objects.filter(ket_qua_hoc_thu="DUNG").update(ket_qua_hoc_thu="KHONG_DANG_KY")

    for b in BuoiHoc.objects.filter(xac_nhan_luc__isnull=False).select_related("gia_su"):
        if HauKiem.objects.filter(buoi_hoc_id=b.pk).exists():
            continue
        if b.kiem_tra == "HOP_LE":
            kl = "HOP_LE"
        elif b.kiem_tra == "CO_VAN_DE":
            kl = "CO_VAN_DE"
        elif b.kiem_tra == "DA_XU_LY":
            kl = "DA_XU_LY_KHONG_TINH" if b.trang_thai == "DA_HUY" else "DA_XU_LY_TINH"
        else:
            kl = "CHUA_KIEM_TRA"
        hs = HoSoGiaSu.objects.filter(user_id=b.gia_su_id).first()
        HauKiem.objects.create(
            buoi_hoc_id=b.pk, nguoi_phu_trach_id=getattr(hs, "nguoi_moi_id", None), ket_luan=kl,
            da_cham=b.kiem_tra not in ("CHUA_KIEM_TRA",), do_dai_nhan_xet=min(len(b.danh_gia or ""), 32767),
            da_gui_zalo=b.zalo_trang_thai == "DA_GUI",
        )


def lui(apps, schema_editor):
    YeuCau = apps.get_model("core", "YeuCauHocTap")
    YeuCau.objects.filter(ket_qua_hoc_thu="DONG_Y").update(ket_qua_hoc_thu="TIEP_TUC")
    YeuCau.objects.filter(ket_qua_hoc_thu="KHONG_DANG_KY").update(ket_qua_hoc_thu="DUNG")


class Migration(migrations.Migration):
    dependencies = [("core", "0017_giao_dien_moi_cot_va_bang")]
    operations = [migrations.RunPython(tien, lui)]
