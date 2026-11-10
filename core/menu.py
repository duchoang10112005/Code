"""Menu trái và bảng lệnh Ctrl+K của giao diện mới, theo vai trò (khớp các màn Trang chủ trong bộ UI).

Mỗi mục: (nhãn, icon, url_name hoặc None nếu "Sắp có", các tiền tố url_name để tô sáng, khóa huy hiệu).
"""

from django.urls import NoReverseMatch, reverse

THONG_TIN_VAI_TRO = {
    "GIA_SU": {"phu_de": "Góc giảng dạy", "lop_body": "vt-gia-su"},
    "TUYEN_SINH": {"phu_de": "Bảng điều phối", "lop_body": "vt-tuyen-sinh"},
    "ADMIN": {"phu_de": "Trung tâm điều hành", "lop_body": "vt-admin"},
}

TRANG_CHU = ("Trang chủ", "bi-house-door", "trang_chu", ("trang_chu",), None)

MENU = {
    "GIA_SU": [
        ("GIẢNG DẠY", [
            TRANG_CHU,
            ("Lời mời nhận lớp", "bi-envelope-open", "loi_moi_cua_toi", ("loi_moi",), "so_loi_moi_cho"),
            ("Lớp của tôi", "bi-collection", "lop_cua_toi", ("lop_cua_toi", "khoa_cua_toi"), None),
            ("Buổi học", "bi-calendar3", "buoi_cua_toi", ("buoi_",), "so_buoi_cho_xac_nhan"),
            ("Thu nhập", "bi-wallet2", "thu_nhap", ("thu_nhap",), None),
        ]),
        ("CÁ NHÂN", [
            ("Hồ sơ của tôi", "bi-person-circle", "ho_so_cua_toi", ("ho_so_",), None),
        ]),
    ],
    "TUYEN_SINH": [
        ("VẬN HÀNH", [
            TRANG_CHU,
            ("Yêu cầu học tập", "bi-inbox", "yeu_cau_danh_sach", ("yeu_cau_",), "so_yeu_cau_can_xu_ly"),
            ("Học viên", "bi-people", "hoc_vien_danh_sach", ("hoc_vien_",), None),
            ("Gia sư", "bi-mortarboard", "gia_su_danh_sach", ("gia_su_",), None),
            ("Khóa học", "bi-journal-bookmark", "khoa_hoc_danh_sach", ("khoa_hoc_",), "so_khoa_sap_het"),
            ("Hậu kiểm buổi học", "bi-clipboard-check", "hau_kiem", ("hau_kiem",), "so_hau_kiem_cho"),
        ]),
        ("TÀI CHÍNH", [
            ("Đối soát thù lao", "bi-calculator", "doi_soat", ("doi_soat",), None),
        ]),
    ],
    "ADMIN": [
        ("", [TRANG_CHU]),
        ("VẬN HÀNH", [
            ("Cần xem xét", "bi-exclamation-diamond", "xem_xet", ("xem_xet", "duyet_doi_gia_su"), "so_can_xem_xet"),
            ("Yêu cầu học tập", "bi-inbox", "yeu_cau_danh_sach", ("yeu_cau_",), None),
            ("Khóa học", "bi-journal-bookmark", "khoa_hoc_danh_sach", ("khoa_hoc_",), None),
            ("Gia sư", "bi-mortarboard", "gia_su_danh_sach", ("gia_su_",), "so_mon_cho_duyet"),
        ]),
        ("TÀI CHÍNH", [
            ("Đối soát thù lao", "bi-calculator", "doi_soat", ("doi_soat",), None),
        ]),
        ("QUẢN TRỊ", [
            ("Tài khoản", "bi-people", "tai_khoan_danh_sach", ("tai_khoan_",), None),
            ("Nhật ký thao tác", "bi-clock-history", "nhat_ky", ("nhat_ky",), None),
        ]),
    ],
}

# Lệnh nhanh trong bảng Ctrl+K (nhãn, icon, url_name).
LENH = {
    "GIA_SU": [("Xem lời mời nhận lớp", "bi-envelope-open", "loi_moi_cua_toi"),
               ("Tạo buổi học", "bi-plus-lg", "buoi_tao"),
               ("Xem thu nhập tháng này", "bi-wallet2", "thu_nhap"),
               ("Cập nhật hồ sơ, giờ rảnh", "bi-person-circle", "ho_so_cua_toi")],
    "TUYEN_SINH": [("Tạo yêu cầu mới", "bi-plus-lg", "yeu_cau_tao"),
                   ("Yêu cầu học tập", "bi-inbox", "yeu_cau_danh_sach"),
                   ("Khóa học", "bi-journal-bookmark", "khoa_hoc_danh_sach"),
                   ("Đối soát thù lao", "bi-calculator", "doi_soat")],
    "ADMIN": [("Cần xem xét", "bi-exclamation-diamond", "xem_xet"),
              ("Tạo tài khoản", "bi-person-plus", "tai_khoan_tao"),
              ("Đối soát thù lao", "bi-calculator", "doi_soat"),
              ("Nhật ký thao tác", "bi-clock-history", "nhat_ky")],
}


def _url(ten):
    try:
        return reverse(ten)
    except NoReverseMatch:  # màn chưa làm → hiện "Sắp có"
        return None


def menu_cho(user, url_name, huy_hieu):
    nhom = []
    for tieu_de, muc in MENU.get(user.vai_tro, []):
        ds = []
        for nhan, icon, ten, tien_to, khoa in muc:
            dang_o = bool(url_name) and any(url_name == t or url_name.startswith(t) for t in tien_to)
            ds.append({"nhan": nhan, "icon": icon, "url": _url(ten), "dang_o": dang_o,
                       "huy_hieu": huy_hieu.get(khoa, 0) if khoa else 0})
        nhom.append({"tieu_de": tieu_de, "muc": ds})
    return nhom


def lenh_cho(user):
    return [{"nhan": n, "icon": i, "url": u} for n, i, t in LENH.get(user.vai_tro, []) if (u := _url(t))]


def chu_viet_tat(ho_ten):
    tu = (ho_ten or "?").split()
    return (tu[0][0] + (tu[-1][0] if len(tu) > 1 else "")).upper()
