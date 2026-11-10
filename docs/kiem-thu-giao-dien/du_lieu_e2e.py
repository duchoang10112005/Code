"""Tạo dữ liệu demo phong phú cho kiểm thử giao diện (chạy trên BẢN SAO DB, không chạy trên DB thật).

    DB_PATH=<bản sao> python manage.py shell -c "exec(open('docs/kiem-thu-giao-dien/du_lieu_e2e.py', encoding='utf-8').read())"
"""
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from core.models import (BuoiHoc, HocVien, KhoaHoc, LoiMoi, MonHoc, ThuLao, User, YeuCauHocTap)
from core.services.thong_bao import thong_bao
from core.services.thu_lao import dau_thang

now = timezone.now()
gs = User.objects.get(username="giasu1")
ts = User.objects.get(username="tuyensinh")
toan = MonHoc.objects.get(ma="TOAN")
ly = MonHoc.objects.get(ma="LY")


def hv(ten, ph):
    return HocVien.objects.get_or_create(ho_ten=ten, defaults={"ten_phu_huynh": ph, "sdt_phu_huynh": "84905111222",
                                                               "tao_boi": ts, "tuyen_sinh_phu_trach": ts})[0]


def khoa_moi(hoc_vien, mon, trinh_do, so_buoi):
    yc = YeuCauHocTap.objects.create(hoc_vien=hoc_vien, mon_hoc=mon, trinh_do=trinh_do, muc_tieu="Vững kiến thức nền",
                                     lich_mong_muon="T3, T5 19:00–21:00", trang_thai="CHINH_THUC", gia_su=gs,
                                     tao_boi=ts, khung_mong_muon=["1-TOI", "3-TOI"])
    return KhoaHoc.objects.create(yeu_cau=yc, hoc_vien=hoc_vien, gia_su=gs, so_buoi_dang_ky=so_buoi,
                                  hoc_phi_moi_buoi=250_000, thu_lao_moi_buoi=150_000, tao_boi=ts,
                                  tuyen_sinh_phu_trach=ts, lich_co_dinh=[{"thu": 1, "gio": "19:30"}, {"thu": 3, "gio": "19:30"}],
                                  zalo_nhom=f"{mon} {hoc_vien.ho_ten} – GS {gs.ho_ten}")


def buoi(khoa, bat_dau, trang_thai, **kw):
    zoom = {"zoom_meeting_id": "84512093377", "zoom_join_url": "https://zoom.us/j/84512093377",
            "zoom_start_url": "https://zoom.us/s/84512093377", "zoom_passcode": "482913"}
    zoom.update(kw)
    b = BuoiHoc.objects.create(loai="CHINH_THUC", khoa_hoc=khoa, yeu_cau=khoa.yeu_cau, gia_su=gs,
                               hoc_vien=khoa.hoc_vien, bat_dau=bat_dau, thoi_luong_phut=90, trang_thai=trang_thai,
                               thu_lao_du_kien=khoa.thu_lao_moi_buoi,
                               han_xac_nhan=bat_dau + timedelta(minutes=90, hours=12), **zoom)
    return b


k1 = khoa_moi(hv("Trần Gia Bảo", "Trần Văn Hải"), toan, "Lớp 9", 10)
k2 = khoa_moi(hv("Lê Thu Hà", "Lê Văn Tâm"), ly, "Lớp 10", 16)
# Buổi đã dạy trong tháng (có thù lao)
for i in range(1, 6):
    b = buoi(k1 if i % 2 else k2, now - timedelta(days=i * 3, hours=2), "HOAN_TAT", xac_nhan_luc=now - timedelta(days=i * 3),
             noi_dung="Ôn tập", xep_loai="TOT", danh_gia="Em làm bài tốt, nắm chắc kiến thức buổi này", so_thu_tu=i)
    KhoaHoc.objects.filter(pk=b.khoa_hoc_id).update(so_buoi_da_dung=F("so_buoi_da_dung") + 1)
    if timezone.localtime(b.bat_dau).date() >= dau_thang(timezone.localdate()):
        ThuLao.objects.create(buoi_hoc=b, gia_su=gs, so_tien=150_000, thang=dau_thang(timezone.localdate()))
# Buổi chờ xác nhận (kết thúc 9 giờ trước → còn ~3 giờ, "Sắp tự hủy")
buoi(k1, now - timedelta(hours=10, minutes=30), "DA_LEN_LICH")
# Buổi tiếp theo + sắp tới + lỗi Zoom
buoi(k2, now + timedelta(minutes=45), "DA_LEN_LICH")
buoi(k1, now + timedelta(days=2), "DA_LEN_LICH")
buoi(k2, now + timedelta(days=3), "LOI_ZOOM", zoom_loi="Hết quota phòng", zoom_meeting_id="", zoom_join_url="")
# Lời mời đang chờ (1 sắp hết hạn)
yc_moi = YeuCauHocTap.objects.create(hoc_vien=hv("Võ Khánh Linh", "Võ Văn Long"), mon_hoc=toan, trinh_do="Lớp 8",
                                     muc_tieu="Vững kiến thức thi học kỳ I", lich_mong_muon="T3, T5 tối",
                                     trang_thai="DANG_TIM", tao_boi=ts, khung_mong_muon=["1-TOI", "3-TOI", "5-SANG"],
                                     thu_lao_du_kien=150_000, ghi_chu="Học viên hơi nhút nhát, cần động viên.")
LoiMoi.objects.create(yeu_cau=yc_moi, gia_su=gs, gui_boi=ts, het_han_luc=now + timedelta(hours=2, minutes=40),
                      diem_khop=94, chi_tiet_khop={"dung_mon": True, "dung_cap_do": True, "trung_gio": "2/3",
                                                   "dang_nhan_lop": True})
yc_moi2 = YeuCauHocTap.objects.create(hoc_vien=hv("Nguyễn Minh Anh", "Nguyễn Văn Bình"), mon_hoc=ly, trinh_do="Lớp 11",
                                      muc_tieu="Chuẩn bị thi học sinh giỏi", lich_mong_muon="T7 sáng",
                                      trang_thai="DANG_TIM", tao_boi=ts, khung_mong_muon=["5-SANG"])
LoiMoi.objects.create(yeu_cau=yc_moi2, gia_su=gs, gui_boi=ts, het_han_luc=now + timedelta(hours=18), diem_khop=78)
thong_bao(gs, "Lời mời mới: Toán Lớp 8", "Võ Khánh Linh · hết hạn sau 24 giờ", "/loi-moi/", "LOI_MOI")
print("Đã tạo dữ liệu e2e cho giasu1")
