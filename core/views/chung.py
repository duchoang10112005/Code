"""Trang chung: đăng nhập, trang chủ theo vai trò."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F
from django.shortcuts import render
from django.urls import reverse_lazy

from core.forms import DangNhapForm, DatMatKhauBatBuocForm, DoiMatKhauForm
from django.utils import timezone

from core.models import BuoiHoc, HocVien, KhoaHoc, LoiMoi, MonGiaSu, User, YeuCauHocTap
from core.services.yeu_cau import quet_loi_moi_het_han


class DangNhapView(auth_views.LoginView):
    """SD-01: đăng nhập theo vai trò (tên đăng nhập / email / SĐT), "Ghi nhớ đăng nhập trên máy này"."""

    template_name = "core/dang_nhap.html"
    authentication_form = DangNhapForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        r = super().form_valid(form)
        if not self.request.POST.get("ghi_nho"):
            self.request.session.set_expiry(0)  # hết phiên khi đóng trình duyệt
        return r

    def get_context_data(self, **kwargs):
        from django.conf import settings
        ctx = super().get_context_data(**kwargs)
        qtv = User.objects.filter(vai_tro=User.VaiTro.ADMIN, is_active=True).order_by("pk").first()
        ctx["lien_he_qtv"] = qtv
        ctx["ghi_nho"] = self.request.method != "POST" or bool(self.request.POST.get("ghi_nho"))
        if settings.DEBUG:  # Bản demo: nút điền nhanh tài khoản mẫu (lệnh seed_demo)
            from core.management.commands.seed_demo import MAT_KHAU_DEMO
            mau = [("giasu1", "Gia sư", "#FF7A59"), ("tuyensinh", "Tuyển sinh", "#6366F1"),
                   ("admin", "Quản trị viên", "#14B8A6")]
            co = set(User.objects.filter(username__in=[m[0] for m in mau], is_active=True)
                     .values_list("username", flat=True))
            ctx["tai_khoan_mau"] = [{"username": u, "nhan": n, "mau": c} for u, n, c in mau if u in co]
            ctx["mat_khau_mau"] = MAT_KHAU_DEMO
        return ctx


class DoiMatKhauView(SuccessMessageMixin, auth_views.PasswordChangeView):
    """Tự đổi mật khẩu, hoặc bắt buộc đặt mật khẩu mới lần đầu (SD-02, cờ phai_doi_mat_khau)."""

    success_url = reverse_lazy("trang_chu")
    success_message = "Đã đổi mật khẩu."

    @property
    def bat_buoc(self):
        return getattr(self.request.user, "phai_doi_mat_khau", False)

    def get_template_names(self):
        return ["core/dat_mat_khau_moi.html" if self.bat_buoc else "core/doi_mat_khau.html"]

    def get_form_class(self):
        return DatMatKhauBatBuocForm if self.bat_buoc else DoiMatKhauForm

    def form_valid(self, form):
        bat_buoc = self.bat_buoc
        r = super().form_valid(form)
        u = self.request.user
        if bat_buoc:
            User.objects.filter(pk=u.pk).update(phai_doi_mat_khau=False)
            u.phai_doi_mat_khau = False
        from core.services.nhat_ky import ghi_nhat_ky
        ghi_nhat_ky(u, "Đổi mật khẩu", u.username, "Đặt mật khẩu mới lần đầu" if bat_buoc else "",
                    loai="TAI_KHOAN")
        return r


@login_required
def trang_chu(request):
    u = request.user
    hom_nay = timezone.localdate()
    chung = {"hom_nay": hom_nay, "thu_hom_nay": hom_nay.weekday()}
    if u.la_admin:
        from datetime import datetime
        from core.services import trang_chu as tc
        try:
            thang = datetime.strptime(request.GET.get("thang", ""), "%Y-%m").date()
        except ValueError:
            thang = None
        ctx = tc.quan_tri(u, thang)
        return render(request, "core/trang_chu_admin.html", ctx)
    if u.la_tuyen_sinh:
        from datetime import datetime
        from core.services import trang_chu as tc
        try:
            thang = datetime.strptime(request.GET.get("thang", ""), "%Y-%m").date()
        except ValueError:
            thang = None
        return render(request, "core/trang_chu_tuyen_sinh.html", tc.tuyen_sinh(u, thang))
    # Gia sư: chỉ thấy dữ liệu của chính mình (BRULE-23)
    from datetime import datetime
    from core.services import trang_chu as tc
    from core.services.buoi_hoc import link_lop
    thang = None
    try:
        thang = datetime.strptime(request.GET.get("thang", ""), "%Y-%m").date()
    except ValueError:
        pass
    ctx = tc.gia_su(u, thang)
    ctx["now"] = timezone.now()
    if ctx["tiep"]:
        ctx["link_lop_tiep"] = link_lop(ctx["tiep"], request)
    return render(request, "core/trang_chu_gia_su.html", ctx)


def bai_test_demo(request):
    """Trang công khai (DEMO): gom bài test năng lực của mọi môn vào MỘT đường dẫn. Chỉ hiển thị, không chấm điểm thật."""
    from core.models import MonHoc
    return render(request, "core/bai_test_demo.html", {"ds_mon": MonHoc.objects.filter(dang_mo=True).order_by("ten")})
