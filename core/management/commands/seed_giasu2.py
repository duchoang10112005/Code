"""Bổ sung dữ liệu mẫu cho gia sư giasu2 (Lê Hoàng Nam) để trang chủ/lớp/thù lao trông đầy đủ:  python manage.py seed_giasu2

Thêm 4 học viên với 3 khóa chính thức (đang học ×2, hoàn thành ×1), 1 yêu cầu học thử xong chờ chốt, 1 lời mời đang chờ,
cùng lịch sử buổi học đã hoàn tất, thù lao các tháng, đối soát tháng trước, hậu kiểm.

AN TOÀN CHO ZOOM: chỉ tạo buổi ĐÃ DIỄN RA (hoàn tất) nên không chiếm phòng Zoom duy nhất; không có buổi "đã lên lịch" nào ở tương
lai, không gọi Zoom / Zalo / email thật. Email phụ huynh = EMAIL_DEMO (mặc định hộp thư của người demo). Chạy lại vẫn an toàn.
"""

import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.management.commands.seed_mo_rong import Command as SeedMoRong, KL, LM, TT, YC, _dau_thang
from core.models import (BuoiHoc, DoiSoatThang, HocVien, KhoaHoc, MonHoc, ThuLao, User)

EMAIL_DEMO = "hoangtrungduc10112005@gmail.com"

# họ tên, lớp, giới tính, trường, phụ huynh, SĐT, môn, mục tiêu
HOC_VIEN = [
    ("Nguyễn Hà My", "Lớp 8", "NU", "THCS Nguyễn Huệ", "Nguyễn Văn Phát", "84905777101", "TOAN", "Củng cố đại số, lên lớp 9 vững kiến thức"),
    ("Trần Bảo Ngọc", "Lớp 10", "NU", "THPT Phan Châu Trinh", "Trần Thị Mai", "84935777102", "ANH", "Nâng điểm tiếng Anh, giao tiếp tự tin"),
    ("Lê Quang Huy", "Lớp 12", "NAM", "THPT Hoàng Hoa Thám", "Lê Văn Cường", "84914777103", "IELTS", "Đạt IELTS 6.5 để xét tuyển"),
    ("Phạm Khánh An", "Lớp 6", "NAM", "THCS Lê Lợi", "Phạm Thị Hạnh", "84983777104", "TOAN", "Làm quen chương trình Toán lớp 6"),
    ("Đỗ Minh Khôi", "Lớp 7", "NAM", "THCS Trần Phú", "Đỗ Văn Tùng", "84906777105", "TOAN", "Lấy lại gốc môn Toán"),
]


class Command(SeedMoRong):
    help = "Bổ sung dữ liệu mẫu cho gia sư giasu2 (chỉ buổi đã diễn ra, không chiếm phòng Zoom)."

    def handle(self, *args, **opts):
        if HocVien.objects.filter(ho_ten=HOC_VIEN[0][0]).exists():
            self.stdout.write("Dữ liệu giasu2 đã có – bỏ qua.")
            return
        self.r = random.Random(77)
        self.now = timezone.now()
        self.hom_nay = timezone.localdate()
        self.zoom_id = 91_000_000_000
        self.admin = User.objects.get(username="admin")
        self.mon = {m.ma: m for m in MonHoc.objects.all()}
        nam = User.objects.get(username="giasu2")
        self.ts = [nam.ho_so_gia_su.nguoi_moi or User.objects.get(username="tuyensinh")]  # NV đã mời Nam
        with transaction.atomic():
            self._tao(nam)
        self.stdout.write(self.style.SUCCESS(f"Xong. giasu2 hiện có {KhoaHoc.objects.filter(gia_su=nam).count()} khóa, "
                                             f"{BuoiHoc.objects.filter(gia_su=nam).count()} buổi."))

    def _tao(self, nam):
        ts = self.ts[0]
        hv = []
        for i, (ten, lop, gt, truong, ph, sdt, mon, mt) in enumerate(HOC_VIEN):
            hv.append(HocVien.objects.create(
                ho_ten=ten, lop=lop, gioi_tinh=gt, truong=truong, ten_phu_huynh=ph, sdt_phu_huynh=sdt,
                email_phu_huynh=EMAIL_DEMO, dong_y_ghi_hinh=True, tao_boi=ts, tuyen_sinh_phu_trach=ts))

        # --- 3 khóa chính thức: (học viên, số buổi đk, đã dạy, phút, học phí, lịch, trạng thái, tự học thử?)
        spec = [(0, 16, 10, 60, 250000, [(1, 19), (3, 19)], KhoaHoc.TrangThai.DANG_HOC, True),
                (1, 12, 6, 90, 220000, [(2, 19)], KhoaHoc.TrangThai.DANG_HOC, False),
                (2, 10, 10, 90, 300000, [(5, 9)], KhoaHoc.TrangThai.HOAN_THANH, True)]
        for i, so_dk, da_dung, phut, hoc_phi, lich, tt_khoa, hoc_thu in spec:
            h, ten_mon = hv[i], HOC_VIEN[i][6]
            y = self._yeu_cau(h, ten_mon, YC.CHINH_THUC, nam, muc_tieu=HOC_VIEN[i][7], dang_ky_thang=not hoc_thu,
                              ket_qua_hoc_thu="DONG_Y" if hoc_thu else "")
            self._loi_moi(y, nam, LM.ACCEPTED)
            if hoc_thu:
                b0 = self._buoi(None, y, nam, h, self._gio_dia_phuong(self.hom_nay - timedelta(days=da_dung * 7 + 12), 19), 60,
                                TT.HOAN_TAT, BuoiHoc.Loai.HOC_THU)
                self._hau_kiem(b0, KL.HOP_LE)
            khoa, ngay, gio = self._lop_hoc(y, nam, h, so_dk, da_dung, phut, hoc_phi, lich, tt_khoa)
            for k, d in enumerate(ngay):
                b = self._buoi(khoa, y, nam, h, self._gio_dia_phuong(d, gio), phut, TT.HOAN_TAT, so_thu_tu=k + 1,
                               thu_lao=khoa.thu_lao_moi_buoi)
                ThuLao.objects.create(buoi_hoc=b, gia_su=nam, thang=_dau_thang(d), so_tien=khoa.thu_lao_moi_buoi,
                                      trang_thai=ThuLao.TrangThai.TAM_TINH if _dau_thang(d) == _dau_thang(self.hom_nay)
                                      else ThuLao.TrangThai.DA_DOI_SOAT)
                gan = (self.hom_nay - d).days <= 8
                self._hau_kiem(b, KL.CHUA_KIEM_TRA if gan and k >= len(ngay) - 1 and i == 0 else KL.HOP_LE)

        # --- học thử xong, chờ phụ huynh chốt (NV tuyển sinh sẽ "Mở khóa học")
        y = self._yeu_cau(hv[3], HOC_VIEN[3][6], YC.HOC_THU_XONG, nam, muc_tieu=HOC_VIEN[3][7],
                          ket_qua_hoc_thu="CAN_THEM_THOI_GIAN", ghi_chu_hoc_thu="Phụ huynh cần bàn với gia đình, hẹn gọi lại.")
        self._loi_moi(y, nam, LM.ACCEPTED)
        b = self._buoi(None, y, nam, hv[3], self._gio_dia_phuong(self.hom_nay - timedelta(days=2), 19), 60,
                       TT.HOAN_TAT, BuoiHoc.Loai.HOC_THU)
        self._hau_kiem(b, KL.HOP_LE)

        # --- 1 lời mời đang chờ nhận lớp
        y = self._yeu_cau(hv[4], HOC_VIEN[4][6], YC.DANG_TIM, muc_tieu=HOC_VIEN[4][7])
        self._loi_moi(y, nam, LM.CHO, 91)

        # --- đối soát các tháng đã qua (đã chi trả)
        thang_nay = _dau_thang(self.hom_nay)
        for thang in sorted(set(ThuLao.objects.filter(gia_su=nam, thang__lt=thang_nay).values_list("thang", flat=True))):
            tong = sum(t.so_tien for t in ThuLao.objects.filter(gia_su=nam, thang=thang))
            chot = timezone.make_aware(datetime.combine(_dau_thang(thang + timedelta(days=32)), time(9)) + timedelta(days=14))
            if DoiSoatThang.objects.filter(gia_su=nam, thang=thang).exists():
                continue
            DoiSoatThang.objects.create(
                gia_su=nam, thang=thang, tong_tien=tong, trang_thai=DoiSoatThang.TrangThai.DA_CHI_TRA,
                kiem_tra_boi=ts, kiem_tra_luc=chot - timedelta(days=3), chot_boi=self.admin, chot_luc=chot,
                chi_tra_boi=self.admin, chi_tra_luc=chot + timedelta(days=2), chung_tu=f"UNC-{thang:%Y-%m}-{nam.pk:03d}")
