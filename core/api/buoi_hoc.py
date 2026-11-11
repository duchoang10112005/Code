"""API buổi học của gia sư (SD-13, SD-15, SD-16)."""

from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.api import api, doc_du_lieu, tra_ve
from core.forms import TaoBuoiForm
from core.models import BuoiHoc
from core.services import buoi_hoc as dv

GS = ("GIA_SU",)


@api(vai_tro=GS, phuong_thuc=("POST",))
def kiem_tra_lich(request):
    """Kiểm tra trước khi tạo: mỗi buổi OK / chặn (lý do) / cảnh báo + nhãn "Buổi 6/16". Không ghi gì."""
    from core.views.buoi_hoc import lay_buoi_bu, lay_lop
    form = TaoBuoiForm(doc_du_lieu(request))
    if not form.is_valid():
        return tra_ve(False, "Chọn lớp, ngày và giờ bắt đầu.", errors={k: [str(m) for m in v] for k, v in form.errors.items()})
    lop = lay_lop(request.user, form.cleaned_data["lop"])
    ke = dv.kiem_tra_ke_hoach(request.user, lop, form.ke_hoach(),
                              lay_buoi_bu(request.user, lop, form.cleaned_data["hoc_bu_cho"]),
                              form.cleaned_data.get("thoi_luong"))
    dong = [{"bat_dau": f"{timezone.localtime(x['bat_dau']):%H:%M}", "ngay": f"{timezone.localtime(x['bat_dau']):%d/%m/%Y}",
             "thu": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][timezone.localtime(x["bat_dau"]).weekday()],
             "ket_thuc": f"{timezone.localtime(x['ket_thuc']):%H:%M}", "ngay_iso": f"{timezone.localtime(x['bat_dau']):%Y-%m-%d}",
             "muc": x["muc"], "ly_do": x["ly_do"], "nhan": x["nhan"]} for x in ke]
    so_ok = sum(1 for x in ke if x["muc"] != "chan")
    so_chan = len(ke) - so_ok
    if so_chan:
        msg = f"{so_chan} buổi chưa tạo được. Đổi ngày hoặc giờ để tiếp tục." if not so_ok else \
              f"Sẵn sàng tạo {so_ok} buổi · {so_chan} buổi bị chặn sẽ bỏ qua."
    else:
        msg = f"Sẵn sàng tạo {so_ok} buổi."
    return tra_ve(True, msg, data={"dong": dong, "so_ok": so_ok, "so_chan": so_chan})


@api(vai_tro=GS)
def tin_nhan_lop(request, pk):
    b = get_object_or_404(BuoiHoc.objects.select_related("khoa_hoc", "yeu_cau__mon_hoc", "hoc_vien", "gia_su"),
                          pk=pk, gia_su=request.user)
    return tra_ve(data={"tin_nhan": dv.noi_dung_moi_vao_lop(b, request), "link_lop": dv.link_lop(b, request)})


@api(vai_tro=GS, phuong_thuc=("POST",))
def luu_nhap(request, pk):
    b = get_object_or_404(BuoiHoc, pk=pk, gia_su=request.user)
    nhap = dv.luu_nhap(request.user, b, doc_du_lieu(request))
    return tra_ve(message=f"Đã lưu nháp {timezone.localtime(nhap.luu_luc):%H:%M}",
                  data={"luu_luc": f"{timezone.localtime(nhap.luu_luc):%H:%M}"})


@api(vai_tro=GS, phuong_thuc=("POST",))
def gui_lai_zalo(request, pk):
    b = get_object_or_404(BuoiHoc.objects.select_related("hoc_vien", "yeu_cau__mon_hoc", "gia_su"),
                          pk=pk, gia_su=request.user)
    if b.trang_thai not in (BuoiHoc.TrangThai.HOAN_TAT, BuoiHoc.TrangThai.DANG_XEM_XET):
        return tra_ve(False, "Chỉ gửi nhận xét cho buổi đã xác nhận hoàn tất.")
    ok_z = b.zalo_trang_thai == BuoiHoc.GuiZalo.DA_GUI or dv.gui_zalo_danh_gia(b)
    ok_e = b.email_trang_thai == BuoiHoc.GuiZalo.DA_GUI or dv.gui_email_danh_gia(b)
    kenh = [k for k, ok in (("Zalo", ok_z), ("email", ok_e)) if ok]
    return tra_ve(bool(kenh), ("Đã gửi nhận xét cho phụ huynh qua " + " và ".join(kenh) + ".") if kenh else
                  "Chưa gửi được. Hãy sao chép nhận xét và gửi tay cho phụ huynh.",
                  data={"zalo": b.get_zalo_trang_thai_display(), "email": b.get_email_trang_thai_display()})
