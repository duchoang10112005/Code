"""API Tuyển sinh: tìm học viên đã có, đếm gia sư phù hợp khi tạo yêu cầu (SD-05)."""

from django.shortcuts import get_object_or_404

from core.api import api, tra_ve
from core.models import HocVien, MonHoc, YeuCauHocTap
from core.services import yeu_cau as dv
from core.services.tim_kiem import chuan_hoa

TS = ("TUYEN_SINH", "ADMIN")


@api(vai_tro=TS)
def tim_hoc_vien(request):
    q = chuan_hoa(request.GET.get("q", ""))
    if len(q) < 2:
        return tra_ve(data={"ds": []})
    ds = []
    for h in HocVien.objects.order_by("-pk")[:2000]:
        if q in chuan_hoa(h.ho_ten) or q in chuan_hoa(h.ten_phu_huynh) or q in h.sdt_phu_huynh \
                or q.lstrip("0") in h.sdt_phu_huynh:
            mo = YeuCauHocTap.objects.filter(hoc_vien=h, trang_thai__in=["MOI", "DANG_TIM", "DA_PHAN_CONG"]) \
                .select_related("mon_hoc").first()
            ds.append({"pk": h.pk, "ho_ten": h.ho_ten, "lop": h.lop, "phu_huynh": h.ten_phu_huynh,
                       "yeu_cau_mo": f"{mo.ma} môn {mo.mon_hoc} đang {mo.get_trang_thai_display().lower()}" if mo else ""})
            if len(ds) >= 8:
                break
    return tra_ve(data={"ds": ds})


@api(vai_tro=TS)
def dem_gia_su(request):
    mon = get_object_or_404(MonHoc, pk=request.GET.get("mon") or 0)
    cap = request.GET.get("cap_do")
    khung = [k for k in request.GET.getlist("khung") if k]
    tong, khop = dv.dem_gia_su_phu_hop(mon, int(cap) if cap and cap.isdigit() else None, khung)
    return tra_ve(data={"tong": tong, "khop": khop})
