from django.contrib.auth import views as auth_views
from django.urls import path

from core.views import bang_gia, chung, gia_su, khoa_hoc, quy_chuan, tai_khoan, yeu_cau

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

    # Phần 3 – Yêu cầu học tập, học viên, lời mời nhận lớp (PB-02..PB-06)
    path("yeu-cau/", yeu_cau.danh_sach, name="yeu_cau_danh_sach"),
    path("yeu-cau/tao/", yeu_cau.tao, name="yeu_cau_tao"),
    path("yeu-cau/<int:pk>/", yeu_cau.chi_tiet, name="yeu_cau_chi_tiet"),
    path("yeu-cau/<int:pk>/sua/", yeu_cau.sua, name="yeu_cau_sua"),
    path("yeu-cau/<int:pk>/gui-loi-moi/", yeu_cau.gui_loi_moi, name="yeu_cau_gui_loi_moi"),
    path("yeu-cau/<int:pk>/dong/", yeu_cau.dong, name="yeu_cau_dong"),
    path("hoc-vien/", yeu_cau.hoc_vien_danh_sach, name="hoc_vien_danh_sach"),
    path("hoc-vien/<int:pk>/", yeu_cau.hoc_vien_chi_tiet, name="hoc_vien_chi_tiet"),
    path("loi-moi/", yeu_cau.loi_moi_cua_toi, name="loi_moi_cua_toi"),
    path("loi-moi/<int:pk>/nhan/", yeu_cau.nhan_lop, name="loi_moi_nhan"),
    path("loi-moi/<int:pk>/tu-choi/", yeu_cau.tu_choi_loi_moi, name="loi_moi_tu_choi"),

    # Phần 4 – Khóa học (PB-07..PB-10)
    path("yeu-cau/<int:pk>/ket-qua-hoc-thu/", khoa_hoc.ghi_ket_qua_hoc_thu, name="yeu_cau_ket_qua_hoc_thu"),
    path("yeu-cau/<int:pk>/tao-khoa/", khoa_hoc.tao, name="khoa_hoc_tao"),
    path("khoa-hoc/", khoa_hoc.danh_sach, name="khoa_hoc_danh_sach"),
    path("khoa-hoc/<int:pk>/", khoa_hoc.chi_tiet, name="khoa_hoc_chi_tiet"),
    path("khoa-hoc/<int:pk>/trang-thai/", khoa_hoc.doi_trang_thai, name="khoa_hoc_doi_trang_thai"),
    path("lop-cua-toi/", khoa_hoc.lop_cua_toi, name="lop_cua_toi"),
    path("lop-cua-toi/khoa/<int:pk>/", khoa_hoc.khoa_cua_toi, name="khoa_cua_toi"),

    # Bảng giá (Admin cấu hình, NVTS xem để báo giá)
    path("bang-gia/", bang_gia.xem, name="bang_gia"),
    path("bang-gia/nhom/<int:pk>/", bang_gia.sua_nhom, name="bang_gia_sua_nhom"),
    path("bang-gia/gan-mon/", bang_gia.gan_mon, name="bang_gia_gan_mon"),
    path("bang-gia/goi/", bang_gia.them_goi, name="bang_gia_them_goi"),
    path("bang-gia/goi/<int:pk>/quyen-loi/", bang_gia.sua_quyen_loi, name="bang_gia_sua_quyen_loi"),

    # Xem trước quy chuẩn giao diện (chỉ khi DEBUG)
    path("quy-chuan-giao-dien/", quy_chuan.xem_truoc, name="quy_chuan_giao_dien"),
]
