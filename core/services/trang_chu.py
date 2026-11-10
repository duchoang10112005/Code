"""Dữ liệu trang chủ theo vai trò (tính từ dữ liệu có sẵn, không lưu thêm)."""

import calendar
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from core.models import BuoiHoc, KhoaHoc, LoiMoi, ThuLao, YeuCauHocTap
from core.services.thu_lao import dau_thang

TT = BuoiHoc.TrangThai
# Màu nhận diện từng lớp (chấm lịch, avatar) — theo bảng màu của bộ thiết kế.
MAU_LOP = [("#6366F1", "#EEF0FF", "#4F46E5"), ("#14B8A6", "#E6FAF7", "#0F766E"), ("#FF7A59", "#FFF1EA", "#C2410C"),
           ("#EAB308", "#FEF9C3", "#A16207"), ("#EC4899", "#FCE7F3", "#BE185D"), ("#0EA5E9", "#E0F2FE", "#0369A1")]
DA_DAY = [TT.HOAN_TAT, TT.DANG_XEM_XET]


def _chu_tat(ten):
    tu = (ten or "?").split()
    return (tu[0][0] + (tu[-1][0] if len(tu) > 1 else "")).upper()


def _con_lai(td):
    """timedelta → "2 giờ 40 phút" / "18 giờ" / "45 phút"."""
    phut = max(int(td.total_seconds() // 60), 0)
    g, p = divmod(phut, 60)
    if g >= 24:
        return f"{g // 24} ngày {g % 24} giờ" if g % 24 else f"{g // 24} ngày"
    if g and p:
        return f"{g} giờ {p} phút"
    return f"{g} giờ" if g else f"{p} phút"


def _loi_chao(now, ten):
    h = timezone.localtime(now).hour
    buoi = "sáng" if h < 11 else ("trưa" if h < 13 else ("chiều" if h < 18 else "tối"))
    return f"Chào buổi {buoi}, {(ten or '').split()[-1] if ten else ''} 👋"


def _tuan_lien_tuc(gia_su, hom_nay):
    """Số tuần liên tục (tính tới tuần này hoặc tuần trước) có ít nhất 1 buổi dạy; + 6 cột tuần gần nhất."""
    dau_tuan = hom_nay - timedelta(days=hom_nay.weekday())
    ngay = set(timezone.localtime(b).date() for b in BuoiHoc.objects.filter(
        gia_su=gia_su, trang_thai__in=DA_DAY, bat_dau__gte=timezone.now() - timedelta(weeks=60)
    ).values_list("bat_dau", flat=True))
    tuan_co = {d - timedelta(days=d.weekday()) for d in ngay}
    dem, t = 0, dau_tuan if dau_tuan in tuan_co else dau_tuan - timedelta(weeks=1)
    while t in tuan_co:
        dem += 1
        t -= timedelta(weeks=1)
    cot = []
    for i in range(5, -1, -1):
        t = dau_tuan - timedelta(weeks=i)
        n = sum(1 for d in ngay if t <= d < t + timedelta(days=7))
        cot.append({"h": 4 + min(n, 5) * 2, "bg": "#EAB308" if n else "#E1E4EC"})
    return dem, cot


def _thanh_tich(gia_su, hom_nay, so_buoi_tong, chuoi_tuan):
    moc_buoi = [10, 50, 100, 200, 500]
    dat_buoi = max([m for m in moc_buoi if so_buoi_tong >= m], default=0)
    moc_sau = next((m for m in moc_buoi if m > so_buoi_tong), None)
    khoa_xong = KhoaHoc.objects.filter(gia_su=gia_su, trang_thai=KhoaHoc.TrangThai.HOAN_THANH)
    thang_truoc = dau_thang(hom_nay.replace(day=1) - timedelta(days=1))
    day_thang_truoc = BuoiHoc.objects.filter(gia_su=gia_su, trang_thai__in=DA_DAY,
                                             bat_dau__date__gte=thang_truoc, bat_dau__date__lt=hom_nay.replace(day=1))
    tre_thang_truoc = BuoiHoc.objects.filter(gia_su=gia_su, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN,
                                             bat_dau__date__gte=thang_truoc, bat_dau__date__lt=hom_nay.replace(day=1))
    ds = [
        {"dat": bool(dat_buoi), "icon": "bi-award", "nhan": f"{dat_buoi or 10} buổi đã dạy",
         "phu": f"Đã dạy {so_buoi_tong} buổi" if dat_buoi else f"Còn {10 - so_buoi_tong} buổi"},
        {"dat": khoa_xong.exists(), "icon": "bi-mortarboard", "nhan": f"{khoa_xong.count() or 1} khóa hoàn thành",
         "phu": f"Gần nhất: {khoa_xong.order_by('-hoan_thanh_luc', '-pk').first().ma}" if khoa_xong.exists()
         else "Hoàn thành khóa đầu tiên"},
        {"dat": day_thang_truoc.exists() and not tre_thang_truoc.exists(), "icon": "bi-clock-history",
         "nhan": f"Tháng {thang_truoc.month} đúng hạn", "phu": "Không trễ hạn xác nhận"},
        {"dat": chuoi_tuan >= 4, "icon": "bi-fire", "nhan": "4 tuần dạy liên tục",
         "phu": f"Hiện tại {chuoi_tuan} tuần"},
    ]
    return ds, sum(1 for b in ds if b["dat"]), (f"{moc_sau} buổi (còn {moc_sau - so_buoi_tong})" if moc_sau else "")


def _lich_thang(gia_su, thang, hom_nay, mau_cua):
    """Lưới tháng (thứ 2 đầu tuần) + chấm màu theo lớp có buổi trong ngày."""
    nam, th = thang.year, thang.month
    so_ngay = calendar.monthrange(nam, th)[1]
    dau = date(nam, th, 1)
    bat_dau_luoi = dau - timedelta(days=dau.weekday())
    cuoi = date(nam, th, so_ngay)
    ket_thuc_luoi = cuoi + timedelta(days=6 - cuoi.weekday())
    cham = {}
    for b in BuoiHoc.objects.filter(gia_su=gia_su, bat_dau__date__gte=bat_dau_luoi,
                                    bat_dau__date__lte=ket_thuc_luoi).exclude(trang_thai=TT.DA_HUY):
        d = timezone.localtime(b.bat_dau).date()
        m = mau_cua(b)
        if m not in cham.setdefault(d, []):
            cham[d].append(m)
    o, d = [], bat_dau_luoi
    while d <= ket_thuc_luoi:
        o.append({"n": d.day, "trong_thang": d.month == th, "hom_nay": d == hom_nay, "cham": cham.get(d, [])[:3],
                  "ngay": d})
        d += timedelta(days=1)
    truoc = (dau - timedelta(days=1)).replace(day=1)
    sau = cuoi + timedelta(days=1)
    return {"o": o, "tieu_de": f"Tháng {th}/{nam}", "truoc": f"{truoc:%Y-%m}", "sau": f"{sau:%Y-%m}"}


def gia_su(user, thang=None, now=None):
    from core.services.buoi_hoc import nhan_buoi, quet_han

    quet_han()
    now = now or timezone.now()
    hom_nay = timezone.localdate(now)
    thang = thang or hom_nay.replace(day=1)
    ho_so = getattr(user, "ho_so_gia_su", None)
    muc_tieu = getattr(ho_so, "muc_tieu_buoi_thang", 20) or 20
    dau_t = hom_nay.replace(day=1)

    khoa = list(KhoaHoc.objects.filter(gia_su=user, trang_thai=KhoaHoc.TrangThai.DANG_HOC)
                .select_related("hoc_vien", "yeu_cau__mon_hoc").order_by("pk"))
    mau_khoa = {k.pk: MAU_LOP[i % len(MAU_LOP)] for i, k in enumerate(khoa)}

    def mau_cua(b):
        return mau_khoa.get(b.khoa_hoc_id, ("#9AA1B8",))[0] if b.khoa_hoc_id else "#FF7A59"

    buoi_thang = BuoiHoc.objects.filter(gia_su=user, trang_thai__in=DA_DAY, loai=BuoiHoc.Loai.CHINH_THUC,
                                        bat_dau__date__gte=dau_t)
    so_buoi_thang = buoi_thang.count()
    tam_tinh = ThuLao.objects.filter(gia_su=user, thang=dau_t).exclude(trang_thai=ThuLao.TrangThai.HUY) \
        .aggregate(t=Sum("so_tien"))["t"] or 0
    # Đường nhỏ thu nhập theo tuần trong tháng
    tuan = [0] * 5
    for tl in ThuLao.objects.filter(gia_su=user, thang=dau_t).exclude(trang_thai=ThuLao.TrangThai.HUY) \
            .select_related("buoi_hoc"):
        tuan[min((timezone.localtime(tl.buoi_hoc.bat_dau).day - 1) // 7, 4)] += tl.so_tien
    cao = max(tuan) or 1
    duong = " ".join(f"{i * 14},{22 - round(v * 18 / cao)}" for i, v in enumerate(tuan))
    chuoi, cot_tuan = _tuan_lien_tuc(user, hom_nay)
    so_buoi_tong = BuoiHoc.objects.filter(gia_su=user, trang_thai__in=DA_DAY).count()

    qs = BuoiHoc.objects.filter(gia_su=user).select_related("hoc_vien", "yeu_cau__mon_hoc", "khoa_hoc")
    tiep = qs.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, ket_thuc_luc__gt=now).order_by("bat_dau").first()
    sap_toi = list(qs.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=now).order_by("bat_dau")[:4])
    cho_xn = list(qs.filter(trang_thai=TT.DA_LEN_LICH, ket_thuc_luc__lte=now, han_xac_nhan__gte=now)
                  .order_by("han_xac_nhan"))
    loi_zoom = list(qs.filter(trang_thai=TT.LOI_ZOOM, bat_dau__gt=now).order_by("bat_dau"))
    tu_huy = list(qs.filter(trang_thai=TT.DA_HUY, ly_do_huy=BuoiHoc.LyDoHuy.QUA_HAN,
                            han_xac_nhan__gte=now - timedelta(days=settings.NGHIEP_VU["NGAY_MO_LAI_TOI_DA"]))
                  .exclude(yeu_cau_xu_ly__trang_thai="CHO_XU_LY").order_by("-han_xac_nhan"))
    loi_moi = list(user.loi_moi.filter(trang_thai=LoiMoi.TrangThai.CHO, het_han_luc__gt=now)
                   .select_related("yeu_cau__hoc_vien", "yeu_cau__mon_hoc").order_by("het_han_luc"))
    hoc_thu = YeuCauHocTap.objects.filter(gia_su=user, trang_thai=YeuCauHocTap.TrangThai.DA_PHAN_CONG,
                                          dang_ky_thang=False).select_related("hoc_vien", "mon_hoc")
    can_tao_thu = [y for y in hoc_thu if not y.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU, gia_su=user)
                   .exclude(trang_thai=TT.DA_HUY).exists()]
    nhac_gio = settings.NGHIEP_VU.get("NHAC_TRUOC_HAN_GIO", 3)

    gap, chu_y = [], []
    for b in cho_xn:
        con = b.han_xac_nhan - now
        (gap if con <= timedelta(hours=12) else chu_y).append({
            "loai": "Đánh giá", "icon": "bi-pencil-square", "icon_bg": "#FFF1EA", "icon_c": "#C2410C",
            "tieu_de": f"{b.yeu_cau.mon_hoc} · {b.hoc_vien.ho_ten}",
            "mo_ta": f"{nhan_buoi(b)} {timezone.localtime(b.bat_dau):%H:%M %d/%m}, chưa xác nhận hoàn tất",
            "chip": "Sắp tự hủy" if con <= timedelta(hours=nhac_gio) else "Chờ xác nhận", "chip_mau": "cam",
            "thoi_gian": f"còn {_con_lai(con)}", "gio_do": con <= timedelta(hours=nhac_gio), "icon_tg": "bi-stopwatch",
            "nut": "Đánh giá", "url": reverse("buoi_chi_tiet", args=[b.pk])})
    for lm in loi_moi:
        con = lm.het_han_luc - now
        (gap if con <= timedelta(hours=6) else chu_y).append({
            "loai": "Lời mời", "icon": "bi-envelope-open", "icon_bg": "#EEF0FF", "icon_c": "#4F46E5",
            "tieu_de": f"{lm.yeu_cau.mon_hoc} {lm.yeu_cau.trinh_do} · lớp mới",
            "mo_ta": f"Mục tiêu: {lm.yeu_cau.muc_tieu[:70]}", "chip": "Đang chờ", "chip_mau": "xanh",
            "thoi_gian": f"còn {_con_lai(con)}", "gio_do": con <= timedelta(hours=6), "icon_tg": "bi-stopwatch",
            "nut": "Xem lời mời", "url": reverse("loi_moi_cua_toi") + f"?chon={lm.pk}"})
    for b in loi_zoom:
        chu_y.append({
            "loai": "Lỗi Zoom", "icon": "bi-camera-video-off", "icon_bg": "#FDECEC", "icon_c": "#C2292E",
            "tieu_de": f"{b.yeu_cau.mon_hoc} · {b.hoc_vien.ho_ten}", "mo_ta": "Hệ thống chưa tạo được phòng Zoom cho buổi này",
            "chip": "Lỗi Zoom", "chip_mau": "do", "thoi_gian": f"{timezone.localtime(b.bat_dau):%H:%M %d/%m}",
            "gio_do": False, "icon_tg": "bi-calendar3", "nut": "Thử lại", "url": reverse("buoi_chi_tiet", args=[b.pk])})
    for b in tu_huy:
        chu_y.append({
            "loai": "Tự hủy", "icon": "bi-x-octagon", "icon_bg": "#FDECEC", "icon_c": "#C2292E",
            "tieu_de": f"{b.yeu_cau.mon_hoc} · {b.hoc_vien.ho_ten}",
            "mo_ta": f"Buổi {timezone.localtime(b.bat_dau):%H:%M %d/%m} bị tự hủy vì quá hạn xác nhận",
            "chip": "Tự hủy", "chip_mau": "do", "thoi_gian": "xin mở lại trong 7 ngày", "gio_do": False,
            "icon_tg": "bi-info-circle", "nut": "Xin mở lại", "url": reverse("buoi_chi_tiet", args=[b.pk])})
    for y in can_tao_thu:
        chu_y.append({
            "loai": "Học thử", "icon": "bi-calendar-plus", "icon_bg": "#E6FAF7", "icon_c": "#0F766E",
            "tieu_de": f"{y.mon_hoc} · {y.hoc_vien.ho_ten}", "mo_ta": "Bạn đã nhận lớp. Hẹn giờ và tạo buổi học thử",
            "chip": "Đã có gia sư", "chip_mau": "xanh_la", "thoi_gian": y.lich_mong_muon[:40], "gio_do": False,
            "icon_tg": "bi-calendar3", "nut": "Tạo buổi", "url": reverse("buoi_tao") + f"?yeu_cau={y.pk}"})
    nhom_viec = [g for g in [
        {"ten": "Gấp, trong hôm nay", "goi_y": "Sắp hết hạn", "icon": "bi-lightning-charge", "mau": "#C2410C",
         "nen": "#FFF4EF", "vien": "#FBD9C9", "cham": "#FF7A59", "muc": gap},
        {"ten": "Cần chú ý", "goi_y": "", "icon": "bi-flag", "mau": "#4A5068", "nen": "#F7F8FC", "vien": "#E6E9F2",
         "cham": "#9AA1B8", "muc": chu_y},
    ] if g["muc"]]

    tien_do = []
    for k in khoa:
        xep = k.so_buoi_dang_len_lich
        m = mau_khoa[k.pk]
        tien_do.append({"khoa": k, "ten": f"{k.yeu_cau.mon_hoc} {k.yeu_cau.trinh_do}".strip(), "hoc_vien": k.hoc_vien.ho_ten,
                        "chu_tat": _chu_tat(k.hoc_vien.ho_ten), "nen": m[1], "mau": m[2], "da": k.so_buoi_da_dung,
                        "tong": k.so_buoi_dang_ky, "w_da": round(k.so_buoi_da_dung * 100 / k.so_buoi_dang_ky),
                        "w_xep": round(xep * 100 / k.so_buoi_dang_ky)})

    hom_nay_co = qs.filter(bat_dau__date=hom_nay).exclude(trang_thai=TT.DA_HUY).count()
    chip = []
    if hom_nay_co:
        chip.append({"icon": "bi-calendar3", "mau": "#1E2235", "chu": f"Hôm nay có {hom_nay_co} buổi học"})
    sap_het = [lm for lm in loi_moi if lm.het_han_luc - now <= timedelta(hours=6)]
    if sap_het:
        chip.append({"icon": "bi-stopwatch", "mau": "#C2410C", "chu": f"{len(sap_het)} lời mời sắp hết hạn"})
    if cho_xn:
        chip.append({"icon": "bi-pencil-square", "mau": "#C2410C", "chu": f"{len(cho_xn)} buổi chờ xác nhận"})
    con_muc_tieu = max(muc_tieu - so_buoi_thang, 0)
    if so_buoi_tong == 0:
        cheer = "Chào mừng bạn! Nhận lời mời đầu tiên để bắt đầu dạy cùng trung tâm."
    else:
        cheer = (f"Bạn đã dạy {chuoi} tuần liên tục. " if chuoi >= 2 else "") + (
            f"Thêm {con_muc_tieu} buổi nữa là chạm mục tiêu tháng {hom_nay.month}." if con_muc_tieu
            else f"Bạn đã đạt mục tiêu tháng {hom_nay.month}. Tuyệt vời!")

    thanh_tich, so_dat, moc_sau = _thanh_tich(user, hom_nay, so_buoi_tong, chuoi)
    canh_bao = next((b for b in cho_xn if b.han_xac_nhan - now <= timedelta(hours=nhac_gio)), None)
    return {
        "loi_chao": _loi_chao(now, user.ho_ten), "cheer": cheer, "chip": chip,
        "so_buoi_thang": so_buoi_thang, "muc_tieu": muc_tieu,
        "vong_offset": round(113.1 * (1 - min(so_buoi_thang / muc_tieu, 1)), 1),
        "tam_tinh": tam_tinh, "duong_thu_nhap": duong, "so_lop": len(khoa), "chuoi_tuan": chuoi, "cot_tuan": cot_tuan,
        "avatar_lop": tien_do[:4],
        "tiep": tiep, "tiep_nhan": nhan_buoi(tiep) if tiep else "",
        "tiep_mo_phong_luc": (tiep.bat_dau - timedelta(minutes=settings.NGHIEP_VU.get("MO_PHONG_TRUOC_PHUT", 10)))
        if tiep else None,
        "canh_bao": canh_bao, "canh_bao_con": _con_lai(canh_bao.han_xac_nhan - now) if canh_bao else "",
        "nhom_viec": nhom_viec, "so_viec": len(gap) + len(chu_y),
        "tien_do": tien_do, "thanh_tich": thanh_tich, "so_thanh_tich": so_dat, "moc_sau": moc_sau,
        "lich": _lich_thang(user, thang, hom_nay, mau_cua),
        "chu_giai_lich": [{"ten": t["ten"], "mau": mau_khoa[t["khoa"].pk][0]} for t in tien_do[:3]],
        "sap_toi": [{"b": b, "mau": mau_cua(b)} for b in sap_toi],
        "che_do_mo_phong": settings.ZOOM_MODE == "fake",
    }
