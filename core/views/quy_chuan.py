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
        ("Bìa sổ", "--gs-cover", "#1D3A7A", "Menu trái, nút chính, đường kẻ đầu nhóm"),
        ("Mực xanh", "--gs-ink", "#1E40AF", "Link, mã hồ sơ, dữ liệu"),
        ("Mực đỏ", "--gs-red", "#B71C1C", "Chỉ cho lời phê: việc cần xử lý, số đếm cần làm"),
        ("Chữ", "--gs-text", "#16213B", "Nội dung chính"),
        ("Chữ phụ", "--gs-text-muted", "#45557D", "Nhãn, chú thích"),
        ("Viền nhãn vở", "--gs-tag", "#8AA0D0", "Viền kép của nhãn hồ sơ"),
        ("Viền", "--gs-border", "#D5DDEF", "Trang giấy, bảng"),
        ("Nền giấy", "--gs-bg", "#EEF2F9", "Nền trang"),
    ]
    sac_thai = [
        ("neutral", "Trung tính (nét đứt)", "Chờ hoặc không cần làm gì: Hết hạn, Vô hiệu"),
        ("info", "Thông tin (nét đứt)", "Mới / đã lên lịch, chờ diễn ra: Mới, Đã lên lịch, Tạm tính"),
        ("progress", "Đang chạy (nét liền)", "Đang chạy bình thường: Đã phân công, Đang học"),
        ("success", "Xong (nét liền)", "Đã xong, hợp lệ: Hoàn tất, Đã duyệt, Đã đối soát"),
        ("warning", "Chờ xử lý (nét đứt)", "Chờ người xử lý: Đang tìm gia sư, Đang xem xét, Tạm giữ"),
        ("danger", "Lỗi / đã đóng (gạch ngang)", "Cần sửa ngay: Lỗi Zoom, Có vấn đề, Gửi lỗi"),
    ]
    return render(request, "core/quy_chuan_giao_dien.html", {"nhom": nhom, "mau": mau, "sac_thai": sac_thai})
