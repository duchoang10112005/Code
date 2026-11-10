"""API chung: chuông thông báo, tìm nhanh Ctrl+K."""

from django.utils import timezone

from core.api import api, doc_du_lieu, tra_ve
from core.services import thong_bao as tb
from core.services.tim_kiem import tim


@api()
def thong_bao(request):
    ds = request.user.thong_bao.all()[:20]
    return tra_ve(data={
        "chua_doc": request.user.thong_bao.filter(da_doc=False).count(),
        "thong_bao": [{"id": t.pk, "tieu_de": t.tieu_de, "noi_dung": t.noi_dung, "url": t.url, "da_doc": t.da_doc,
                       "luc": f"{timezone.localtime(t.tao_luc):%H:%M %d/%m}"} for t in ds],
    })


@api(phuong_thuc=("POST",))
def thong_bao_da_doc(request):
    ids = doc_du_lieu(request).get("ids") or None
    n = tb.danh_dau_da_doc(request.user, ids)
    return tra_ve(message=f"Đã đánh dấu {n} thông báo là đã đọc.", data={"so": n})


@api()
def tim_kiem(request):
    return tra_ve(data={"nhom": tim(request.user, request.GET.get("q", ""))})
