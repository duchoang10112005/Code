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


def chi_so_gia_su(user, now=None):
    """4 chỉ số tháng trên trang chủ gia sư (dùng cho lần tải trang và API tự cập nhật)."""
    now = now or timezone.now()
    hom_nay = timezone.localdate(now)
    dau_t = hom_nay.replace(day=1)
    ho_so = getattr(user, "ho_so_gia_su", None)
    muc_tieu = getattr(ho_so, "muc_tieu_buoi_thang", 20) or 20
    so_buoi_thang = BuoiHoc.objects.filter(gia_su=user, trang_thai__in=DA_DAY, loai=BuoiHoc.Loai.CHINH_THUC,
                                           bat_dau__date__gte=dau_t).count()
    thu_lao = ThuLao.objects.filter(gia_su=user, thang=dau_t).exclude(trang_thai=ThuLao.TrangThai.HUY)
    tam_tinh = thu_lao.aggregate(t=Sum("so_tien"))["t"] or 0
    tuan = [0] * 5  # đường nhỏ thu nhập theo tuần trong tháng
    for tl in thu_lao.select_related("buoi_hoc"):
        tuan[min((timezone.localtime(tl.buoi_hoc.bat_dau).day - 1) // 7, 4)] += tl.so_tien
    cao = max(tuan) or 1
    chuoi, cot_tuan = _tuan_lien_tuc(user, hom_nay)
    return {
        "so_buoi_thang": so_buoi_thang, "muc_tieu": muc_tieu,
        "vong_offset": round(113.1 * (1 - min(so_buoi_thang / muc_tieu, 1)), 1),
        "tam_tinh": tam_tinh, "duong_thu_nhap": " ".join(f"{i * 14},{22 - round(v * 18 / cao)}" for i, v in enumerate(tuan)),
        "so_lop": KhoaHoc.objects.filter(gia_su=user, trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
        "chuoi_tuan": chuoi, "cot_tuan": cot_tuan,
    }


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

    cs = chi_so_gia_su(user, now)
    so_buoi_thang, chuoi = cs["so_buoi_thang"], cs["chuoi_tuan"]
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
        **cs,
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


# =============================================================================
# Trang chủ Tuyển sinh – bảng điều phối
# =============================================================================
def chi_so_tuyen_sinh(now=None):
    """4 chỉ số: yêu cầu đang mở, lời mời đang chờ (sắp hết hạn), khóa sắp hết buổi, % yêu cầu có gia sư tháng này."""
    from django.db.models import F
    now = now or timezone.now()
    dau_t = timezone.localdate(now).replace(day=1)
    YC = YeuCauHocTap.TrangThai
    mo = YeuCauHocTap.objects.filter(trang_thai__in=[YC.MOI, YC.DANG_TIM, YC.DA_PHAN_CONG, YC.HOC_THU_XONG])
    cho = LoiMoi.objects.filter(trang_thai=LoiMoi.TrangThai.CHO, het_han_luc__gt=now)
    sap_het_han = cho.filter(het_han_luc__lte=now + timedelta(hours=6)).count()
    so_cho = cho.count()
    sap_het = KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).annotate(
        con=F("so_buoi_dang_ky") - F("so_buoi_da_dung")).filter(
        con__lte=settings.NGHIEP_VU.get("NGUONG_SAP_HET_BUOI", 2)).count()
    trong_thang = YeuCauHocTap.objects.filter(tao_luc__date__gte=dau_t).exclude(trang_thai=YC.DONG)
    tong = trong_thang.count()
    co_gs = trong_thang.filter(trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG, YC.CHINH_THUC]).count()
    ty_le = round(co_gs * 100 / tong) if tong else 0
    ngay = [timezone.localdate(now) - timedelta(days=i) for i in range(6, -1, -1)]
    dem = [YeuCauHocTap.objects.filter(tao_luc__date=d).count() for d in ngay]
    cao = max(dem) or 1
    return {"so_mo": mo.count(), "so_cho": so_cho, "sap_het_han": sap_het_han,
            "w_sap_het_han": round(sap_het_han * 100 / so_cho) if so_cho else 0, "so_sap_het": sap_het,
            "ty_le_co_gs": ty_le, "vong_ty_le": round(113.1 * (1 - ty_le / 100), 1), "thang_cs": dau_t.month,
            "duong_yc": " ".join(f"{i * 9},{22 - round(v * 18 / cao)}" for i, v in enumerate(dem))}


def _dong(ma, ten, mo_ta, chip, mau_chip, han, han_do, nut, url):
    return {"ma": ma, "ten": ten, "mo_ta": mo_ta, "chip": chip, "mau_chip": mau_chip, "han": han,
            "han_do": han_do, "nut": nut, "url": url}


def _viec_tuyen_sinh(now):
    from django.db.models import F
    from django.urls import reverse
    from core.models import DoiGiaSu
    from core.services import yeu_cau as dv_yc
    from core.services.thu_lao import tong_hop
    YC = YeuCauHocTap.TrangThai
    yc_qs = YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su").prefetch_related("loi_moi", "buoi_hoc")
    gap, hom_nay, tuan = [], [], []
    for y in yc_qs.filter(trang_thai__in=[YC.MOI, YC.DANG_TIM, YC.DA_PHAN_CONG]).order_by("tao_luc"):
        b = dv_yc.buoc_tiep_theo(y, now)
        ten = f"{y.hoc_vien.ho_ten} · {y.mon_hoc} {y.trinh_do}"
        url = reverse("yeu_cau_chi_tiet", args=[y.pk])
        if y.trang_thai == YC.MOI:
            gap.append(_dong(y.ma, ten, b["chu"], "Mới", "xanh", f"tạo {_con_lai(now - y.tao_luc)} trước", False,
                             "Tìm gia sư", url))
        elif y.trang_thai == YC.DANG_TIM and b["mau"] == "do":
            gap.append(_dong(y.ma, ten, b["chu"], "Chưa có gia sư", "do", "cần mời lại", True, "Mời lại", url))
        elif y.trang_thai == YC.DANG_TIM:
            (gap if b["mau"] == "cam" else hom_nay).append(_dong(
                y.ma, ten, "Đã mời gia sư, chưa ai nhận", "Đang mời gia sư", "cam", b["chu"].split(" · ")[-1],
                b["mau"] == "cam", "Mời thêm", url))
        elif "Ghi kết quả" in b["chu"]:
            gap.append(_dong(y.ma, ten, "Học thử xong · gọi phụ huynh lấy kết quả", "Học thử", "tim", "đã dạy xong",
                             False, "Ghi kết quả", url))
        elif "Gọi lại" in b["chu"]:
            (gap if b["mau"] == "do" else tuan).append(_dong(
                y.ma, ten, "Phụ huynh cần thêm thời gian", "Đã có gia sư", "xanh_la", b["chu"].split(" · ")[-1],
                b["mau"] == "do", "Gọi lại", url))
        elif "Mở khóa" in b["chu"]:
            hom_nay.append(_dong(y.ma, ten, "Phụ huynh đăng ký chính thức", "Đã có gia sư", "xanh_la", "chờ mở khóa",
                                 False, "Mở khóa", url))
    for y in yc_qs.filter(trang_thai=YC.HOC_THU_XONG):
        hom_nay.append(_dong(y.ma, f"{y.hoc_vien.ho_ten} · {y.mon_hoc} {y.trinh_do}", "Phụ huynh đồng ý đăng ký",
                             "Học thử", "tim", "chờ mở khóa", False, "Mở khóa",
                             reverse("yeu_cau_chi_tiet", args=[y.pk]) + "?mo=khoa"))
    for k in KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).annotate(
            con=F("so_buoi_dang_ky") - F("so_buoi_da_dung")).filter(
            con__lte=settings.NGHIEP_VU.get("NGUONG_SAP_HET_BUOI", 2)).select_related("hoc_vien", "yeu_cau__mon_hoc"):
        hom_nay.append(_dong(k.ma, f"{k.hoc_vien.ho_ten} · {k.yeu_cau.mon_hoc}",
                             f"Còn {k.con}/{k.so_buoi_dang_ky} buổi · gọi phụ huynh gia hạn", "Đang học", "xanh_la",
                             f"còn {k.con} buổi", False, "Xem khóa", reverse("khoa_hoc_chi_tiet", args=[k.pk])))
    for d in DoiGiaSu.objects.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET).select_related(
            "khoa_hoc__hoc_vien", "khoa_hoc__yeu_cau__mon_hoc"):
        hom_nay.append(_dong(d.khoa_hoc.ma, f"{d.khoa_hoc.hoc_vien.ho_ten} · {d.khoa_hoc.yeu_cau.mon_hoc}",
                             "Đổi gia sư lần 2 · chờ Quản trị viên duyệt", "Chờ duyệt", "xanh",
                             f"{_con_lai(now - d.tao_luc)} trước", False, "Xem",
                             reverse("khoa_hoc_chi_tiet", args=[d.khoa_hoc_id])))
    hom = timezone.localdate(now)
    thang_truoc = (hom.replace(day=1) - timedelta(days=1)).replace(day=1)
    bang = tong_hop(thang_truoc)
    chua = [d for d in bang if d.trang_thai in ("CHUA_KIEM_TRA", "CAN_KIEM_TRA_LAI")]
    if chua:
        tuan.append(_dong(f"T{thang_truoc:%m/%Y}", f"Thù lao tháng {thang_truoc:%m/%Y} cần kiểm tra",
                          f"{len(bang)} gia sư · {len(bang) - len(chua)} đã kiểm tra, {len(chua)} chưa", "Đang mở",
                          "cam", "trước khi chốt", False, "Đối soát", reverse("doi_soat") + f"?thang={thang_truoc:%Y-%m}"))
    return gap, hom_nay, tuan


def tuyen_sinh(user, thang=None, now=None):
    from core.models import NhacViec
    from core.services import yeu_cau as dv_yc
    from core.services.buoi_hoc import quet_han

    dv_yc.quet_loi_moi_het_han()
    quet_han()
    now = now or timezone.now()
    hom_nay = timezone.localdate(now)
    thang = thang or hom_nay.replace(day=1)
    cs = chi_so_tuyen_sinh(now)
    gap, hom_nay_ds, tuan = _viec_tuyen_sinh(now)
    nhom = [g for g in [
        {"ma": "gap", "ten": "Gấp, cần xử lý ngay", "goi_y": "Phụ huynh đang chờ", "icon": "bi-lightning-charge",
         "mau": "#C2410C", "nen": "#FFF4EF", "vien": "#FBD9C9", "cham": "#FF7A59", "muc": gap},
        {"ma": "hom_nay", "ten": "Trong hôm nay", "goi_y": "", "icon": "bi-sun", "mau": "#4F46E5", "nen": "#F5F6FF",
         "vien": "#DCDFFB", "cham": "#6366F1", "muc": hom_nay_ds},
        {"ma": "tuan", "ten": "Trong tuần", "goi_y": "", "icon": "bi-calendar-week", "mau": "#4A5068",
         "nen": "#F7F8FC", "vien": "#E6E9F2", "cham": "#9AA1B8", "muc": tuan}] if g["muc"]]

    cham, sap_toi = {}, []

    def them(d, m):
        if m not in cham.setdefault(d, []):
            cham[d].append(m)
    for b in BuoiHoc.objects.filter(loai=BuoiHoc.Loai.HOC_THU, trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO + [TT.HOAN_TAT],
                                    bat_dau__gte=now - timedelta(days=40)).select_related("yeu_cau__mon_hoc", "gia_su"):
        them(timezone.localtime(b.bat_dau).date(), "#6366F1")
        if b.bat_dau >= now:
            sap_toi.append({"luc": b.bat_dau, "mau": "#6366F1", "ten": f"Học thử · {b.yeu_cau.ma}",
                            "phu": f"{b.yeu_cau.mon_hoc} · gia sư {b.gia_su.ho_ten}"})
    for lm in LoiMoi.objects.filter(trang_thai=LoiMoi.TrangThai.CHO, het_han_luc__gt=now).select_related(
            "yeu_cau__mon_hoc", "yeu_cau__hoc_vien"):
        them(timezone.localtime(lm.het_han_luc).date(), "#FF7A59")
        sap_toi.append({"luc": lm.het_han_luc, "mau": "#FF7A59", "ten": f"Hạn lời mời · {lm.yeu_cau.ma}",
                        "phu": f"{lm.yeu_cau.mon_hoc} · {lm.yeu_cau.hoc_vien.ho_ten}"})
    for nv in NhacViec.objects.filter(nguoi_phu_trach=user, xong_luc__isnull=True):
        them(timezone.localtime(nv.han_luc).date(), "#14B8A6")
        sap_toi.append({"luc": nv.han_luc, "mau": "#14B8A6", "ten": nv.get_loai_display(), "phu": nv.noi_dung[:60]})
    sap_toi.sort(key=lambda x: x["luc"])
    chip = []
    if gap:
        chip.append({"icon": "bi-lightning-charge", "mau": "#C2410C", "chu": f"{len(gap)} việc gấp hôm nay"})
    if cs["sap_het_han"]:
        chip.append({"icon": "bi-stopwatch", "mau": "#1E2235", "chu": f"{cs['sap_het_han']} lời mời sắp hết hạn"})
    so_kq = sum(1 for g in gap if g["nut"] == "Ghi kết quả")
    if so_kq:
        chip.append({"icon": "bi-clipboard-check", "mau": "#1E2235", "chu": f"{so_kq} kết quả học thử chưa ghi"})
    return {**cs, "loi_chao": _loi_chao(now, user.ho_ten),
            "cheer": (f"Tháng này {cs['ty_le_co_gs']}% yêu cầu đã có gia sư. " if cs["ty_le_co_gs"] else "")
            + (f"Còn {len(gap)} việc gấp đang chờ bạn." if gap else "Không có việc gấp nào."),
            "chip": chip, "nhom_viec": nhom, "so_viec": len(gap) + len(hom_nay_ds) + len(tuan),
            "lich": _lich_thang_tu_cham(thang, hom_nay, cham), "sap_toi": sap_toi[:5]}


def _lich_thang_tu_cham(thang, hom_nay, cham):
    nam, th = thang.year, thang.month
    dau = date(nam, th, 1)
    cuoi = date(nam, th, calendar.monthrange(nam, th)[1])
    d, kt, o = dau - timedelta(days=dau.weekday()), cuoi + timedelta(days=6 - cuoi.weekday()), []
    while d <= kt:
        o.append({"n": d.day, "trong_thang": d.month == th, "hom_nay": d == hom_nay, "cham": cham.get(d, [])[:3]})
        d += timedelta(days=1)
    truoc = (dau - timedelta(days=1)).replace(day=1)
    return {"o": o, "tieu_de": f"Tháng {th}/{nam}", "truoc": f"{truoc:%Y-%m}", "sau": f"{cuoi + timedelta(days=1):%Y-%m}"}


# =============================================================================
# Trang chủ Quản trị viên: ngoại lệ cần quyết định
# =============================================================================
def quan_tri(user, thang=None, now=None):
    from django.db.models import Sum
    from django.urls import reverse
    from core.models import DoiSoatThang, HoSoGiaSu, KhoaHoc, NhatKy, ThuLao
    from core.services import thu_lao as dv_tl
    from core.services import xem_xet as dv_xx
    from core.services.buoi_hoc import quet_han

    quet_han()
    now = now or timezone.now()
    hom_nay = timezone.localdate(now)
    thang = thang or hom_nay.replace(day=1)
    tq = dv_xx.tong_quan_trang_chu(now)
    ngay_chot = settings.NGHIEP_VU.get("NGAY_CHOT_THU_LAO", 15)
    nhom = []
    if tq["cho_lau"]:
        nhom.append({"ten": "Yêu cầu chờ quá 24 giờ", "goi_y": "Gán thẳng gia sư", "icon": "bi-hourglass-split",
                     "mau": "#C2292E", "nen": "#FDECEC", "vien": "#F8C9CA", "cham": "#E5484D", "muc": [
            {"ma": y.ma, "ten": f"{y.hoc_vien.ho_ten} · {y.mon_hoc} {y.trinh_do}",
             "mo_ta": "Đang mời gia sư, chưa ai nhận" if y.trang_thai == "DANG_TIM" else "Chưa gửi lời mời",
             "chip": f"Chờ {int((now - y.tao_luc).total_seconds() // 3600)} giờ", "mau_chip": "do",
             "han": f"tạo {timezone.localtime(y.tao_luc):%d/%m · %H:%M}", "han_do": True, "nut": "Gán gia sư",
             "url": reverse("yeu_cau_chi_tiet", args=[y.pk])} for y in tq["cho_lau"]]})
    if tq["mo_lai_loi"]:
        nhom.append({"ten": "Mở lại buổi · lỗi hệ thống", "goi_y": "", "icon": "bi-camera-video", "mau": "#C2410C",
                     "nen": "#FFF4E5", "vien": "#FFD9A8", "cham": "#F59E0B", "muc": [
            {"ma": x["ma"], "ten": x["tieu_de"], "mo_ta": x["mo_ta"], "chip": x["nhan"],
             "mau_chip": "xam" if x["loai"] == "tu_huy" else "do",
             "han": (f"còn {max((x['han'] - now).days, 0)} ngày mở lại" if x["loai"] == "tu_huy" and x["han"]
                     else x["cho"]), "han_do": False, "nut": "Xem xét",
             "url": reverse("xem_xet") + f"?chon={x['key']}"} for x in tq["mo_lai_loi"]]})
    if tq["cho_duyet"]:
        nhom.append({"ten": "Chờ duyệt", "goi_y": "", "icon": "bi-check2-square", "mau": "#4F46E5", "nen": "#F5F6FF",
                     "vien": "#DCDFFB", "cham": "#6366F1", "muc": [
            {"ma": x["ma"], "ten": x["tieu_de"], "mo_ta": x["mo_ta"], "chip": "Chờ duyệt", "mau_chip": "xanh",
             "han": x["cho"], "han_do": False, "nut": "Duyệt",
             "url": x.get("url") or reverse("xem_xet") + f"?chon={x['key']}"} for x in tq["cho_duyet"]]})
    if tq["cho_chot"]:
        muc = []
        for t in tq["cho_chot"]:
            th = t["thang"]
            tong = len(dv_tl.tong_hop(th))
            han = dv_tl.thang_sau(th).replace(day=min(ngay_chot, 28))
            muc.append({"ma": f"T{th.month}/{th.year}", "ten": f"Thù lao tháng {th.month}",
                        "mo_ta": f"{tong} gia sư · {len(t['ds'])} đã kiểm tra, chờ chốt",
                        "chip": f"Đã kiểm tra {len(t['ds'])}/{tong}", "mau_chip": "xanh_la",
                        "han": f"hạn chốt {han:%d/%m}", "han_do": han <= hom_nay, "nut": "Chốt tháng",
                        "url": reverse("doi_soat") + f"?thang={th:%Y-%m}"})
        nhom.append({"ten": "Thù lao chờ chốt", "goi_y": "", "icon": "bi-lock", "mau": "#0F766E", "nen": "#E6FAF7",
                     "vien": "#B5EDE3", "cham": "#14B8A6", "muc": muc})

    # Lịch: hạn chốt thù lao (xanh ngọc), hạn mở lại buổi tự hủy (đỏ)
    cham, sap_toi = {}, []
    han_chot = hom_nay.replace(day=min(ngay_chot, 28))
    if han_chot < hom_nay:
        han_chot = dv_tl.thang_sau(hom_nay.replace(day=1)).replace(day=min(ngay_chot, 28))
    thang_truoc = (han_chot.replace(day=1) - timedelta(days=1)).replace(day=1)
    cham.setdefault(han_chot, []).append("#14B8A6")
    tong_tr = dv_tl.tong_hop(thang_truoc)
    sap_toi.append({"luc": han_chot, "mau": "#14B8A6", "ten": f"Hạn chốt thù lao T{thang_truoc.month}",
                    "phu": f"{len(tong_tr)} gia sư · " + f"{sum(d.tong for d in tong_tr):,}đ".replace(",", ".")})
    for x in tq["mo_lai_loi"]:
        if x["loai"] in ("tu_huy", "mo_lai") and x["han"]:
            d = timezone.localtime(x["han"]).date()
            cham.setdefault(d, []).append("#E5484D")
            sap_toi.append({"luc": d, "mau": "#E5484D", "ten": f"Hết hạn mở lại {x['ma']}", "phu": x["tieu_de"]})
    sap_toi.sort(key=lambda x: x["luc"])
    so_cho_lau = len(tq["cho_lau"])
    chip = []
    if so_cho_lau:
        chip.append({"icon": "bi-hourglass-split", "mau": "#C2292E", "chu": f"{so_cho_lau} yêu cầu chờ quá 24 giờ"})
    if tq["cho_duyet"]:
        chip.append({"icon": "bi-check2-square", "mau": "#4F46E5", "chu": f"{len(tq['cho_duyet'])} mục chờ duyệt"})
    chip.append({"icon": "bi-lock", "mau": "#0F766E", "chu": f"Hạn chốt thù lao {han_chot:%d/%m}"})
    so_nl = sum(len(g["muc"]) for g in nhom)
    th_nay = hom_nay.replace(day=1)
    return {
        "loi_chao": _loi_chao(now, user.ho_ten), "chip": chip, "nhom_viec": nhom, "so_viec": so_nl,
        "cheer": (f"Có {so_nl} ngoại lệ cần bạn quyết định." if so_nl else "Không có ngoại lệ nào đang chờ.")
        + (f" {so_cho_lau} yêu cầu đã chờ quá 24 giờ, nên xử lý trước." if so_cho_lau else ""),
        "lich": _lich_thang_tu_cham(thang, hom_nay, cham), "sap_toi": sap_toi[:4],
        "nhat_ky": NhatKy.objects.select_related("nguoi_thuc_hien").order_by("-thoi_diem")[:3],
        "tong_quan": {"thang": th_nay.month,
                      "gia_su": HoSoGiaSu.objects.filter(trang_thai=HoSoGiaSu.TrangThai.HOAT_DONG,
                                                         user__is_active=True, user__vai_tro="GIA_SU").count(),
                      "khoa": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
                      "buoi": BuoiHoc.objects.filter(bat_dau__date__gte=th_nay, bat_dau__date__lt=dv_tl.thang_sau(th_nay))
                      .exclude(trang_thai=TT.DA_HUY).count(),
                      "tam_tinh": ThuLao.objects.filter(thang=th_nay, trang_thai=ThuLao.TrangThai.TAM_TINH)
                      .aggregate(s=Sum("so_tien"))["s"] or 0},
    }
