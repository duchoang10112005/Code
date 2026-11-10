# Dữ liệu mẫu cho màn Hậu kiểm (chạy trên DB e2e/demo, KHÔNG chạy trên DB thật):
#   manage.py shell -c "exec(open('docs/kiem-thu-giao-dien/du_lieu_hau_kiem.py', encoding='utf-8').read())"
# Gắn người mời = tài khoản "tuyensinh" cho mọi gia sư, rồi chấm 5 tiêu chí với số liệu Zoom giả lập đa dạng.
from datetime import timedelta

from core.integrations.zoom import NguoiThamGia
from core.models import BuoiHoc, HauKiemBuoi, HoSoGiaSu, User
from core.services import hau_kiem as dv_hk

ts = User.objects.get(username="tuyensinh")
HoSoGiaSu.objects.update(nguoi_moi=ts)
kich_ban = [(0, 100, 100), (2, 98, 95), (12, 90, 92), (0, 54, 98), (31, 60, 40), (0, 100, 88)]
for i, b in enumerate(BuoiHoc.objects.filter(trang_thai=BuoiHoc.TrangThai.HOAN_TAT).order_by("bat_dau")):
    hk, _ = HauKiemBuoi.objects.get_or_create(buoi_hoc=b)
    hk.nguoi_phu_trach = ts
    hk.ket_luan = HauKiemBuoi.KetLuan.CHUA_KIEM_TRA
    hk.save()
    tre, gs, hv = kich_ban[i % len(kich_ban)]
    tl = b.thoi_luong_phut
    t0 = b.bat_dau
    nguoi = [NguoiThamGia("GS", "", t0 + timedelta(minutes=tre), t0 + timedelta(minutes=tre + tl * gs / 100), la_host=True),
             NguoiThamGia("HV", "", t0, t0 + timedelta(minutes=tl * hv / 100))]
    dv_hk.cham(hk, nguoi)
    print(b.ma, hk.so_canh_bao)
