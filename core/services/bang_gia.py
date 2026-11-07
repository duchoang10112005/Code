"""Bảng giá và tính học phí / thù lao tự động (thay cho việc NV tuyển sinh tự nhập số tiền).

Giá gắn với CẤP ĐỘ HỌC (không gắn với tên môn): mỗi môn thuộc một loại môn (Phổ thông, IELTS…),
mỗi loại môn có các cấp độ (Cơ bản / Nâng cao; Nền tảng / Chuyên sâu…) với đơn giá giờ và % trung tâm riêng.

Công thức:
    giá gốc / buổi   = đơn giá giờ của cấp độ × thời lượng (1h | 1,5h | 2h)
    học phí / buổi   = giá gốc × (1 − % giảm của gói)            → làm tròn tới 1.000đ
    thù lao / buổi   = giá gốc × (1 − % trung tâm giữ lại)       → làm tròn tới 100đ
    tổng học phí     = học phí / buổi × số buổi của gói (10 | 20 | 30)

Thù lao luôn tính trên GIÁ GỐC: phần giảm giá do trung tâm chịu, gia sư không bị thiệt.
Vì vậy % khuyến mãi của gói không được vượt % trung tâm giữ lại của bất kỳ cấp độ nào
(nếu không, trung tâm sẽ trả gia sư nhiều hơn số tiền thu của phụ huynh).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db.models import Min, Q
from django.utils import timezone

from core.models import CapDo, GoiKhoaHoc, KhoaHoc

THOI_LUONG_HOP_LE = [c.value for c in KhoaHoc.ThoiLuong]


def lam_tron(so, buoc):
    return int((Decimal(so) / buoc).quantize(Decimal(1), rounding=ROUND_HALF_UP) * buoc)


def goi_dang_ap_dung(ngay=None):
    """{so_buoi: GoiKhoaHoc} đang hiệu lực vào `ngay` (mức có ngày bắt đầu gần nhất thắng)."""
    ngay = ngay or timezone.localdate()
    ket_qua = {}
    qs = (GoiKhoaHoc.objects.filter(hieu_luc_tu__lte=ngay)
          .filter(Q(hieu_luc_den__isnull=True) | Q(hieu_luc_den__gte=ngay))
          .order_by("so_buoi", "-hieu_luc_tu"))
    for goi in qs:
        ket_qua.setdefault(goi.so_buoi, goi)
    return ket_qua


def gioi_han_giam():
    """% giảm tối đa cho phép = % trung tâm giữ lại nhỏ nhất trong các cấp độ."""
    return CapDo.objects.aggregate(m=Min("ty_le_trung_tam"))["m"]


@dataclass
class BaoGia:
    cap_do: CapDo
    so_buoi: int
    thoi_luong_phut: int
    don_gia_gio: int
    ty_le_giam: Decimal
    ty_le_trung_tam: Decimal
    hoc_phi_goc: int
    hoc_phi: int
    thu_lao: int
    quyen_loi: str = ""

    @property
    def tong_hoc_phi(self):
        return self.hoc_phi * self.so_buoi

    @property
    def tiet_kiem(self):
        return (self.hoc_phi_goc - self.hoc_phi) * self.so_buoi

    @property
    def trung_tam_moi_buoi(self):
        return self.hoc_phi - self.thu_lao


def gia_mot_buoi(cap_do, thoi_luong_phut):
    """(giá gốc, thù lao) của một buổi theo cấp độ và khung giờ."""
    goc = Decimal(cap_do.don_gia_gio) * thoi_luong_phut / 60
    return int(goc), lam_tron(goc * (100 - cap_do.ty_le_trung_tam) / 100, 100)


def tinh_gia(mon_hoc, cap_do, so_buoi, thoi_luong_phut, ngay=None):
    if cap_do is None:
        raise ValidationError("Chưa chọn cấp độ học.")
    if mon_hoc.loai_mon_id != cap_do.loai_mon_id:
        raise ValidationError(f"Cấp độ \"{cap_do.ten}\" không thuộc loại môn của {mon_hoc}.")
    if thoi_luong_phut not in THOI_LUONG_HOP_LE:
        raise ValidationError("Thời lượng buổi chỉ được chọn 1 giờ, 1,5 giờ hoặc 2 giờ.")
    goi = goi_dang_ap_dung(ngay).get(so_buoi)
    if not goi:
        raise ValidationError(f"Gói {so_buoi} buổi hiện không được áp dụng.")
    goc, thu_lao = gia_mot_buoi(cap_do, thoi_luong_phut)
    hoc_phi = lam_tron(Decimal(goc) * (100 - goi.ty_le_giam) / 100, 1000)
    if thu_lao > hoc_phi:
        raise ValidationError("Bảng giá đang sai: thù lao gia sư lớn hơn học phí sau khuyến mãi. Admin cần giảm % khuyến mãi.")
    return BaoGia(cap_do, so_buoi, thoi_luong_phut, cap_do.don_gia_gio, goi.ty_le_giam, cap_do.ty_le_trung_tam,
                  goc, hoc_phi, thu_lao, goi.quyen_loi)


def bang_bao_gia(loai_mon, ngay=None):
    """Dữ liệu cho JS form tạo khóa: mọi tổ hợp cấp độ (của loại môn) × gói × khung giờ."""
    goi = goi_dang_ap_dung(ngay)
    ds = []
    for cap_do in CapDo.objects.filter(loai_mon=loai_mon):
        for so_buoi, g in sorted(goi.items()):
            for phut in THOI_LUONG_HOP_LE:
                goc, thu_lao = gia_mot_buoi(cap_do, phut)
                ds.append({
                    "cap_do": cap_do.pk, "so_buoi": so_buoi, "phut": phut, "hoc_phi_goc": goc,
                    "hoc_phi": lam_tron(Decimal(goc) * (100 - g.ty_le_giam) / 100, 1000),
                    "thu_lao": thu_lao, "giam": float(g.ty_le_giam), "quyen_loi": g.ds_quyen_loi,
                })
    return ds
