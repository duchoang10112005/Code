"""Phần 5b – Xử lý ngoại lệ: Admin xem xét buổi học, sửa số buổi, gán thẳng gia sư; NVTS đổi gia sư."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import BuoiHoc, DoiGiaSu, KhoaHoc, User, YeuCauHocTap
from core.permissions import ADMIN, TUYEN_SINH, vai_tro_required
from core.services import ngoai_le as dv
from core.services.buoi_hoc import quet_han
from core.services.tien_ich import thong_diep_loi as _loi


def _du_lieu_zoom(buoi):
    """Tỷ lệ tham gia gia sư / học viên lấy trực tiếp từ Zoom (None nếu không có dữ liệu)."""
    if not buoi or not buoi.zoom_meeting_id:
        return None
    from core.integrations.zoom import ZoomError
    from core.services.buoi_hoc import lay_zoom_client
    try:
        ds = lay_zoom_client().lay_nguoi_tham_gia(buoi.zoom_meeting_id)
    except ZoomError:
        return None
    if not ds:
        return None
    tl = buoi.thoi_luong_phut or 1

    def phut(x):
        return round(sum((p.ra_luc - p.vao_luc).total_seconds() / 60 for p in x if p.vao_luc and p.ra_luc))
    gs, hv = phut([p for p in ds if p.la_host]), phut([p for p in ds if not p.la_host])
    return {"gs": gs, "hv": hv, "pt_gs": min(round(gs * 100 / tl), 100), "pt_hv": min(round(hv * 100 / tl), 100)}


VI_SAO = {
    "mo_lai": "Buổi tự hủy vì quá 12 giờ chưa xác nhận. Gia sư cho biết đã dạy nhưng quên xác nhận. Đối chiếu dữ liệu "
              "Zoom trước khi mở lại; hạn mở lại là 7 ngày sau buổi học.",
    "tu_huy": "Buổi tự hủy vì quá 12 giờ chưa xác nhận, gia sư chưa gửi yêu cầu. Có thể chủ động mở lại nếu có xác nhận "
              "từ phụ huynh hoặc Tuyển sinh.",
    "loi_he_thong": "Gia sư gặp lỗi hệ thống khi thao tác. Hạn xác nhận đã được cộng 24 giờ. Nếu bản nháp đủ 3 mục bắt "
                    "buộc, có thể khôi phục và xác nhận thay gia sư.",
    "su_co_zoom": "Phòng Zoom của buổi lỗi hoặc gia sư báo sự cố. Có thể tạo lại phòng bằng tài khoản host khác.",
    "doi_gia_su": "Khóa đã đổi gia sư trước đây nên lần đổi này cần Quản trị viên duyệt. Trong lúc chờ, các buổi vẫn do "
                  "gia sư cũ dạy.",
    "ho_so": "Hồ sơ gia sư chờ duyệt. Kiểm tra minh chứng, bài test rồi duyệt hồ sơ và từng môn.",
    "mon": "Gia sư đang hoạt động đăng ký thêm môn. Kiểm tra minh chứng, bài test rồi duyệt môn.",
}


@vai_tro_required(ADMIN)
def xem_xet(request):
    """QTV › Cần xem xét (SD-32): hàng đợi hợp nhất, tab, tìm theo mã (bh399 = BH-00399)."""
    from django.utils import timezone
    from core.models import BanNhapDanhGia, YeuCauXuLy
    from core.services import xem_xet as dv_xx
    quet_han()
    q = request.GET.get("q", "").strip()
    tab = request.GET.get("tab", "")
    tab = tab if tab in dict(dv_xx.TAB) else ""
    ds, dem, khong_co = dv_xx.hang_doi(q, tab)
    chon = next((x for x in ds if x["key"] == request.GET.get("chon")), ds[0] if ds else None)
    ctx = {"ds": ds, "dem": dem, "ds_tab": [(k, n, dem[k]) for k, n in dv_xx.TAB], "tab": tab, "q": q,
           "khong_co": khong_co, "chon": chon}
    if chon:
        b = chon["buoi"]
        ctx["vi_sao"] = VI_SAO[chon["loai"]]
        if b:
            dau_thang = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ctx["zoom"] = _du_lieu_zoom(b)
            ctx["so_lan_xin"] = YeuCauXuLy.objects.filter(nguoi_gui=b.gia_su, loai=YeuCauXuLy.Loai.MO_LAI,
                                                          tao_luc__gte=dau_thang).count()
            ctx["ban_nhap"] = BanNhapDanhGia.objects.filter(buoi_hoc=b).first()
            ctx["nhap_du"] = dv_xx.ban_nhap_du(b) is not None
        if chon["loai"] == "doi_gia_su":
            ctx["so_lan_doi"] = chon["obj"].khoa_hoc.lich_su_doi_gia_su.filter(
                trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN).count()
    return render(request, "core/ngoai_le/xem_xet.html", ctx)


@vai_tro_required(ADMIN)
@require_POST
def xu_ly_muc(request, loai, pk, hanh_dong):
    """Một nút trên trang Cần xem xét → service tương ứng; quay lại đúng mục với thông báo."""
    from core.models import YeuCauXuLy
    from core.services import xem_xet as dv_xx
    ly_do = request.POST.get("ly_do", "")
    tiep = reverse("xem_xet") + (f"?tab={request.POST.get('tab')}" if request.POST.get("tab") else "")
    try:
        if loai == "tu_huy":
            buoi = get_object_or_404(BuoiHoc, pk=pk)
            if hanh_dong != "mo_lai":
                raise ValidationError("Thao tác không hợp lệ.")
            dv_xx.mo_lai_tu_yeu_cau(request.user, buoi, ly_do)
            msg = f"Đã mở lại {buoi.ma}: gia sư có thêm 24 giờ để xác nhận."
        elif loai == "doi_gia_su":
            dn = get_object_or_404(DoiGiaSu, pk=pk)
            if hanh_dong not in ("duyet", "tu_choi"):
                raise ValidationError("Thao tác không hợp lệ.")
            dv.duyet_doi_gia_su(request.user, dn, hanh_dong == "duyet", ly_do)
            msg = (f"Đã duyệt đổi gia sư {dn.khoa_hoc.ma}." if hanh_dong == "duyet"
                   else f"Đã từ chối đề nghị đổi gia sư {dn.khoa_hoc.ma}.")
        else:
            yc = get_object_or_404(YeuCauXuLy.objects.select_related("buoi_hoc__gia_su", "nguoi_gui"), pk=pk)
            ham = {"mo_lai": lambda: dv_xx.mo_lai_tu_yeu_cau(request.user, yc, ly_do),
                   "tu_choi": lambda: dv_xx.tu_choi_mo_lai(request.user, yc, ly_do),
                   "khoi_phuc": lambda: dv_xx.khoi_phuc_tu_nhap(request.user, yc, ly_do),
                   "ky_thuat": lambda: dv_xx.chuyen_ky_thuat(request.user, yc, ly_do),
                   "zoom": lambda: dv_xx.tao_lai_zoom(request.user, yc)}.get(hanh_dong)
            if not ham:
                raise ValidationError("Thao tác không hợp lệ.")
            ham()
            ma = yc.buoi_hoc.ma if yc.buoi_hoc_id else "sự cố"
            msg = {"mo_lai": f"Đã mở lại {ma}: gia sư có thêm 24 giờ để xác nhận.",
                   "tu_choi": f"Đã từ chối yêu cầu {ma}, đã báo gia sư.",
                   "khoi_phuc": f"Đã khôi phục và xác nhận {ma} từ bản nháp.",
                   "ky_thuat": f"Đã chuyển {ma} cho kỹ thuật.",
                   "zoom": f"Đã tạo lại phòng Zoom cho {ma}, đã báo gia sư."}[hanh_dong]
        messages.success(request, msg)
    except ValidationError as e:
        messages.error(request, _loi(e))
        return redirect(tiep + ("&" if "?" in tiep else "?") + f"chon={loai}-{pk}")
    return redirect(tiep)


@vai_tro_required(ADMIN)
@require_POST
def xu_ly_buoi(request, pk, hanh_dong):
    buoi = get_object_or_404(BuoiHoc.objects.select_related("gia_su", "yeu_cau__mon_hoc"), pk=pk)
    ham = {"hop_le": dv.xac_nhan_hop_le, "huy": dv.huy_sau_xem_xet, "mo_lai": dv.mo_lai}.get(hanh_dong)
    if not ham:
        messages.error(request, "Thao tác không hợp lệ.")
        return redirect("xem_xet")
    try:
        ham(request.user, buoi, request.POST.get("ly_do", ""))
        messages.success(request, {"hop_le": f"Đã công nhận {buoi.ma}.", "huy": f"Đã hủy {buoi.ma} và trả lại buổi cho khóa.",
                                   "mo_lai": f"Đã mở lại {buoi.ma}; gia sư đã được báo qua email."}[hanh_dong])
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("xem_xet")


@vai_tro_required(ADMIN)
@require_POST
def duyet_doi_gia_su(request, pk):
    dn = get_object_or_404(DoiGiaSu, pk=pk)
    dong_y = request.POST.get("dong_y") == "1"
    try:
        dv.duyet_doi_gia_su(request.user, dn, dong_y, request.POST.get("ghi_chu", ""))
        messages.success(request, "Đã duyệt: khóa chuyển sang tìm gia sư mới." if dong_y else "Đã từ chối đề nghị.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("xem_xet")


@vai_tro_required(ADMIN, TUYEN_SINH)
@require_POST
def doi_gia_su(request, pk):
    khoa = get_object_or_404(KhoaHoc.objects.select_related("gia_su", "yeu_cau"), pk=pk)
    from core.models import User
    gs_moi = None
    if request.POST.get("gia_su_moi"):
        gs_moi = User.objects.filter(pk=request.POST["gia_su_moi"], vai_tro=User.VaiTro.GIA_SU, is_active=True).first()
        if not gs_moi:
            messages.error(request, "Gia sư mới không hợp lệ.")
            return redirect(f"{reverse('khoa_hoc_chi_tiet', args=[pk])}?mo=doi-gs")
    try:
        dn = dv.de_nghi_doi_gia_su(request.user, khoa, request.POST.get("ly_do", ""), request.POST.get("ghi_chu", ""),
                                   gia_su_moi=gs_moi, thu_lao_moi=request.POST.get("thu_lao_moi") or None,
                                   da_dong_y=bool(request.POST.get("da_dong_y")))
    except (ValidationError, ValueError) as e:
        messages.error(request, _loi(e) if isinstance(e, ValidationError) else "Thù lao không hợp lệ.")
        return redirect(f"{reverse('khoa_hoc_chi_tiet', args=[pk])}?mo=doi-gs")
    if dn.trang_thai == DoiGiaSu.TrangThai.CHO_DUYET:
        messages.success(request, "Đã gửi đề xuất đổi gia sư, chờ Quản trị viên duyệt. Trong lúc chờ, các buổi vẫn do "
                                  f"{khoa.gia_su.ho_ten} dạy.")
        return redirect("khoa_hoc_chi_tiet", pk=pk)
    if gs_moi:
        dn.refresh_from_db()
        messages.success(request, f"Đã đổi gia sư sang {gs_moi.ho_ten}, chuyển {dn.so_buoi_chuyen} buổi đã xếp. "
                                  "Nhớ báo phụ huynh và đổi nhóm Zalo lớp.")
        return redirect("khoa_hoc_chi_tiet", pk=pk)
    messages.success(request, "Đã đổi gia sư: khóa tạm dừng, chọn gia sư mới và gửi lời mời bên dưới. "
                              "Khi có người nhận, khóa tự học tiếp với số buổi còn lại.")
    return redirect("yeu_cau_chi_tiet", pk=khoa.yeu_cau_id)


@vai_tro_required(ADMIN)
@require_POST
def sua_so_buoi(request, pk):
    khoa = get_object_or_404(KhoaHoc, pk=pk)
    try:
        so = int(request.POST.get("so_buoi", ""))
        dv.sua_so_buoi(request.user, khoa, so, request.POST.get("ly_do", ""))
        messages.success(request, f"Đã cập nhật số buổi đăng ký thành {so}.")
    except ValueError:
        messages.error(request, "Số buổi không hợp lệ.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("khoa_hoc_chi_tiet", pk=pk)


@vai_tro_required(ADMIN)
@require_POST
def gan_thang(request, pk):
    yc = get_object_or_404(YeuCauHocTap.objects.select_related("mon_hoc", "hoc_vien"), pk=pk)
    gs = get_object_or_404(User, pk=request.POST.get("gia_su") or 0, vai_tro=User.VaiTro.GIA_SU)
    try:
        dv.gan_thang(request.user, yc, gs, request.POST.get("ly_do", ""))
        messages.success(request, f"Đã phân công {gs.ho_ten} cho {yc.ma}.")
    except ValidationError as e:
        messages.error(request, _loi(e))
    return redirect("yeu_cau_chi_tiet", pk=pk)
