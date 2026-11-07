from django.contrib.auth import views as auth_views
from django.urls import path

from core.views import chung, gia_su, quy_chuan, tai_khoan

urlpatterns = [
    path("", chung.trang_chu, name="trang_chu"),
    path("dang-nhap/", chung.DangNhapView.as_view(), name="dang_nhap"),
    path("dang-xuat/", auth_views.LogoutView.as_view(), name="dang_xuat"),
    path(
        "doi-mat-khau/",
        chung.DoiMatKhauView.as_view(),
        name="doi_mat_khau",
    ),

    # Admin – quản lý tài khoản & nhật ký (PB-01, PB-23)
    path("tai-khoan/", tai_khoan.danh_sach, name="tai_khoan_danh_sach"),
    path("tai-khoan/tao/", tai_khoan.tao, name="tai_khoan_tao"),
    path("tai-khoan/<int:pk>/sua/", tai_khoan.sua, name="tai_khoan_sua"),
    path("tai-khoan/<int:pk>/doi-trang-thai/", tai_khoan.doi_trang_thai, name="tai_khoan_doi_trang_thai"),
    path("nhat-ky/", tai_khoan.nhat_ky, name="nhat_ky"),

    # Phần 2 – Hồ sơ gia sư (PB-04)
    path("ho-so/", gia_su.ho_so_cua_toi, name="ho_so_cua_toi"),
    path("ho-so/cap-nhat/", gia_su.cap_nhat_ho_so, name="ho_so_cap_nhat"),
    path("ho-so/mon/dang-ky/", gia_su.dang_ky_mon, name="ho_so_dang_ky_mon"),
    path("ho-so/mon/<int:pk>/rut/", gia_su.rut_mon, name="ho_so_rut_mon"),
    path("ho-so/lich/them/", gia_su.them_lich, name="ho_so_them_lich"),
    path("ho-so/lich/<int:pk>/xoa/", gia_su.xoa_lich, name="ho_so_xoa_lich"),
    path("gia-su/", gia_su.danh_sach, name="gia_su_danh_sach"),
    path("gia-su/<int:pk>/", gia_su.chi_tiet, name="gia_su_chi_tiet"),
    path("gia-su/mon/<int:pk>/xu-ly/", gia_su.xu_ly_mon, name="gia_su_xu_ly_mon"),
    path("gia-su/<int:pk>/trang-thai/", gia_su.doi_trang_thai, name="gia_su_doi_trang_thai"),

    # Xem trước quy chuẩn giao diện (chỉ khi DEBUG)
    path("quy-chuan-giao-dien/", quy_chuan.xem_truoc, name="quy_chuan_giao_dien"),
]
