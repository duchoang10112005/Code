"""Thù lao & đối soát tháng – tiến trình 6.0 trên DFD (PB-16, PB-17, PB-26..28).

- Thù lao từng buổi được tạo tự động khi gia sư xác nhận hoàn tất (services/buoi_hoc.py).
- Tổng tháng = thù lao tạm tính + đã đối soát + các khoản điều chỉnh (âm = trừ). Tạm giữ KHÔNG tính.
- Kiểm soát 2 người: NV tuyển sinh kiểm tra → Admin chốt. Tháng đã chốt thì khóa sổ:
  mọi thay đổi sau đó phải là khoản điều chỉnh ghi vào tháng sau.
"""

from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import DieuChinhThuLao, DoiSoatThang, ThuLao, User
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email
from core.services.tien_ich import dinh_dang_tien

TL = ThuLao.TrangThai
DS = DoiSoatThang.TrangThai


def dau_thang(d=None):
    d = d or timezone.localdate()
    return d.replace(day=1)


def thang_sau(thang):
    return date(thang.year + (thang.month == 12), thang.month % 12 + 1, 1)


def da_chot(gia_su, thang):
    return DoiSoatThang.objects.filter(gia_su=gia_su, thang=dau_thang(thang), trang_thai=DS.DA_CHOT).exists()


def thang_ghi_nhan(gia_su, ngay):
    """Tháng ghi thù lao cho một buổi: tháng của buổi học, hoặc tháng mở gần nhất nếu tháng đó đã chốt."""
    thang = dau_thang(ngay)
    while da_chot(gia_su, thang):
        thang = thang_sau(thang)
    return thang


@dataclass
class DongTong:
    gia_su: User
    so_buoi: int = 0
    tam_tinh: int = 0
    da_doi_soat: int = 0
    tam_giu: int = 0
    so_tam_giu: int = 0
    dieu_chinh: int = 0
    doi_soat: DoiSoatThang | None = None
    ds_dieu_chinh: list = field(default_factory=list)

    @property
    def tong(self):
        return self.tam_tinh + self.da_doi_soat + self.dieu_chinh

    @property
    def trang_thai(self):
        if self.doi_soat and self.doi_soat.trang_thai == DS.DA_CHOT:
            return "DA_CHOT"
        if self.doi_soat:
            return "DA_KIEM_TRA" if self.doi_soat.tong_tien == self.tong else "CAN_KIEM_TRA_LAI"
        return "CHUA_KIEM_TRA"


def tong_hop(thang, gia_su=None):
    """Bảng tổng hợp thù lao tháng theo từng gia sư (có phát sinh trong tháng)."""
    thang = dau_thang(thang)
    tl = ThuLao.objects.filter(thang=thang).exclude(trang_thai=TL.HUY)
    dc = DieuChinhThuLao.objects.filter(thang=thang)
    ds = DoiSoatThang.objects.filter(thang=thang)
    if gia_su:
        tl, dc, ds = tl.filter(gia_su=gia_su), dc.filter(gia_su=gia_su), ds.filter(gia_su=gia_su)
    bang = {}

    def dong(gs_id):
        if gs_id not in bang:
            bang[gs_id] = DongTong(gia_su=User.objects.get(pk=gs_id))
        return bang[gs_id]

    for r in tl.values("gia_su").annotate(
            so=Count("id", filter=~Q(trang_thai=TL.TAM_GIU)),
            tam_tinh=Sum("so_tien", filter=Q(trang_thai=TL.TAM_TINH)),
            da_ds=Sum("so_tien", filter=Q(trang_thai=TL.DA_DOI_SOAT)),
            giu=Sum("so_tien", filter=Q(trang_thai=TL.TAM_GIU)),
            so_giu=Count("id", filter=Q(trang_thai=TL.TAM_GIU))):
        d = dong(r["gia_su"])
        d.so_buoi, d.tam_tinh, d.da_doi_soat = r["so"], r["tam_tinh"] or 0, r["da_ds"] or 0
        d.tam_giu, d.so_tam_giu = r["giu"] or 0, r["so_giu"]
    for x in dc.select_related("tao_boi", "buoi_hoc"):
        d = dong(x.gia_su_id)
        d.dieu_chinh += x.so_tien
        d.ds_dieu_chinh.append(x)
    for x in ds.select_related("kiem_tra_boi", "chot_boi"):
        dong(x.gia_su_id).doi_soat = x
    return sorted(bang.values(), key=lambda d: d.gia_su.ho_ten)


def them_dieu_chinh(nguoi, gia_su, thang, so_tien, ly_do, buoi_hoc=None):
    thang = dau_thang(thang)
    ly_do = (ly_do or "").strip()[:500]
    if not ly_do:
        raise ValidationError("Cần ghi lý do điều chỉnh.")
    if not so_tien:
        raise ValidationError("Số tiền điều chỉnh phải khác 0.")
    if da_chot(gia_su, thang):
        raise ValidationError(f"Tháng {thang:%m/%Y} đã chốt. Hãy ghi điều chỉnh vào tháng {thang_sau(thang):%m/%Y}.")
    with transaction.atomic():
        x = DieuChinhThuLao.objects.create(gia_su=gia_su, thang=thang, so_tien=so_tien, ly_do=ly_do,
                                           buoi_hoc=buoi_hoc, tao_boi=nguoi)
        # Số liệu đã đổi → bản kiểm tra cũ không còn giá trị, NVTS phải kiểm tra lại.
        DoiSoatThang.objects.filter(gia_su=gia_su, thang=thang, trang_thai=DS.DA_KIEM_TRA).delete()
        ghi_nhat_ky(nguoi, "Điều chỉnh thù lao", gia_su.ho_ten, f"{thang:%m/%Y}: {dinh_dang_tien(so_tien)}. {ly_do}")
    return x


def kiem_tra(nvts, gia_su, thang):
    """NV tuyển sinh xác nhận đã đối chiếu số buổi / số tiền của một gia sư trong tháng."""
    thang = dau_thang(thang)
    (d,) = tong_hop(thang, gia_su) or [None]
    if d is None:
        raise ValidationError("Gia sư không có thù lao trong tháng này.")
    if d.trang_thai == "DA_CHOT":
        raise ValidationError("Tháng này đã chốt.")
    if d.so_tam_giu:
        raise ValidationError(f"Còn {d.so_tam_giu} buổi đang tạm giữ (chờ Admin xem xét). Xử lý xong mới kiểm tra được.")
    DoiSoatThang.objects.update_or_create(
        gia_su=gia_su, thang=thang,
        defaults={"tong_tien": d.tong, "trang_thai": DS.DA_KIEM_TRA, "kiem_tra_boi": nvts,
                  "kiem_tra_luc": timezone.now()})
    ghi_nhat_ky(nvts, "Kiểm tra đối soát thù lao", gia_su.ho_ten, f"{thang:%m/%Y}: {dinh_dang_tien(d.tong)}")
    return d


def chot(admin, gia_su, thang):
    """Admin chốt tháng: chỉ khi NVTS đã kiểm tra và số liệu không đổi kể từ lúc kiểm tra."""
    thang = dau_thang(thang)
    (d,) = tong_hop(thang, gia_su) or [None]
    if d is None or d.doi_soat is None:
        raise ValidationError("NV tuyển sinh chưa kiểm tra tháng này.")
    if d.trang_thai == "DA_CHOT":
        raise ValidationError("Tháng này đã chốt rồi.")
    if d.trang_thai == "CAN_KIEM_TRA_LAI":
        raise ValidationError("Số liệu đã thay đổi sau khi NVTS kiểm tra. Cần NVTS kiểm tra lại.")
    if d.doi_soat.kiem_tra_boi_id == admin.pk:
        raise ValidationError("Người kiểm tra không được tự chốt (kiểm soát 2 người).")
    with transaction.atomic():
        n = DoiSoatThang.objects.filter(pk=d.doi_soat.pk, trang_thai=DS.DA_KIEM_TRA).update(
            trang_thai=DS.DA_CHOT, chot_boi=admin, chot_luc=timezone.now())
        if n == 0:
            raise ValidationError("Tháng này vừa được chốt.")
        ThuLao.objects.filter(gia_su=gia_su, thang=thang, trang_thai=TL.TAM_TINH).update(trang_thai=TL.DA_DOI_SOAT)
        ghi_nhat_ky(admin, "Chốt đối soát thù lao", gia_su.ho_ten, f"{thang:%m/%Y}: {dinh_dang_tien(d.tong)}")
    gui_email(gia_su, f"Thù lao tháng {thang:%m/%Y} đã được chốt",
              f"Trung tâm đã chốt thù lao tháng {thang:%m/%Y} của bạn: {d.so_buoi} buổi, "
              f"tổng {dinh_dang_tien(d.tong)}" + (f" (gồm điều chỉnh {dinh_dang_tien(d.dieu_chinh)})" if d.dieu_chinh else "")
              + ".\nXem chi tiết ở mục Thu nhập.")
    return d
