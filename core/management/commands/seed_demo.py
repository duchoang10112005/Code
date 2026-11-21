"""Tạo dữ liệu demo: `python manage.py seed_demo`

Chạy lại nhiều lần không bị trùng (dùng get_or_create). Phần 3–6 sẽ bổ sung thêm
yêu cầu, khóa học, buổi học mẫu ở đủ các trạng thái.
"""

from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (BuoiHoc, CapDo, HocVien, HoSoGiaSu, KhoaHoc, LichRanh, LoiMoi, MonGiaSu, MonHoc, ThuLao, User,
                         YeuCauHocTap)

MAT_KHAU_DEMO = "Demo@2026"

MON_HOC = [  # (mã, tên)
    ("TOAN", "Toán"), ("ANH", "Tiếng Anh"), ("LY", "Vật lý"),
    ("HOA", "Hóa học"), ("VAN", "Ngữ văn"), ("IELTS", "IELTS"),
]

TAI_KHOAN = [
    # username, họ tên, vai trò, email
    ("admin", "Hoàng Trung Đức", User.VaiTro.ADMIN, "admin@giasu.local"),
    ("tuyensinh", "Trần Đình Phước Hưng", User.VaiTro.TUYEN_SINH, "tuyensinh@giasu.local"),
    ("giasu1", "Nguyễn Minh Anh", User.VaiTro.GIA_SU, "giasu1@giasu.local"),
    ("giasu2", "Lê Hoàng Nam", User.VaiTro.GIA_SU, "giasu2@giasu.local"),
    ("giasu3", "Phạm Thu Trang", User.VaiTro.GIA_SU, "giasu3@giasu.local"),
]

# Gia sư → [(mã môn, cấp độ, trạng thái duyệt)], lịch rảnh [(thứ, từ, đến)], trạng thái hồ sơ
GIA_SU = {
    "giasu1": ([("TOAN", "Lớp 6–12", "DA_DUYET"), ("LY", "Lớp 10–12", "DA_DUYET")],
               [(0, time(18), time(21)), (2, time(18), time(21)), (5, time(8), time(11))], "HOAT_DONG"),
    "giasu2": ([("ANH", "Lớp 1–9", "DA_DUYET"), ("IELTS", "Band 5.0–6.5", "CHO_DUYET")],
               [(1, time(19), time(21)), (3, time(19), time(21))], "HOAT_DONG"),
    "giasu3": ([("TOAN", "Lớp 1–5", "DA_DUYET"), ("VAN", "Lớp 6–9", "DA_DUYET")],
               [(4, time(17), time(20)), (6, time(8), time(12))], "HOAT_DONG"),
}


class Command(BaseCommand):
    help = "Tạo tài khoản và dữ liệu mẫu để demo."

    @transaction.atomic
    def handle(self, *args, **options):
        mon = {}
        for ma, ten in MON_HOC:
            mon[ma], _ = MonHoc.objects.get_or_create(ma=ma, defaults={"ten": ten})
        # Cấp độ mặc định (migration 0019 chỉ nạp cho môn có từ trước; database mới thì môn tạo ở đây)
        from importlib import import_module
        m19 = import_module("core.migrations.0019_cap_do_mac_dinh")
        for ma, m in mon.items():
            if not CapDo.objects.filter(mon_hoc=m).exists():
                for i, ten_cd in enumerate(m19.THEO_MA.get(ma, m19.PHO_THONG)):
                    CapDo.objects.create(mon_hoc=m, ten=ten_cd, thu_tu=i)

        admin_user = None
        for username, ho_ten, vai_tro, email in TAI_KHOAN:
            u, tao_moi = User.objects.get_or_create(
                username=username,
                defaults={"ho_ten": ho_ten, "vai_tro": vai_tro, "email": email,
                          "is_staff": vai_tro == User.VaiTro.ADMIN,
                          "is_superuser": vai_tro == User.VaiTro.ADMIN},
            )
            if tao_moi:
                u.set_password(MAT_KHAU_DEMO)
                u.save()
            if vai_tro == User.VaiTro.ADMIN:
                admin_user = u
            self.stdout.write(f"  {'+' if tao_moi else '='} {username:<10} {u.get_vai_tro_display()}")

        for username, (ds_mon, ds_lich, trang_thai) in GIA_SU.items():
            ho_so, _ = HoSoGiaSu.objects.get_or_create(user=User.objects.get(username=username))
            ho_so.trang_thai = trang_thai
            ho_so.kinh_nghiem = ho_so.kinh_nghiem or "3 năm dạy kèm trực tuyến."
            ho_so.save()
            for ma, cap_do, tt in ds_mon:
                MonGiaSu.objects.get_or_create(
                    ho_so=ho_so, mon_hoc=mon[ma],
                    defaults={"cap_do": cap_do, "trang_thai": tt,
                              "duyet_boi": admin_user if tt == "DA_DUYET" else None,
                              "duyet_luc": timezone.now() if tt == "DA_DUYET" else None},
                )
            if not ho_so.lich_ranh.exists():
                LichRanh.objects.bulk_create(
                    [LichRanh(ho_so=ho_so, thu=t, tu_gio=a, den_gio=b) for t, a, b in ds_lich]
                )

        self._tao_yeu_cau_mau(mon)
        self._tao_khoa_hoc_mau(mon)

        self.stdout.write(self.style.SUCCESS(
            "Xong. Mật khẩu chung của các tài khoản demo xem trong README_DEMO.md."
        ))

    def _tao_yeu_cau_mau(self, mon):
        """Phần 3: học viên + yêu cầu ở đủ trạng thái để demo ngay (không gửi email)."""
        nvts = User.objects.get(username="tuyensinh")
        gs1, gs3 = User.objects.get(username="giasu1"), User.objects.get(username="giasu3")
        now = timezone.now()
        YC, LM = YeuCauHocTap.TrangThai, LoiMoi.TrangThai
        mau = [
            # học viên, lớp, phụ huynh, sđt, môn, trình độ, mục tiêu, thứ, giờ, trạng thái, [(gia sư, trạng thái lời mời)]
            ("Trần Bảo Ngọc", "Lớp 9", "Trần Văn Hùng", "84905111222", "TOAN", "Lớp 9", "Ôn thi vào lớp 10, đạt 8+",
             [0, 2], "Tối 19h–21h", YC.MOI, []),
            ("Nguyễn Khánh Linh", "Lớp 5", "Nguyễn Thị Mai", "84935222333", "TOAN", "Lớp 5", "Củng cố phân số, toán đố",
             [2, 4], "Chiều 17h–19h", YC.DANG_TIM, [(gs1, LM.CHO), (gs3, LM.CHO)]),
            ("Phạm Gia An", "Lớp 8", "Phạm Quốc Bảo", "84914333444", "VAN", "Lớp 8", "Cải thiện kỹ năng viết văn nghị luận",
             [5, 6], "Sáng cuối tuần", YC.DANG_TIM, [(gs3, LM.REJECTED)]),
            ("Đỗ Minh Khôi", "Lớp 11", "Đỗ Thanh Hà", "84983444555", "LY", "Lớp 11", "Lấy lại gốc Điện học",
             [0, 5], "Tối 19h–21h", YC.DA_PHAN_CONG, [(gs1, LM.ACCEPTED)]),
        ]
        for ten, lop, ph, sdt, ma_mon, td, mt, thu, gio, tt, ds_lm in mau:
            hv, tao_moi = HocVien.objects.get_or_create(
                ho_ten=ten, defaults={"lop": lop, "ten_phu_huynh": ph, "sdt_phu_huynh": sdt,
                                      "dong_y_ghi_hinh": True, "tao_boi": nvts})
            if not tao_moi:
                continue
            yc = YeuCauHocTap.objects.create(
                hoc_vien=hv, mon_hoc=mon[ma_mon], trinh_do=td, muc_tieu=mt, thu_mong_muon=thu,
                lich_mong_muon=gio, trang_thai=tt, tao_boi=nvts,
                gia_su=gs1 if tt == YC.DA_PHAN_CONG else None,
                phan_cong_luc=now if tt == YC.DA_PHAN_CONG else None,
            )
            for gs, tt_lm in ds_lm:
                LoiMoi.objects.create(
                    yeu_cau=yc, gia_su=gs, gui_boi=nvts, trang_thai=tt_lm,
                    phan_hoi_luc=None if tt_lm == LM.CHO else now,
                    ly_do_tu_choi="Trùng lịch dạy cuối tuần" if tt_lm == LM.REJECTED else "",
                )
            self.stdout.write(f"  + {yc.ma} {ten} ({yc.get_trang_thai_display()})")

    def _tao_khoa_hoc_mau(self, mon):
        """Phần 4: (1) buổi học thử đã hoàn tất cho yêu cầu Đỗ Minh Khôi → demo nhánh B;
        (2) một học viên đăng ký thẳng (nhánh A) có khóa 10 buổi đã học 8 → demo "sắp hết buổi"."""
        nvts = User.objects.get(username="tuyensinh")
        gs3 = User.objects.get(username="giasu3")
        now = timezone.now()

        yc = YeuCauHocTap.objects.filter(hoc_vien__ho_ten="Đỗ Minh Khôi",
                                         trang_thai=YeuCauHocTap.TrangThai.DA_PHAN_CONG).first()
        if yc and not yc.buoi_hoc.filter(loai=BuoiHoc.Loai.HOC_THU).exists():
            BuoiHoc.objects.create(
                loai=BuoiHoc.Loai.HOC_THU, yeu_cau=yc, gia_su=yc.gia_su, hoc_vien=yc.hoc_vien,
                bat_dau=now - timedelta(days=1, hours=2), thoi_luong_phut=60,
                trang_thai=BuoiHoc.TrangThai.HOAN_TAT, xac_nhan_luc=now - timedelta(days=1),
                zoom_meeting_id="80000000001", zoom_join_url="https://zoom.us/j/80000000001?pwd=gia-lap",
                noi_dung="Kiểm tra đầu vào chương Điện tích – Điện trường.",
                danh_gia="Em nắm công thức nhưng còn yếu bài tập vận dụng; tiếp thu nhanh, nên học 2 buổi/tuần.",
                kiem_tra=BuoiHoc.KiemTra.HOP_LE,
            )
            self.stdout.write(f"  + Buổi học thử hoàn tất cho {yc.ma}")

        hv, tao_moi = HocVien.objects.get_or_create(
            ho_ten="Võ Thanh Tâm", defaults={"lop": "Lớp 4", "ten_phu_huynh": "Võ Thị Lan",
                                             "sdt_phu_huynh": "84935666777", "dong_y_ghi_hinh": True,
                                             "tao_boi": nvts})
        if not tao_moi:
            return
        yc2 = YeuCauHocTap.objects.create(
            hoc_vien=hv, mon_hoc=mon["TOAN"], trinh_do="Lớp 4", muc_tieu="Rèn tính nhanh, chuẩn bị thi học kỳ",
            thu_mong_muon=[4, 6], lich_mong_muon="Chiều thứ 6, sáng CN", trang_thai=YeuCauHocTap.TrangThai.CHINH_THUC,
            gia_su=gs3, phan_cong_luc=now - timedelta(days=40), tao_boi=nvts)
        LoiMoi.objects.create(yeu_cau=yc2, gia_su=gs3, gui_boi=nvts, trang_thai=LoiMoi.TrangThai.ACCEPTED,
                              phan_hoi_luc=now - timedelta(days=40))
        khoa = KhoaHoc.objects.create(
            yeu_cau=yc2, hoc_vien=hv, gia_su=gs3, so_buoi_dang_ky=10, so_buoi_da_dung=8, thoi_luong_phut=90,
            hoc_phi_moi_buoi=150_000, thu_lao_moi_buoi=120_000, tao_boi=nvts)
        # 8 buổi đã xác nhận (mỗi buổi có đúng 1 bản ghi thù lao) để số liệu khớp nhau.
        # Buổi thứ 8 không đạt hậu kiểm Zoom → "Đang xem xét", thù lao tạm giữ (demo màn hình Admin).
        TT, han = BuoiHoc.TrangThai, timedelta(hours=12)
        for i in range(8):
            bat_dau = now - timedelta(days=29 - i * 3, hours=3)
            co_van_de = i == 7
            b = BuoiHoc.objects.create(
                loai=BuoiHoc.Loai.CHINH_THUC, khoa_hoc=khoa, yeu_cau=yc2, gia_su=gs3, hoc_vien=hv,
                bat_dau=bat_dau, thoi_luong_phut=90, so_thu_tu=i + 1, thu_lao_du_kien=khoa.thu_lao_moi_buoi,
                han_xac_nhan=bat_dau + timedelta(minutes=90) + han,
                trang_thai=TT.DANG_XEM_XET if co_van_de else TT.HOAN_TAT,
                xac_nhan_luc=bat_dau + timedelta(hours=2),
                kiem_tra=BuoiHoc.KiemTra.CO_VAN_DE if co_van_de else BuoiHoc.KiemTra.HOP_LE,
                kiem_tra_ghi_chu="Gia sư và học viên cùng có mặt 22/90 phút (cần ≥ 67%)." if co_van_de else "",
                phut_tham_gia_chung=22 if co_van_de else 88,
                zoom_meeting_id=f"8100000000{i}", zoom_join_url=f"https://zoom.us/j/8100000000{i}?pwd=gia-lap",
                noi_dung=f"Buổi {i + 1}: luyện tập phép nhân chia và bài toán có lời văn.",
                xep_loai=BuoiHoc.XepLoai.TOT, danh_gia="Em làm bài cẩn thận hơn, tốc độ tính tăng.",
                zalo_trang_thai=BuoiHoc.GuiZalo.DA_GUI,
            )
            ThuLao.objects.create(buoi_hoc=b, gia_su=gs3, thang=timezone.localdate(bat_dau).replace(day=1),
                                  so_tien=khoa.thu_lao_moi_buoi,
                                  trang_thai=ThuLao.TrangThai.TAM_GIU if co_van_de else ThuLao.TrangThai.TAM_TINH)
        # Một buổi vừa dạy xong 2 giờ trước, chờ gia sư xác nhận; một buổi bị tự hủy vì quá hạn.
        for bat_dau, trang_thai, ly_do in [(now - timedelta(hours=3, minutes=30), TT.DA_LEN_LICH, ""),
                                           (now - timedelta(days=2), TT.DA_HUY, BuoiHoc.LyDoHuy.QUA_HAN)]:
            BuoiHoc.objects.create(
                loai=BuoiHoc.Loai.CHINH_THUC, khoa_hoc=khoa, yeu_cau=yc2, gia_su=gs3, hoc_vien=hv, bat_dau=bat_dau,
                thoi_luong_phut=90, thu_lao_du_kien=khoa.thu_lao_moi_buoi, trang_thai=trang_thai, ly_do_huy=ly_do,
                han_xac_nhan=bat_dau + timedelta(minutes=90) + han, ban_ghi_trang_thai=BuoiHoc.BanGhi.CHO_XU_LY,
                zoom_meeting_id="8200000000" + str(int(trang_thai == TT.DA_HUY)),
                zoom_join_url="https://zoom.us/j/82000000000?pwd=gia-lap")
        self.stdout.write(f"  + {khoa.ma} {hv} (nhánh A, 8/10 buổi, 1 buổi chờ xác nhận, 1 buổi đang xem xét)")
