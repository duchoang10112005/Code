"""Django admin – chỉ để nhóm tra cứu dữ liệu khi phát triển (/django-admin/).
Người dùng thật thao tác qua giao diện chính của hệ thống."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models as m


@admin.register(m.User)
class TaiKhoanAdmin(UserAdmin):
    list_display = ("username", "ho_ten", "vai_tro", "email", "is_active")
    list_filter = ("vai_tro", "is_active")
    search_fields = ("username", "ho_ten", "email")
    fieldsets = UserAdmin.fieldsets + (("Thông tin trung tâm", {"fields": ("vai_tro", "ho_ten", "so_dien_thoai",
                                                                         "phai_doi_mat_khau", "ly_do_khoa", "khoa_luc")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Thông tin trung tâm", {"fields": ("vai_tro", "ho_ten", "email")}),)


class MonGiaSuInline(admin.TabularInline):
    model = m.MonGiaSu
    extra = 0


class LichRanhInline(admin.TabularInline):
    model = m.LichRanh
    extra = 0


@admin.register(m.HoSoGiaSu)
class HoSoGiaSuAdmin(admin.ModelAdmin):
    list_display = ("user", "trang_thai", "email_zoom")
    inlines = [MonGiaSuInline, LichRanhInline]


@admin.register(m.YeuCauHocTap)
class YeuCauAdmin(admin.ModelAdmin):
    list_display = ("__str__", "trang_thai", "gia_su", "tao_luc")
    list_filter = ("trang_thai", "mon_hoc")


@admin.register(m.KhoaHoc)
class KhoaHocAdmin(admin.ModelAdmin):
    list_display = ("__str__", "gia_su", "so_buoi_dang_ky", "so_buoi_da_dung", "trang_thai")


@admin.register(m.BuoiHoc)
class BuoiHocAdmin(admin.ModelAdmin):
    list_display = ("__str__", "loai", "gia_su", "trang_thai", "kiem_tra", "ban_ghi_trang_thai")
    list_filter = ("loai", "trang_thai", "kiem_tra")


@admin.register(m.NhatKy)
class NhatKyAdmin(admin.ModelAdmin):
    """Nhật ký chỉ thêm: không sửa, không xóa (SD-35)."""
    list_display = ("thoi_diem", "nguoi_thuc_hien", "hanh_dong", "doi_tuong", "ma_doi_tuong")
    list_filter = ("loai_doi_tuong",)
    search_fields = ("ma_doi_tuong", "hanh_dong", "chi_tiet")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(m.NhatKyGuiTin)
class NhatKyGuiTinAdmin(admin.ModelAdmin):
    list_display = ("thoi_diem", "kenh", "nguoi_nhan", "thanh_cong")


for model in (m.MonHoc, m.MonGiaSu, m.LichRanh, m.HocVien, m.LoiMoi, m.ThuLao, m.DieuChinhThuLao, m.DoiSoatThang,
              m.MaMoiGiaSu, m.CapDo, m.MinhChung, m.GiaHanKhoa, m.TaiKhoanZoom, m.BanNhapDanhGia, m.HauKiemBuoi,
              m.YeuCauXuLy, m.ThongBao, m.NhacViec, m.SuCoHeThong):
    admin.site.register(model)
