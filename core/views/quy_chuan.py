"""Trang xem trước quy chuẩn giao diện (chỉ bật khi DEBUG=True)."""

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from core.models import BuoiHoc, HoSoGiaSu, KhoaHoc, LoiMoi, MonGiaSu, ThuLao, YeuCauHocTap


def xem_truoc(request):
    if not settings.DEBUG:
        raise Http404
    nhom = [
        ("Yêu cầu học tập (D4)", YeuCauHocTap.TrangThai.choices),
        ("Lời mời nhận lớp (D5)", LoiMoi.TrangThai.choices),
        ("Khóa học (D6)", KhoaHoc.TrangThai.choices),
        ("Buổi học (D7)", BuoiHoc.TrangThai.choices),
        ("Hậu kiểm buổi học (D7)", BuoiHoc.KiemTra.choices),
        ("Bản ghi Zoom (D7)", BuoiHoc.BanGhi.choices),
        ("Gửi Zalo (D7)", BuoiHoc.GuiZalo.choices),
        ("Thù lao (D8)", ThuLao.TrangThai.choices),
        ("Hồ sơ gia sư (D2)", HoSoGiaSu.TrangThai.choices),
        ("Môn dạy của gia sư (D2)", MonGiaSu.TrangThai.choices),
    ]
    mau = [
        ("Chính", "--gs-primary", "#0F766E", "Nút chính, link, mục đang chọn"),
        ("Chính – hover", "--gs-primary-hover", "#115E59", "Khi rê chuột / nhấn"),
        ("Nhấn", "--gs-accent", "#D97706", "Huy hiệu đếm, việc cần làm"),
        ("Menu", "--gs-nav-bg", "#134E4A", "Thanh menu bên trái"),
        ("Chữ", "--gs-text", "#0F172A", "Nội dung chính"),
        ("Chữ phụ", "--gs-text-muted", "#475569", "Nhãn, chú thích"),
        ("Viền", "--gs-border", "#E2E8F0", "Card, bảng"),
        ("Nền", "--gs-bg", "#F6F8F9", "Nền trang"),
    ]
    sac_thai = [
        ("neutral", "Trung tính", "Kết thúc, không cần làm gì: Đã hủy, Đã đóng, Hết hạn"),
        ("info", "Thông tin", "Mới / đã lên lịch, chờ diễn ra: Mới, Đã lên lịch, Tạm tính"),
        ("progress", "Đang tiến hành", "Đang chạy bình thường: Đã phân công, Đang học"),
        ("success", "Thành công", "Đã xong, hợp lệ: Hoàn tất, Đã duyệt, Đã đối soát"),
        ("warning", "Cần chú ý", "Chờ người xử lý: Đang tìm gia sư, Đang xem xét, Tạm giữ"),
        ("danger", "Lỗi", "Cần sửa ngay: Lỗi Zoom, Có vấn đề, Gửi lỗi"),
    ]
    return render(request, "core/quy_chuan_giao_dien.html", {"nhom": nhom, "mau": mau, "sac_thai": sac_thai})
