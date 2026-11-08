"""Trang chung: đăng nhập, trang chủ theo vai trò."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F
from django.shortcuts import render
from django.urls import reverse_lazy

from core.forms import DangNhapForm, DoiMatKhauForm
from django.utils import timezone

from core.models import BuoiHoc, HocVien, KhoaHoc, LoiMoi, MonGiaSu, User, YeuCauHocTap
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
    hom_nay = timezone.localdate()
    chung = {"hom_nay": hom_nay, "thu_hom_nay": hom_nay.weekday()}
    if u.la_admin:
        ctx = {
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
