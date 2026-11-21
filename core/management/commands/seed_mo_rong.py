"""Nạp dữ liệu demo PHONG PHÚ:  python manage.py seed_mo_rong

Thêm vào dữ liệu của seed_demo (chạy lại seed_demo trước, không tạo trùng): thêm Tuyển sinh, gia sư ở đủ trạng thái,
24 học viên / yêu cầu ở mọi bước của luồng, 9 khóa học (đang học, sắp hết buổi, tạm dừng, hoàn thành, hủy), buổi học
nhiều tháng, thù lao + đối soát đã chi trả, hậu kiểm, đổi gia sư, hàng đợi Cần xem xét, nhắc việc, thông báo, nhật ký.

An toàn khi chạy lại: nếu đã có tài khoản giasu4 thì bỏ qua. KHÔNG gọi Zoom / Zalo / email thật; link Zoom của buổi mẫu là
link giả lập. Email phụ huynh để trống để khỏi gửi thư vào địa chỉ không tồn tại.
"""

import random
from datetime import date, datetime, time, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (BuoiHoc, CapDo, DieuChinhThuLao, DoiGiaSu, DoiSoatThang, HauKiemBuoi, HoSoGiaSu, HocVien,
                         KhoaHoc, LichRanh, LoiMoi, MaMoiGiaSu, MonGiaSu, MonHoc, NhacViec, NhatKy, SuCoHeThong,
                         ThongBao, ThuLao, User, YeuCauHocTap, YeuCauXuLy)
from core.management.commands.seed_demo import MAT_KHAU_DEMO
from core.services import hau_kiem as dv_hk

YC, LM, TT, KL = YeuCauHocTap.TrangThai, LoiMoi.TrangThai, BuoiHoc.TrangThai, HauKiemBuoi.KetLuan
KHUNG_GIO = {"SANG": (time(8), time(11)), "CHIEU": (time(14), time(17)), "TOI_SOM": (time(17, 30), time(19)),
             "TOI": (time(19), time(21))}

TUYEN_SINH_MOI = [("tuyensinh2", "Lý Hồng Nhung", "nhung.lh@giasu.local"),
                  ("tuyensinh3", "Ngô Quang Vinh", "vinh.nq@giasu.local")]

# username, họ tên, người mời (0=tuyensinh, 1=tuyensinh2, 2=tuyensinh3), trạng thái hồ sơ, học vấn,
# [(mã môn, trạng thái môn)], [(thứ, khung)], tạm nghỉ thêm N ngày
GIA_SU_MOI = [
    ("giasu4", "Trần Quốc Bảo", 0, "HOAT_DONG", "SV năm 4 ĐH Bách khoa Đà Nẵng", [("TOAN", "DA_DUYET"), ("LY", "DA_DUYET")],
     [(0, "TOI"), (2, "TOI"), (4, "TOI_SOM"), (5, "SANG"), (6, "CHIEU")], 0),
    ("giasu5", "Lê Thị Hồng Ánh", 0, "HOAT_DONG", "Cử nhân Ngôn ngữ Anh · IELTS 8.0",
     [("ANH", "DA_DUYET"), ("IELTS", "DA_DUYET")], [(1, "TOI"), (3, "TOI"), (5, "CHIEU"), (6, "SANG")], 0),
    ("giasu6", "Võ Minh Quân", 0, "HOAT_DONG", "Cử nhân Sư phạm Hóa · ĐHSP Đà Nẵng",
     [("HOA", "DA_DUYET"), ("TOAN", "DA_DUYET")], [(0, "TOI_SOM"), (2, "TOI_SOM"), (4, "TOI"), (6, "SANG")], 0),
    ("giasu7", "Đặng Thu Phương", 1, "HOAT_DONG", "Giáo viên Ngữ văn THCS (nghỉ thai sản bán thời gian)",
     [("VAN", "DA_DUYET"), ("ANH", "DA_DUYET")], [(1, "CHIEU"), (3, "CHIEU"), (5, "SANG")], 6),
    ("giasu8", "Bùi Khánh Duy", 1, "HOAT_DONG", "Thạc sĩ Vật lý · ĐH Sư phạm Huế",
     [("LY", "DA_DUYET"), ("TOAN", "DA_DUYET"), ("HOA", "CHO_DUYET")],
     [(0, "TOI"), (1, "TOI"), (3, "TOI"), (5, "CHIEU")], 0),
    ("giasu9", "Hồ Ngọc Mai", 1, "HOAT_DONG", "IELTS 7.5 · 3 năm dạy IELTS", [("IELTS", "DA_DUYET"), ("ANH", "DA_DUYET")],
     [(2, "TOI"), (4, "TOI"), (5, "TOI_SOM"), (6, "CHIEU")], 0),
    ("giasu10", "Phan Gia Huy", 1, "CHO_DUYET", "SV năm 3 ĐH Kinh tế Đà Nẵng", [("TOAN", "CHO_DUYET")],
     [(1, "TOI"), (3, "TOI")], 0),
    ("giasu11", "Nguyễn Thị Lan Anh", 2, "CHO_DUYET", "Cử nhân Hóa học · ĐH Khoa học Huế", [("HOA", "CHO_DUYET")],
     [(0, "TOI"), (4, "TOI")], 0),
    ("giasu12", "Trương Văn Khoa", 2, "TAM_NGUNG", "Gia sư Toán lâu năm (tạm ngừng theo yêu cầu)",
     [("TOAN", "DA_DUYET")], [(2, "TOI_SOM"), (6, "SANG")], 0),
]

# học viên, lớp, giới tính, trường, phụ huynh, SĐT, môn, mục tiêu
HOC_VIEN = [
    ("Nguyễn Hoàng Long", "Lớp 9", "NAM", "THCS Nguyễn Huệ", "Nguyễn Văn Tài", "84905123401", "TOAN", "Ôn thi vào 10, đạt 8.5+"),
    ("Trần Ngọc Hân", "Lớp 7", "NU", "THCS Lê Lợi", "Trần Thị Bích", "84935123402", "ANH", "Giao tiếp tự tin, nâng điểm kiểm tra"),
    ("Lê Minh Triết", "Lớp 11", "NAM", "THPT Phan Châu Trinh", "Lê Văn Hải", "84914123403", "LY", "Lấy lại gốc Cơ học, thi học kỳ"),
    ("Phạm Thùy Dương", "Lớp 12", "NU", "THPT Hoàng Hoa Thám", "Phạm Quốc Việt", "84983123404", "HOA", "Luyện thi THPT, mục tiêu 8+"),
    ("Võ Anh Khoa", "Lớp 8", "NAM", "THCS Trần Phú", "Võ Thị Thu", "84906123405", "TOAN", "Củng cố đại số, lên lớp 9"),
    ("Đặng Mai Anh", "Lớp 10", "NU", "THPT Thái Phiên", "Đặng Văn Long", "84937123406", "VAN", "Cải thiện viết nghị luận"),
    ("Bùi Gia Bảo", "Lớp 6", "NAM", "THCS Nguyễn Văn Linh", "Bùi Thị Hoa", "84915123407", "ANH", "Nền tảng từ vựng, ngữ pháp"),
    ("Hồ Khánh Vy", "Lớp 11", "NU", "THPT Hòa Vang", "Hồ Văn Sơn", "84984123408", "IELTS", "IELTS 6.5 trước tháng 6/2027"),
    ("Phan Quốc Đạt", "Lớp 9", "NAM", "THCS Nguyễn Khuyến", "Phan Thị Lệ", "84907123409", "LY", "Ôn thi vào 10 chuyên Lý"),
    ("Nguyễn Thảo Nhi", "Lớp 5", "NU", "TH Lê Văn Tám", "Nguyễn Thị Hương", "84938123410", "TOAN", "Rèn tính nhanh, toán đố"),
    ("Trần Đức Anh", "Lớp 12", "NAM", "THPT Nguyễn Trãi", "Trần Văn Dũng", "84916123411", "TOAN", "Luyện đề THPT Quốc gia"),
    ("Lê Bảo Châu", "Lớp 8", "NU", "THCS Lý Tự Trọng", "Lê Thị Nga", "84985123412", "HOA", "Làm quen môn Hóa, bài tập cơ bản"),
    ("Võ Hải Nam", "Lớp 10", "NAM", "THPT Tôn Thất Tùng", "Võ Văn Phúc", "84908123413", "ANH", "Thi chứng chỉ Anh văn B1"),
    ("Đặng Khánh Linh", "Lớp 7", "NU", "THCS Hoàng Sa", "Đặng Thị Phượng", "84939123414", "VAN", "Chuyển sang học online (đã nghỉ)"),
    ("Bùi Thanh Tùng", "Lớp 9", "NAM", "THCS Phan Bội Châu", "Bùi Văn Thành", "84917123415", "TOAN", "Thi vào 10 trường chuyên"),
    ("Hồ Phương Thảo", "Lớp 10", "NU", "THPT Trần Phú", "Hồ Thị Cúc", "84986123416", "ANH", "Giao tiếp và thi học kỳ"),
    ("Phan Minh Khang", "Lớp 11", "NAM", "THPT Ngô Quyền", "Phan Văn Lộc", "84909123417", "TOAN", "Củng cố hàm số, lượng giác"),
    ("Nguyễn Ngọc Diệp", "Lớp 12", "NU", "THPT Phan Châu Trinh", "Nguyễn Văn Hậu", "84940123418", "IELTS", "IELTS 7.0 du học"),
    ("Trần Gia Hưng", "Lớp 8", "NAM", "THCS Nguyễn Huệ", "Trần Thị Yến", "84918123419", "LY", "Lấy lại gốc, mất kiến thức lớp 7"),
    ("Lê Tuấn Kiệt", "Lớp 9", "NAM", "THCS Lê Quý Đôn", "Lê Văn Cường", "84987123420", "HOA", "Ôn thi vào 10"),
    ("Võ Thu Hà", "Lớp 6", "NU", "THCS Trưng Vương", "Võ Thị Thanh", "84910123421", "VAN", "Rèn kỹ năng đọc hiểu"),
    ("Đặng Quốc Huy", "Lớp 10", "NAM", "THPT Phan Thành Tài", "Đặng Văn Thiện", "84941123422", "LY", "Học thêm cho kịp lớp"),
    ("Bùi Lan Phương", "Lớp 7", "NU", "THCS Nguyễn Bỉnh Khiêm", "Bùi Thị Tuyết", "84919123423", "ANH", "Tăng tốc từ vựng và nghe"),
    ("Hồ Đình Phúc", "Lớp 11", "NAM", "THPT Hòa Vang", "Hồ Văn Tín", "84988123424", "TOAN", "Ôn thi học kỳ và thi thử"),
]

NOI_DUNG = ["Ôn lại kiến thức chương trước, chữa bài tập về nhà", "Học phần mới, làm bài tập vận dụng",
            "Luyện đề kiểm tra 45 phút, rút kinh nghiệm", "Củng cố công thức, bài tập nâng cao",
            "Ôn tập tổng hợp và giải đáp thắc mắc"]
NHAN_XET = ["Em nắm chắc kiến thức, làm bài cẩn thận, cần luyện thêm dạng bài nâng cao.",
            "Em hiểu bài nhưng còn chậm ở bước biến đổi; sẽ giao thêm bài luyện tốc độ.",
            "Em tập trung tốt, tiến bộ rõ so với buổi trước, hoàn thành đủ bài tập về nhà.",
            "Em còn lúng túng phần vận dụng; buổi sau ôn lại lý thuyết và làm bài mẫu.",
            "Buổi học hiệu quả, em chủ động đặt câu hỏi và sửa lỗi sai nhanh."]
XEP_LOAI = [BuoiHoc.XepLoai.TOT, BuoiHoc.XepLoai.KHA, BuoiHoc.XepLoai.TOT, BuoiHoc.XepLoai.CAN_HO_TRO, BuoiHoc.XepLoai.KHA]


def _dau_thang(d):
    return d.replace(day=1)


class Command(BaseCommand):
    help = "Nạp dữ liệu demo phong phú (gia sư, học viên, yêu cầu, khóa học, buổi học, thù lao, hậu kiểm...)."

    @transaction.atomic
    def handle(self, *args, **opts):
        call_command("seed_demo", verbosity=0)
        if User.objects.filter(username="giasu4").exists():
            self.stdout.write("Dữ liệu mở rộng đã có (tài khoản giasu4 tồn tại) – bỏ qua.")
            return
        self.r = random.Random(2026)
        self.now = timezone.now()
        self.hom_nay = timezone.localdate()
        self.zoom_id = 90_000_000_000
        self.admin = User.objects.get(username="admin")
        self.mon = {m.ma: m for m in MonHoc.objects.all()}
        self.ts = [User.objects.get(username="tuyensinh")]
        self._tao_tuyen_sinh()
        self.gs = {u.username: u for u in User.objects.filter(vai_tro=User.VaiTro.GIA_SU)}
        self._tao_gia_su()
        self._yeu_cau_va_khoa()
        self._thu_lao_doi_soat()
        self._xu_ly_ngoai_le()
        self._thong_bao_nhat_ky()
        self.stdout.write(self.style.SUCCESS(
            f"Xong. Tổng: {User.objects.count()} tài khoản · {HocVien.objects.count()} học viên · "
            f"{YeuCauHocTap.objects.count()} yêu cầu · {KhoaHoc.objects.count()} khóa · {BuoiHoc.objects.count()} buổi · "
            f"{ThuLao.objects.count()} thù lao. Mật khẩu chung: {MAT_KHAU_DEMO}"))

    # ------------------------------------------------------------------ tài khoản
    def _user(self, username, ho_ten, vai_tro, email):
        u = User.objects.create(username=username, ho_ten=ho_ten, vai_tro=vai_tro, email=email,
                                so_dien_thoai="84" + str(self.r.randint(900000000, 989999999)))
        u.set_password(MAT_KHAU_DEMO)
        u.save()
        return u

    def _tao_tuyen_sinh(self):
        for username, ho_ten, email in TUYEN_SINH_MOI:
            self.ts.append(self._user(username, ho_ten, User.VaiTro.TUYEN_SINH, email))
        for t in self.ts:
            MaMoiGiaSu.objects.get_or_create(tuyen_sinh=t, defaults={"ma": f"MOI{t.pk:04d}{self.r.randint(1000, 9999)}"})
        # gia sư của seed_demo chưa có người mời → gán cho Tuyển sinh đầu tiên để Hậu kiểm có người phụ trách
        HoSoGiaSu.objects.filter(nguoi_moi__isnull=True).update(nguoi_moi=self.ts[0])

    def _tao_gia_su(self):
        cap_do_cua = {}
        for ma, m in self.mon.items():
            cap_do_cua[ma] = list(CapDo.objects.filter(mon_hoc=m).order_by("thu_tu"))
        for username, ho_ten, moi, tt, hoc_van, ds_mon, lich, nghi in GIA_SU_MOI:
            u = self._user(username, ho_ten, User.VaiTro.GIA_SU, f"{username}@giasu.local")
            ho_so = HoSoGiaSu.objects.create(
                user=u, trang_thai=tt, trinh_do=hoc_van, truong_hoc=hoc_van, nguoi_moi=self.ts[moi],
                ma_moi=MaMoiGiaSu.objects.filter(tuyen_sinh=self.ts[moi]).first(),
                kinh_nghiem=f"{self.r.randint(1, 6)} năm dạy kèm trực tuyến, nhiều học viên đạt điểm cao.",
                so_lop_toi_da=self.r.choice([3, 4, 4, 5]),
                tam_nghi_den=self.hom_nay + timedelta(days=nghi) if nghi else None,
                muc_tieu_buoi_thang=self.r.choice([16, 20, 24]))
            for ma, ttm in ds_mon:
                cd = cap_do_cua[ma]
                chon = cd if ma == "IELTS" else cd[: self.r.randint(3, len(cd))]
                mg = MonGiaSu.objects.create(
                    ho_so=ho_so, mon_hoc=self.mon[ma], cap_do=", ".join(c.ten for c in chon)[:100], trang_thai=ttm,
                    diem_test=round(self.r.uniform(7.5, 9.8), 1), gui_luc=self.now - timedelta(days=self.r.randint(2, 60)),
                    ly_do_dang_ky=f"{self.r.randint(1, 5)} năm kinh nghiệm dạy {self.mon[ma].ten}, có bằng cấp liên quan.",
                    duyet_boi=self.admin if ttm == "DA_DUYET" else None,
                    duyet_luc=self.now - timedelta(days=self.r.randint(1, 50)) if ttm == "DA_DUYET" else None)
                mg.cap_do_duyet.set(chon)
            for thu, khung in lich:
                tu, den = KHUNG_GIO[khung]
                LichRanh.objects.create(ho_so=ho_so, thu=thu, khung=khung, tu_gio=tu, den_gio=den)
            self.stdout.write(f"  + {username:<8} {ho_ten} ({tt})")
        # giasu8 đang hoạt động xin thêm môn Hóa; giasu2 (seed_demo) đã có IELTS chờ duyệt → hàng đợi duyệt môn
        self.gs = {u.username: u for u in User.objects.filter(vai_tro=User.VaiTro.GIA_SU)}

    # ------------------------------------------------------------------ yêu cầu, khóa học, buổi học
    def _gio_dia_phuong(self, ngay, gio, phut=0):
        return timezone.make_aware(datetime.combine(ngay, time(gio, phut)))

    def _zoom(self):
        self.zoom_id += 1
        return str(self.zoom_id), f"https://zoom.us/j/{self.zoom_id}?pwd=gia-lap"

    def _buoi(self, khoa=None, yc=None, gs=None, hv=None, bat_dau=None, phut=60, tt=TT.HOAN_TAT, loai=BuoiHoc.Loai.CHINH_THUC,
              so_thu_tu=None, thu_lao=0, ly_do_huy="", loi_zoom=""):
        mid, url = self._zoom()
        xong = tt in (TT.HOAN_TAT, TT.DANG_XEM_XET)
        i = self.r.randrange(5)
        b = BuoiHoc.objects.create(
            loai=loai, khoa_hoc=khoa, yeu_cau=yc, gia_su=gs, hoc_vien=hv, bat_dau=bat_dau, thoi_luong_phut=phut,
            trang_thai=tt, ly_do_huy=ly_do_huy, so_thu_tu=so_thu_tu, thu_lao_du_kien=thu_lao,
            han_xac_nhan=bat_dau + timedelta(minutes=phut, hours=12),
            zoom_meeting_id="" if tt == TT.LOI_ZOOM else mid, zoom_join_url="" if tt == TT.LOI_ZOOM else url,
            zoom_loi=loi_zoom, ban_ghi_trang_thai=BuoiHoc.BanGhi.KHONG_GHI,
            phong_mo_luc=bat_dau - timedelta(minutes=10) if xong or ly_do_huy == "QUA_HAN" else None,
            phong_dong_luc=bat_dau + timedelta(minutes=phut) if xong or ly_do_huy == "QUA_HAN" else None)
        if xong:
            BuoiHoc.objects.filter(pk=b.pk).update(
                xac_nhan_luc=bat_dau + timedelta(minutes=phut + self.r.randint(20, 300)),
                noi_dung=self.r.choice(NOI_DUNG), xep_loai=XEP_LOAI[i], danh_gia=NHAN_XET[i],
                dan_do_buoi_sau="Làm bài tập 1–6 trang 24" if i % 2 == 0 else "",
                thoi_luong_thuc_te=phut, phut_tham_gia_chung=phut - self.r.randint(0, 4),
                kiem_tra=BuoiHoc.KiemTra.HOP_LE, zalo_trang_thai=BuoiHoc.GuiZalo.DA_GUI)
            b.refresh_from_db()
        return b

    def _hau_kiem(self, b, ket_luan, canh_bao=False):
        """HauKiemBuoi đã chấm (da_cham=True) để lượt quét định kỳ không gọi Zoom cho buổi mẫu."""
        hk = HauKiemBuoi.objects.create(
            buoi_hoc=b, nguoi_phu_trach=getattr(getattr(b.gia_su, "ho_so_gia_su", None), "nguoi_moi", None), da_cham=True,
            tre_phut=self.r.randint(0, 3) if not canh_bao else self.r.randint(8, 25),
            ty_le_gia_su=self.r.randint(92, 100) if not canh_bao else self.r.randint(40, 60),
            ty_le_hoc_vien=self.r.randint(85, 100), do_dai_nhan_xet=len(b.danh_gia), da_gui_zalo=True)
        hk.so_canh_bao = dv_hk.so_canh_bao(hk)
        hk.ket_luan = ket_luan
        if ket_luan != KL.CHUA_KIEM_TRA:
            hk.kiem_boi, hk.kiem_luc = hk.nguoi_phu_trach, b.bat_dau + timedelta(days=1)
        if ket_luan == KL.CO_VAN_DE:
            hk.ly_do, hk.ghi_chu = HauKiemBuoi.LyDo.THIEU_GIO, "Gia sư rời phòng sớm 25 phút, đã nhắn hỏi lý do."
        hk.save()
        return hk

    def _lop_hoc(self, yc, gs, hv, so_dk, da_dung, phut, hoc_phi, lich, trang_thai=KhoaHoc.TrangThai.DANG_HOC, ghi_chu=""):
        """Tạo khóa + lịch sử buổi hằng tuần (lùi dần từ tuần gần nhất)."""
        ts = self.ts[hv.pk % len(self.ts)]
        khoa = KhoaHoc.objects.create(
            yeu_cau=yc, hoc_vien=hv, gia_su=gs, so_buoi_dang_ky=so_dk, so_buoi_da_dung=da_dung, thoi_luong_phut=phut,
            hoc_phi_moi_buoi=hoc_phi, thu_lao_moi_buoi=int(hoc_phi * 0.7 // 1000 * 1000), trang_thai=trang_thai,
            ghi_chu=ghi_chu, tao_boi=ts, tuyen_sinh_phu_trach=ts, zalo_nhom=f"{yc.mon_hoc} {hv.ho_ten} – GS {gs.ho_ten.split()[-1]}",
            ghi_chu_phu_huynh="Phụ huynh muốn nhận xét sau mỗi buổi qua Zalo.",
            lich_co_dinh=[{"thu": t, "gio": f"{g:02d}:00"} for t, g in lich],
            hoan_thanh_luc=self.now - timedelta(days=9) if trang_thai == KhoaHoc.TrangThai.HOAN_THANH else None)
        # ngày dạy gần nhất ≤ hôm qua theo thứ của buổi đầu trong lịch
        thu, gio = lich[0]
        d = self.hom_nay - timedelta(days=1)
        while d.weekday() != thu:
            d -= timedelta(days=1)
        ds = [d - timedelta(weeks=k) for k in range(da_dung)][::-1]
        return khoa, ds, gio

    def _yeu_cau(self, hv, ma_mon, tt, gs=None, **them):
        cd = list(CapDo.objects.filter(mon_hoc=self.mon[ma_mon]).order_by("thu_tu"))
        c = cd[min(len(cd) - 1, hv.pk % len(cd))]
        thu = self.r.sample(range(7), 2)
        khung = self.r.choice(["TOI", "TOI_SOM", "CHIEU", "SANG"])
        return YeuCauHocTap.objects.create(
            hoc_vien=hv, mon_hoc=self.mon[ma_mon], cap_do=c, trinh_do=c.ten, muc_tieu=them.pop("muc_tieu"),
            thu_mong_muon=thu, khung_mong_muon=[f"{t}-{khung}" for t in thu], lich_mong_muon=f"{khung.title()} theo lịch gia sư",
            trang_thai=tt, gia_su=gs, phan_cong_luc=self.now - timedelta(days=self.r.randint(2, 40)) if gs else None,
            tao_boi=self.ts[hv.pk % len(self.ts)], thu_lao_du_kien=them.pop("thu_lao", None), **them)

    def _loi_moi(self, yc, gs, tt, diem=None):
        ts = yc.tao_boi
        gui = self.now - timedelta(hours=4)
        lm = LoiMoi.objects.create(
            yeu_cau=yc, gia_su=gs, gui_boi=ts, trang_thai=tt, diem_khop=diem or self.r.randint(62, 98),
            chi_tiet_khop={"dung_mon": True, "dung_cap_do": True, "trung_gio": "2/2", "dang_nhan_lop": True},
            het_han_luc=self.now + timedelta(hours=20) if tt == LM.CHO else self.now - timedelta(hours=6),
            phan_hoi_luc=None if tt == LM.CHO else self.now - timedelta(hours=8),
            ly_do_tu_choi="Trùng lịch dạy các tối trong tuần" if tt == LM.REJECTED else "",
            cam_ket=tt == LM.ACCEPTED)
        LoiMoi.objects.filter(pk=lm.pk).update(gui_luc=gui)
        return lm

    def _yeu_cau_va_khoa(self):
        gs, ts, now = self.gs, self.ts, self.now
        hv_ds = []
        for i, (ten, lop, gt, truong, ph, sdt, ma_mon, mt) in enumerate(HOC_VIEN):
            hv_ds.append(HocVien.objects.create(
                ho_ten=ten, lop=lop, gioi_tinh=gt, truong=truong, ten_phu_huynh=ph, sdt_phu_huynh=sdt,
                dong_y_ghi_hinh=i % 3 != 0, tao_boi=ts[i % 3], tuyen_sinh_phu_trach=ts[i % 3],
                ghi_chu="Phụ huynh bận giờ hành chính, liên hệ buổi tối." if i % 4 == 0 else ""))
        mon_hv = [h[6] for h in HOC_VIEN]
        muc_tieu = [h[7] for h in HOC_VIEN]

        def yc(i, tt, g=None, **kw):
            return self._yeu_cau(hv_ds[i], mon_hv[i], tt, g, muc_tieu=muc_tieu[i], **kw)

        # --- MOI (0-2)
        for i in (0, 1, 2):
            yc(i, YC.MOI, thu_lao=120000 if i == 0 else None)
        # --- DANG_TIM (3-6) với lời mời ở nhiều trạng thái
        y = yc(3, YC.DANG_TIM); self._loi_moi(y, gs["giasu6"], LM.CHO, 92)                        # Hóa
        y = yc(4, YC.DANG_TIM); self._loi_moi(y, gs["giasu4"], LM.CHO, 94); self._loi_moi(y, gs["giasu8"], LM.CHO, 81)  # Toán
        y = yc(5, YC.DANG_TIM); self._loi_moi(y, gs["giasu7"], LM.REJECTED, 70)                    # Văn: hết người nhận → cần mời thêm
        y = yc(6, YC.DANG_TIM); self._loi_moi(y, gs["giasu9"], LM.HET_HAN, 88); self._loi_moi(y, gs["giasu5"], LM.CHO, 79)  # Anh
        # --- DA_PHAN_CONG (7-9)
        y7 = yc(7, YC.DA_PHAN_CONG, gs["giasu9"]); self._loi_moi(y7, gs["giasu9"], LM.ACCEPTED)
        self._buoi(None, y7, gs["giasu9"], hv_ds[7], self._gio_dia_phuong(self.hom_nay + timedelta(days=1), 19), 60,
                   TT.DA_LEN_LICH, BuoiHoc.Loai.HOC_THU)
        y8 = yc(8, YC.DA_PHAN_CONG, gs["giasu8"], dang_ky_thang=True); self._loi_moi(y8, gs["giasu8"], LM.ACCEPTED)
        y9 = yc(9, YC.DA_PHAN_CONG, gs["giasu4"]); self._loi_moi(y9, gs["giasu4"], LM.ACCEPTED)
        b_loi = self._buoi(None, y9, gs["giasu4"], hv_ds[9], self._gio_dia_phuong(self.hom_nay + timedelta(days=1), 17, 30),
                           60, TT.LOI_ZOOM, BuoiHoc.Loai.HOC_THU, loi_zoom="Zoom lỗi khi tạo phòng (HTTP 500): thử lại sau.")
        # --- HOC_THU_XONG (10-12) có buổi học thử hoàn tất + kết quả
        for i, g, kq in ((10, "giasu6", "DONG_Y"), (11, "giasu6", "CAN_THEM_THOI_GIAN"), (12, "giasu5", "TIM_GIA_SU_KHAC")):
            y = yc(i, YC.HOC_THU_XONG, gs[g], ket_qua_hoc_thu=kq,
                   ghi_chu_hoc_thu={"DONG_Y": "Phụ huynh hài lòng, đăng ký 12 buổi.",
                                    "CAN_THEM_THOI_GIAN": "Phụ huynh cần bàn với gia đình, hẹn gọi lại.",
                                    "TIM_GIA_SU_KHAC": "Học viên muốn thử gia sư nữ."}[kq])
            self._loi_moi(y, gs[g], LM.ACCEPTED)
            b = self._buoi(None, y, gs[g], hv_ds[i], self._gio_dia_phuong(self.hom_nay - timedelta(days=2 + i % 3), 19),
                           60, TT.HOAN_TAT, BuoiHoc.Loai.HOC_THU)
            self._hau_kiem(b, KL.HOP_LE)
            if kq == "CAN_THEM_THOI_GIAN":
                NhacViec.objects.create(nguoi_phu_trach=y.tao_boi, loai=NhacViec.Loai.GOI_LAI_PHU_HUYNH, yeu_cau=y,
                                        noi_dung=f"Gọi lại phụ huynh {hv_ds[i].ten_phu_huynh} · {y.ma}",
                                        han_luc=now + timedelta(hours=20))
        # --- DONG (13-14)
        yc(13, YC.DONG, ly_do_dong="Phụ huynh không còn nhu cầu"); yc(14, YC.DONG, ly_do_dong="Không tìm được gia sư phù hợp")

        # --- CHINH_THUC: 9 khóa (15-23)
        spec = [  # i, gia sư, số buổi đk, đã dạy, phút, học phí, lịch [(thứ, giờ)], trạng thái
            (15, "giasu5", 20, 14, 90, 220000, [(1, 19), (3, 19)], KhoaHoc.TrangThai.DANG_HOC),   # Anh
            (16, "giasu4", 12, 9, 60, 250000, [(0, 19), (2, 19)], KhoaHoc.TrangThai.DANG_HOC),    # Toán (đã đổi gia sư)
            (17, "giasu9", 12, 10, 90, 200000, [(4, 19)], KhoaHoc.TrangThai.DANG_HOC),            # IELTS, còn 2 buổi
            (18, "giasu8", 16, 5, 90, 230000, [(1, 19), (5, 15)], KhoaHoc.TrangThai.DANG_HOC),    # Lý
            (19, "giasu6", 10, 3, 60, 300000, [(2, 19), (6, 10)], KhoaHoc.TrangThai.DANG_HOC),    # Hóa (chờ xác nhận, tự hủy)
            (20, "giasu7", 10, 8, 90, 180000, [(5, 9)], KhoaHoc.TrangThai.DANG_HOC),              # Văn (buổi có vấn đề)
            (21, "giasu4", 16, 6, 60, 240000, [(4, 17)], KhoaHoc.TrangThai.TAM_DUNG),             # Lý
            (22, "giasu5", 12, 12, 90, 210000, [(6, 10)], KhoaHoc.TrangThai.HOAN_THANH),          # Anh
            (23, "giasu8", 10, 2, 60, 190000, [(3, 19)], KhoaHoc.TrangThai.HUY),                  # Toán
        ]
        ghi_chu_tt = {KhoaHoc.TrangThai.TAM_DUNG: "Học viên ốm, nghỉ 2 tuần", KhoaHoc.TrangThai.HUY: "Gia đình chuyển nơi ở"}
        khoa_cua = {}
        for n, (i, g, so_dk, da_dung, phut, hoc_phi, lich, tt_khoa) in enumerate(spec):
            hv = hv_ds[i]
            tu_hoc_thu = n % 2 == 0
            y = yc(i, YC.CHINH_THUC, gs[g], dang_ky_thang=not tu_hoc_thu,
                   ket_qua_hoc_thu="DONG_Y" if tu_hoc_thu else "")
            self._loi_moi(y, gs[g], LM.ACCEPTED)
            if tu_hoc_thu:
                b0 = self._buoi(None, y, gs[g], hv, self._gio_dia_phuong(self.hom_nay - timedelta(days=75), 19), 60,
                                TT.HOAN_TAT, BuoiHoc.Loai.HOC_THU)
                self._hau_kiem(b0, KL.HOP_LE)
            khoa, ngay, gio = self._lop_hoc(y, gs[g], hv, so_dk, da_dung, phut, hoc_phi, lich, tt_khoa, ghi_chu_tt.get(tt_khoa, ""))
            khoa_cua[i] = khoa
            xem_xet = i == 20  # buổi cuối đang xem xét (có vấn đề)
            for k, d in enumerate(ngay):
                cuoi = k == len(ngay) - 1
                co_van_de = xem_xet and cuoi
                bd = self._gio_dia_phuong(d, gio)
                b = self._buoi(khoa, y, gs[g], hv, bd, phut, TT.DANG_XEM_XET if co_van_de else TT.HOAN_TAT,
                               so_thu_tu=k + 1, thu_lao=khoa.thu_lao_moi_buoi)
                ThuLao.objects.create(buoi_hoc=b, gia_su=gs[g], thang=_dau_thang(d), so_tien=khoa.thu_lao_moi_buoi,
                                      trang_thai=ThuLao.TrangThai.TAM_GIU if co_van_de else (
                                          ThuLao.TrangThai.TAM_TINH if _dau_thang(d) == _dau_thang(self.hom_nay)
                                          else ThuLao.TrangThai.DA_DOI_SOAT))
                gan = (self.hom_nay - d).days <= 7
                if co_van_de:
                    BuoiHoc.objects.filter(pk=b.pk).update(kiem_tra=BuoiHoc.KiemTra.CO_VAN_DE,
                                                           kiem_tra_ghi_chu="Thiếu giờ: gia sư rời phòng sớm 25 phút.")
                    self._hau_kiem(b, KL.CO_VAN_DE, canh_bao=True)
                elif gan and cuoi and i % 2 == 1:
                    self._hau_kiem(b, KL.CHUA_KIEM_TRA, canh_bao=True)   # chờ Tuyển sinh kết luận, có cảnh báo
                elif gan and k == len(ngay) - 2:
                    self._hau_kiem(b, KL.CHUA_KIEM_TRA)                  # chờ kết luận, đạt đủ tiêu chí
                else:
                    self._hau_kiem(b, KL.HOP_LE)
            # buổi sắp tới (đã lên lịch) cho khóa đang học
            if tt_khoa == KhoaHoc.TrangThai.DANG_HOC and da_dung < so_dk:
                tuong_lai = self.hom_nay + timedelta(days=(lich[0][0] - self.hom_nay.weekday()) % 7 or 7)
                self._buoi(khoa, y, gs[g], hv, self._gio_dia_phuong(tuong_lai, gio), phut, TT.DA_LEN_LICH,
                           thu_lao=khoa.thu_lao_moi_buoi)
        self.khoa_cua, self.hv_ds = khoa_cua, hv_ds

        # --- khóa 17: sắp hết buổi → nhắc hỏi gia hạn
        NhacViec.objects.create(nguoi_phu_trach=khoa_cua[17].tuyen_sinh_phu_trach, loai=NhacViec.Loai.HOI_GIA_HAN,
                                khoa_hoc=khoa_cua[17], noi_dung=f"{khoa_cua[17].ma} · {hv_ds[17].ho_ten} còn 2 buổi",
                                han_luc=now + timedelta(days=1))
        # --- khóa 19: 1 buổi vừa dạy xong chờ xác nhận + 1 buổi tự hủy vì quá hạn (có yêu cầu mở lại)
        k19, y19 = khoa_cua[19], khoa_cua[19].yeu_cau
        self.cho_xn = self._buoi(k19, y19, gs["giasu6"], hv_ds[19], now - timedelta(hours=3, minutes=40), 60, TT.DA_LEN_LICH,
                                 thu_lao=k19.thu_lao_moi_buoi)
        BuoiHoc.objects.filter(pk=self.cho_xn.pk).update(phong_mo_luc=now - timedelta(hours=3, minutes=50),
                                                        phong_dong_luc=now - timedelta(hours=2, minutes=40))
        self.qua_han = self._buoi(k19, y19, gs["giasu6"], hv_ds[19], now - timedelta(days=2, hours=1), 60, TT.DA_HUY,
                                  ly_do_huy="QUA_HAN", thu_lao=k19.thu_lao_moi_buoi)
        # --- khóa 16 (Toán): đã đổi gia sư 1 lần (giasu12 nghỉ) + 1 đề xuất chờ Admin duyệt vì là lần thứ 2
        k18 = khoa_cua[16]
        DoiGiaSu.objects.create(khoa_hoc=k18, gia_su_cu=gs["giasu12"], gia_su_moi=gs["giasu4"], ly_do="GIA_SU_NGHI",
                                ghi_chu="Gia sư cũ xin tạm ngừng dạy.", thu_lao_moi=k18.thu_lao_moi_buoi,
                                gia_su_moi_dong_y=True, so_buoi_chuyen=2, trang_thai=DoiGiaSu.TrangThai.DA_THUC_HIEN,
                                tao_boi=k18.tuyen_sinh_phu_trach)
        DoiGiaSu.objects.create(khoa_hoc=k18, gia_su_cu=gs["giasu4"], gia_su_moi=gs["giasu8"], ly_do="PHU_HUYNH_YEU_CAU",
                                ghi_chu="Phụ huynh muốn gia sư dạy theo hướng ôn thi chuyên.", thu_lao_moi=k18.thu_lao_moi_buoi,
                                gia_su_moi_dong_y=True, trang_thai=DoiGiaSu.TrangThai.CHO_DUYET,
                                tao_boi=k18.tuyen_sinh_phu_trach)
        self.stdout.write(f"  + {len(hv_ds)} học viên/yêu cầu, {len(khoa_cua)} khóa học")

    # ------------------------------------------------------------------ thù lao, đối soát
    def _thu_lao_doi_soat(self):
        thang_nay = _dau_thang(self.hom_nay)
        # điều chỉnh (thưởng / trừ) ở tháng trước và tháng này
        thang_truoc = _dau_thang(thang_nay - timedelta(days=1))
        for g, tien, ly_do, thang in (("giasu4", 50000, "Thưởng dạy bù kịp tiến độ", thang_truoc),
                                      ("giasu5", -20000, "Vào phòng trễ 15 phút buổi 14/10", thang_truoc),
                                      ("giasu6", 100000, "Thưởng học viên đạt điểm cao", thang_truoc),
                                      ("giasu8", -30000, "Quên gửi nhận xét đúng hạn", thang_nay)):
            DieuChinhThuLao.objects.create(gia_su=self.gs[g], thang=thang, so_tien=tien, ly_do=ly_do, tao_boi=self.ts[0])
        # mọi tháng đã qua: đối soát đã chi trả
        thang_cu = set(ThuLao.objects.filter(thang__lt=thang_nay).values_list("gia_su_id", "thang"))
        for gia_su_id, thang in sorted(thang_cu, key=lambda x: (x[1], x[0])):
            tong = sum(t.so_tien for t in ThuLao.objects.filter(gia_su_id=gia_su_id, thang=thang).exclude(trang_thai="HUY"))
            tong += sum(d.so_tien for d in DieuChinhThuLao.objects.filter(gia_su_id=gia_su_id, thang=thang))
            ngay_chot = timezone.make_aware(datetime.combine(_dau_thang(thang + timedelta(days=32)), time(9)) + timedelta(days=14))
            DoiSoatThang.objects.create(
                gia_su_id=gia_su_id, thang=thang, tong_tien=tong, trang_thai=DoiSoatThang.TrangThai.DA_CHI_TRA,
                kiem_tra_boi=self.ts[0], kiem_tra_luc=ngay_chot - timedelta(days=3), chot_boi=self.admin, chot_luc=ngay_chot,
                chi_tra_boi=self.admin, chi_tra_luc=ngay_chot + timedelta(days=2),
                chung_tu=f"UNC-{thang:%Y-%m}-{gia_su_id:03d}")

    # ------------------------------------------------------------------ hàng đợi Cần xem xét
    def _xu_ly_ngoai_le(self):
        now = self.now
        YeuCauXuLy.objects.create(
            loai=YeuCauXuLy.Loai.MO_LAI, buoi_hoc=self.qua_han, nguoi_gui=self.gs["giasu6"],
            noi_dung="Tối hôm đó em bị sốt nên quên xác nhận, buổi học vẫn diễn ra đủ giờ. Em xin mở lại để đánh giá.",
            han_xu_ly=self.qua_han.han_xac_nhan + timedelta(days=7))
        sc = SuCoHeThong.objects.create(
            nguoi_dung=self.gs["giasu6"], duong_dan="/buoi-hoc/1/xac-nhan/", phuong_thuc="POST", ma_loi=500,
            chi_tiet="Traceback (most recent call last):\n  ...\nValueError: lỗi mẫu để demo trang Cần xem xét",
            du_lieu_form={"noi_dung": "Ôn tập chương 2", "mat_khau": "***"})
        b_loi = BuoiHoc.objects.filter(gia_su=self.gs["giasu6"], trang_thai=TT.HOAN_TAT).order_by("-bat_dau").first()
        YeuCauXuLy.objects.create(loai=YeuCauXuLy.Loai.LOI_HE_THONG, buoi_hoc=b_loi, nguoi_gui=self.gs["giasu6"], su_co=sc,
                                  noi_dung="Lỗi khi POST /buoi-hoc/xac-nhan/", han_xu_ly=now + timedelta(hours=14))
        b_zoom = BuoiHoc.objects.filter(trang_thai=TT.LOI_ZOOM).first()
        if b_zoom:
            YeuCauXuLy.objects.create(loai=YeuCauXuLy.Loai.SU_CO_ZOOM, buoi_hoc=b_zoom, nguoi_gui=b_zoom.gia_su,
                                      noi_dung="Không vào được phòng Zoom, báo lỗi 'Meeting is not valid'.",
                                      han_xu_ly=b_zoom.bat_dau)

    # ------------------------------------------------------------------ thông báo, nhật ký
    def _thong_bao_nhat_ky(self):
        now, gs = self.now, self.gs
        TB = ThongBao.Loai
        mau = [
            (self.ts[0], TB.LOI_MOI, "Lời mời mới được gửi", "2 gia sư đang chờ phản hồi YC-…", False),
            (self.ts[0], TB.KHAC, "Còn 2 buổi: gia hạn khóa học", "Hỏi phụ huynh có muốn gia hạn không.", False),
            (self.ts[1], TB.HO_SO, "Gia sư mới đăng ký qua link của bạn", "Phan Gia Huy vừa tạo tài khoản.", False),
            (self.ts[2], TB.HO_SO, "Gia sư mới đăng ký qua link của bạn", "Nguyễn Thị Lan Anh vừa tạo tài khoản.", True),
            (self.admin, TB.XEM_XET, "Có hồ sơ gia sư mới chờ duyệt", "2 hồ sơ chờ duyệt.", False),
            (self.admin, TB.XEM_XET, "Đề nghị đổi gia sư chờ duyệt", "Khóa đã đổi gia sư trước đây, cần duyệt lần 2.", False),
            (gs["giasu4"], TB.LOI_MOI, "Lời mời mới: Toán Lớp 9", "Hết hạn sau 24 giờ.", False),
            (gs["giasu8"], TB.LOI_MOI, "Lời mời mới: Vật lý", "Hết hạn sau 24 giờ.", False),
            (gs["giasu6"], TB.BUOI_HOC, "Buổi học chờ xác nhận", "Xác nhận trước hạn 12 giờ.", False),
        ]
        for u, loai, tieu_de, nd, da_doc in mau:
            tb = ThongBao.objects.create(nguoi_nhan=u, loai=loai, tieu_de=tieu_de, noi_dung=nd, da_doc=da_doc)
            ThongBao.objects.filter(pk=tb.pk).update(tao_luc=now - timedelta(hours=self.r.randint(1, 30)))
        nk = [
            (self.admin, "Duyệt môn dạy", "giasu4", "Toán, Vật lý"), (self.admin, "Duyệt môn dạy", "giasu5", "Tiếng Anh, IELTS"),
            (self.ts[0], "Tạo yêu cầu học tập", "YC-0020", "Hoàng Long – Toán"), (self.ts[0], "Gửi lời mời nhận lớp", "YC-0023", "2 gia sư"),
            (gs["giasu4"], "Nhận lớp (accept)", "YC-0021", "Toán Lớp 9"), (self.ts[1], "Tạo khóa học chính thức", "KH-0003", "12 buổi"),
            (gs["giasu5"], "Tạo buổi học", "BH-00017", "Tiếng Anh"), (gs["giasu6"], "Xác nhận hoàn tất buổi học", "BH-00021", "Tiếp thu tốt"),
            (self.ts[0], "Hậu kiểm: buổi hợp lệ", "BH-00018", ""), (self.ts[0], "Hậu kiểm: buổi có vấn đề", "BH-00030", "Thiếu giờ"),
            (self.admin, "Chốt đối soát thù lao", "giasu4", "Tháng trước"), (self.admin, "Đánh dấu đã chi trả thù lao", "Tháng trước", "9 gia sư"),
            (self.ts[2], "Gia sư đăng ký qua link mời", "giasu11", "Nguyễn Thị Lan Anh"),
            (self.ts[1], "Đề nghị đổi gia sư (chờ Admin duyệt)", "KH-0006", "Lần đổi thứ 2"), (None, "Tự hủy buổi quá hạn xác nhận", "BH-00028", ""),
        ]
        for i, (u, hanh_dong, dt, ct) in enumerate(nk):
            x = NhatKy.objects.create(nguoi_thuc_hien=u, hanh_dong=hanh_dong, doi_tuong=dt, chi_tiet=ct)
            NhatKy.objects.filter(pk=x.pk).update(thoi_diem=now - timedelta(hours=3 * (len(nk) - i)))
