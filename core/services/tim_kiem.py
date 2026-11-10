"""Tìm nhanh Ctrl+K (SD-35): theo mã YC/KH/BH hoặc tên (bỏ dấu), lọc theo quyền của từng vai trò."""

import re
import unicodedata

from django.urls import reverse

from core.models import BuoiHoc, HocVien, KhoaHoc, User, YeuCauHocTap

_MA = re.compile(r"^(yc|kh|bh)0*(\d+)$")
GIOI_HAN = 6


def chuan_hoa(chuoi):
    """BH-00399 → bh00399; Gia Bảo → giabao (bỏ dấu, bỏ gạch, khoảng trắng, chữ thường)."""
    s = unicodedata.normalize("NFD", str(chuoi or "")).replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-_.]", "", s).lower()


def _khop(q, *chuoi):
    return any(q in chuan_hoa(c) for c in chuoi if c)


def _muc_khoa(k, user):
    url = reverse("khoa_cua_toi", args=[k.pk]) if user.la_gia_su else reverse("khoa_hoc_chi_tiet", args=[k.pk])
    return {"nhan": f"{k.ma} · {k.hoc_vien.ho_ten} – {k.yeu_cau.mon_hoc}", "phu": k.get_trang_thai_display(),
            "url": url, "icon": "bi-journal-bookmark"}


def _muc_buoi(b, user):
    if user.la_gia_su:
        url = reverse("buoi_chi_tiet", args=[b.pk])
    elif b.khoa_hoc_id:
        url = reverse("khoa_hoc_chi_tiet", args=[b.khoa_hoc_id])
    else:
        url = reverse("yeu_cau_chi_tiet", args=[b.yeu_cau_id])
    return {"nhan": f"{b.ma} · {b.hoc_vien.ho_ten} – {b.yeu_cau.mon_hoc}", "phu": b.trang_thai_hien_thi[1],
            "url": url, "icon": "bi-calendar3"}


def _muc_yc(y):
    return {"nhan": f"{y.ma} · {y.hoc_vien.ho_ten} – {y.mon_hoc}", "phu": y.get_trang_thai_display(),
            "url": reverse("yeu_cau_chi_tiet", args=[y.pk]), "icon": "bi-inbox"}


def tim(user, q):
    q = chuan_hoa(q)
    if len(q) < 2:
        return []
    la_gs = user.la_gia_su
    khoa_qs = KhoaHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc")
    buoi_qs = BuoiHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc")
    if la_gs:  # gia sư chỉ thấy lớp / buổi của chính mình
        khoa_qs, buoi_qs = khoa_qs.filter(gia_su=user), buoi_qs.filter(gia_su=user)

    m = _MA.match(q)
    if m:
        loai, so = m.group(1), int(m.group(2))
        if loai == "kh":
            ds = [_muc_khoa(k, user) for k in khoa_qs.filter(pk=so)]
            return [{"ten": "Khóa học", "muc": ds}] if ds else []
        if loai == "bh":
            ds = [_muc_buoi(b, user) for b in buoi_qs.filter(pk=so)]
            return [{"ten": "Buổi học", "muc": ds}] if ds else []
        if not la_gs:
            ds = [_muc_yc(y) for y in YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc").filter(pk=so)]
            return [{"ten": "Yêu cầu", "muc": ds}] if ds else []
        return []

    khoa = [_muc_khoa(k, user) for k in khoa_qs.order_by("-pk")[:500]
            if _khop(q, k.hoc_vien.ho_ten, k.yeu_cau.mon_hoc.ten)][:GIOI_HAN]
    if la_gs:
        return [{"ten": "Lớp của tôi", "muc": khoa}] if khoa else []

    yc = [_muc_yc(y) for y in YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc").order_by("-pk")[:500]
          if _khop(q, y.hoc_vien.ho_ten, y.hoc_vien.ten_phu_huynh)][:GIOI_HAN]
    hv = [{"nhan": h.ho_ten, "phu": f"PH {h.ten_phu_huynh}", "icon": "bi-person",
           "url": reverse("hoc_vien_chi_tiet", args=[h.pk])}
          for h in HocVien.objects.order_by("-pk")[:1000] if _khop(q, h.ho_ten, h.ten_phu_huynh)][:GIOI_HAN]
    gs = [{"nhan": u.ho_ten, "phu": u.email, "icon": "bi-mortarboard",
           "url": reverse("gia_su_chi_tiet", args=[u.ho_so_gia_su.pk])}
          for u in User.objects.filter(vai_tro=User.VaiTro.GIA_SU, ho_so_gia_su__isnull=False)
          .select_related("ho_so_gia_su") if _khop(q, u.ho_ten, u.username, u.email)][:GIOI_HAN]
    nhom = [{"ten": t, "muc": ds} for t, ds in (("Yêu cầu", yc), ("Khóa học", khoa), ("Học viên", hv),
                                                 ("Gia sư", gs)) if ds]
    if user.la_admin:
        tk = [{"nhan": u.ho_ten, "phu": u.get_vai_tro_display(), "icon": "bi-person-gear",
               "url": reverse("tai_khoan_sua", args=[u.pk])}
              for u in User.objects.all() if _khop(q, u.ho_ten, u.username, u.email)][:GIOI_HAN]
        if tk:
            nhom.append({"ten": "Tài khoản", "muc": tk})
    return nhom
