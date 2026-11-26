"""Dọn dữ liệu demo để KHÔNG còn buổi học sắp tới nào chiếm phòng Zoom:  python manage.py gon_demo

Trung tâm chỉ có 1 phòng Zoom (1 license Pro) nên mọi buổi học không được trùng giờ nhau. Dữ liệu mẫu có vài buổi "đã lên lịch"
ở tương lai khiến người dùng demo hay bị báo trùng giờ. Lệnh này hủy các buổi đó (lý do: Trung tâm hủy, xóa luôn phòng Zoom nếu có)
rồi in bảng tóm tắt từng gia sư: số khóa chính thức, số buổi học thử. Chạy lại nhiều lần vẫn an toàn.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BuoiHoc, KhoaHoc, User
from core.services import buoi_hoc as dv


def don_buoi_tuong_lai():
    """Hủy mọi buổi đang giữ chỗ phòng Zoom mà chưa bắt đầu. Trả về danh sách mã buổi đã hủy."""
    da_huy = []
    ds = BuoiHoc.objects.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=timezone.now()).select_related("gia_su")
    for b in ds:
        dv.huy_buoi(None, b, BuoiHoc.LyDoHuy.ADMIN_HUY, "Dọn dữ liệu demo: nhường chỗ phòng Zoom", boi_he_thong=True)
        da_huy.append(b.ma)
    return da_huy


class Command(BaseCommand):
    help = "Hủy các buổi học sắp tới của dữ liệu mẫu để không chiếm phòng Zoom (demo không bị báo trùng giờ)."

    def handle(self, *args, **opts):
        da_huy = don_buoi_tuong_lai()
        self.stdout.write(self.style.SUCCESS(f"Đã hủy {len(da_huy)} buổi sắp tới: {', '.join(da_huy) or '—'}"))
        self.stdout.write("Gia sư | khóa chính thức đang học | buổi học thử đã có")
        for u in User.objects.filter(vai_tro=User.VaiTro.GIA_SU).order_by("username"):
            n_khoa = KhoaHoc.objects.filter(gia_su=u, trang_thai=KhoaHoc.TrangThai.DANG_HOC).count()
            n_thu = BuoiHoc.objects.filter(gia_su=u, loai=BuoiHoc.Loai.HOC_THU).count()
            self.stdout.write(f"{u.username:10} {u.ho_ten or u.username:24} {n_khoa} khóa | {n_thu} buổi học thử")
