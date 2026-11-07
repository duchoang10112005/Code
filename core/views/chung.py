"""Trang chung: đăng nhập, trang chủ theo vai trò."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F
from django.shortcuts import render
from django.urls import reverse_lazy

from core.forms import DangNhapForm, DoiMatKhauForm
from core.models import BuoiHoc, HocVien, KhoaHoc, User, YeuCauHocTap
from core.services.yeu_cau import quet_loi_moi_het_han


class DangNhapView(auth_views.LoginView):
    template_name = "core/dang_nhap.html"
    authentication_form = DangNhapForm
    redirect_authenticated_user = True


class DoiMatKhauView(SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "core/doi_mat_khau.html"
    form_class = DoiMatKhauForm
    success_url = reverse_lazy("trang_chu")
    success_message = "Đã đổi mật khẩu."


@login_required
def trang_chu(request):
    u = request.user
    if u.la_admin:
        ctx = {
            "so_tai_khoan": User.objects.count(),
            "so_bi_khoa": User.objects.filter(is_active=False).count(),
            "so_gia_su": User.objects.filter(vai_tro=User.VaiTro.GIA_SU, is_active=True).count(),
            "so_hoc_vien": HocVien.objects.count(),
            "so_khoa_dang_hoc": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
            "so_buoi_xem_xet": BuoiHoc.objects.filter(trang_thai=BuoiHoc.TrangThai.DANG_XEM_XET).count(),
        }
        return render(request, "core/trang_chu_admin.html", ctx)
    if u.la_tuyen_sinh:
        quet_loi_moi_het_han()
        YC = YeuCauHocTap.TrangThai
        ctx = {
            "so_yeu_cau_moi": YeuCauHocTap.objects.filter(trang_thai=YC.MOI).count(),
            "so_dang_tim": YeuCauHocTap.objects.filter(trang_thai=YC.DANG_TIM).count(),
            # Đang tìm nhưng không còn lời mời nào đang chờ → cần NVTS mời thêm gia sư.
            "so_can_moi_them": YeuCauHocTap.objects.filter(trang_thai=YC.DANG_TIM)
                                .exclude(loi_moi__trang_thai="CHO").count(),
            "so_cho_chot": YeuCauHocTap.objects.filter(trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG]).count(),
            "so_sap_het": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC)
                           .annotate(con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung"))
                           .filter(con_lai__lte=2).count(),
            "so_khoa_dang_hoc": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
        }
        return render(request, "core/trang_chu_tuyen_sinh.html", ctx)
    # Gia sư: chỉ thấy dữ liệu của chính mình (BRULE-23)
    ctx = {
        "so_khoa_phu_trach": u.khoa_hoc_phu_trach.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
        "so_buoi_sap_toi": u.buoi_hoc.filter(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH).count(),
    }
    return render(request, "core/trang_chu_gia_su.html", ctx)
