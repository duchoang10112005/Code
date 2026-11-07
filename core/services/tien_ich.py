import re


def chuan_hoa_sdt(sdt):
    """Đưa số điện thoại Việt Nam về dạng 84xxxxxxxxx (định dạng Zalo ZNS yêu cầu).

    Trả về None nếu không hợp lệ.  VD: "0905 123 456" → "84905123456".
    """
    so = re.sub(r"[^\d+]", "", sdt or "")
    if so.startswith("+"):
        so = so[1:]
    if so.startswith("0"):
        so = "84" + so[1:]
    if re.fullmatch(r"84[35789]\d{8}", so):
        return so
    return None


def thong_diep_loi(err):
    """Gộp các thông điệp của một ValidationError thành một câu để hiện cho người dùng."""
    return " ".join(err.messages) if hasattr(err, "messages") else str(err)


def dinh_dang_tien(so):
    """120000 → "120.000đ" (dấu chấm ngăn cách hàng nghìn theo cách viết Việt Nam)."""
    if so is None or so == "":
        return "—"
    return f"{int(so):,}".replace(",", ".") + "đ"

