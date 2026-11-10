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
        from core.models import DoiGiaSu, DoiSoatThang
        from core.services.buoi_hoc import quet_han
        from core.services.ngoai_le import ds_can_xem_xet, ds_cho_lau
        quet_han()
        can_xem = list(ds_can_xem_xet())
        ctx = {
            "ds_can_xem_xet": can_xem[:5], "so_can_xem_xet_tong": len(can_xem),
            "ds_doi_cho_duyet": DoiGiaSu.objects.filter(trang_thai=DoiGiaSu.TrangThai.CHO_DUYET)
                                .select_related("khoa_hoc__hoc_vien", "khoa_hoc__yeu_cau__mon_hoc", "gia_su_cu"),
            "ds_cho_chot": DoiSoatThang.objects.filter(trang_thai=DoiSoatThang.TrangThai.DA_KIEM_TRA)
                           .select_related("gia_su", "kiem_tra_boi").order_by("thang", "gia_su__ho_ten"),
            "so_cho_lau": ds_cho_lau().count(),
            "so_buoi_hom_nay": BuoiHoc.objects.filter(bat_dau__date=hom_nay).exclude(
                trang_thai=BuoiHoc.TrangThai.DA_HUY).count(),
            "so_tai_khoan": User.objects.count(),
            "so_bi_khoa": User.objects.filter(is_active=False).count(),
            "so_gia_su": User.objects.filter(vai_tro=User.VaiTro.GIA_SU, is_active=True).count(),
            "so_hoc_vien": HocVien.objects.count(),
            "so_khoa_dang_hoc": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
            "so_buoi_xem_xet": BuoiHoc.objects.filter(trang_thai=BuoiHoc.TrangThai.DANG_XEM_XET).count(),
            # Hàng việc: môn gia sư đăng ký đang chờ duyệt, tài khoản đang bị khóa.
            "ds_mon_cho_duyet": MonGiaSu.objects.filter(trang_thai=MonGiaSu.TrangThai.CHO_DUYET,
                                                        ho_so__user__vai_tro=User.VaiTro.GIA_SU)
                                .select_related("ho_so__user", "mon_hoc").order_by("pk")[:6],
            "ds_bi_khoa": User.objects.filter(is_active=False).order_by("username")[:6],
            **chung,
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
        # Hàng việc theo nhóm (mỗi nhóm tối đa 5 dòng, xem hết ở trang danh sách).
        yc = YeuCauHocTap.objects.select_related("hoc_vien", "mon_hoc", "gia_su")
        ctx.update({
            "ds_can_moi_them": yc.filter(trang_thai=YC.DANG_TIM).exclude(loi_moi__trang_thai="CHO")
                               .order_by("tao_luc")[:5],
            "ds_yeu_cau_moi": yc.filter(trang_thai=YC.MOI).order_by("tao_luc")[:5],
            "ds_cho_chot": yc.filter(trang_thai__in=[YC.DA_PHAN_CONG, YC.HOC_THU_XONG]).order_by("phan_cong_luc")[:5],
            "ds_sap_het": KhoaHoc.objects.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC)
                          .annotate(con_lai=F("so_buoi_dang_ky") - F("so_buoi_da_dung"))
                          .filter(con_lai__lte=2).select_related("hoc_vien", "gia_su", "yeu_cau__mon_hoc")
                          .order_by("con_lai")[:5],
            "ds_loi_moi_cho": LoiMoi.objects.filter(trang_thai=LoiMoi.TrangThai.CHO)
                              .select_related("yeu_cau__hoc_vien", "yeu_cau__mon_hoc", "gia_su")
                              .order_by("het_han_luc")[:5],
            **chung,
        })
        return render(request, "core/trang_chu_tuyen_sinh.html", ctx)
    # Gia sư: chỉ thấy dữ liệu của chính mình (BRULE-23)
    from core.services.buoi_hoc import quet_han
    quet_han()
    now = timezone.now()
    buoi = u.buoi_hoc.select_related("hoc_vien", "yeu_cau__mon_hoc")
    ctx = {
        "ds_buoi_cho_xn": [b for b in buoi.filter(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH, bat_dau__lte=now)
                           .order_by("bat_dau") if b.cho_xac_nhan],
        "ds_buoi_sap_toi": buoi.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO, bat_dau__gt=now)
                           .order_by("bat_dau")[:5],
        "so_khoa_phu_trach": u.khoa_hoc_phu_trach.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC).count(),
        "so_buoi_sap_toi": u.buoi_hoc.filter(trang_thai=BuoiHoc.TrangThai.DA_LEN_LICH).count(),
        "ds_loi_moi": u.loi_moi.filter(trang_thai=LoiMoi.TrangThai.CHO, het_han_luc__gt=timezone.now())
                      .select_related("yeu_cau__hoc_vien", "yeu_cau__mon_hoc").order_by("het_han_luc"),
        "ds_khoa": u.khoa_hoc_phu_trach.filter(trang_thai=KhoaHoc.TrangThai.DANG_HOC)
                   .select_related("hoc_vien", "yeu_cau__mon_hoc").order_by("pk"),
        "ds_cho_chot": YeuCauHocTap.objects.filter(
            gia_su=u, trang_thai__in=[YeuCauHocTap.TrangThai.DA_PHAN_CONG, YeuCauHocTap.TrangThai.HOC_THU_XONG])
            .select_related("hoc_vien", "mon_hoc"),
        **chung,
    }
    return render(request, "core/trang_chu_gia_su.html", ctx)
