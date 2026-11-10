"""
Mô hình dữ liệu của hệ thống — bám theo 9 kho dữ liệu D1–D9 trên DFD (Sprint 2).

Quy ước: tên model/trường dùng tiếng Việt không dấu để đối chiếu dễ với tài liệu.
Mỗi mục bên dưới ghi rõ mã kho (D1…D9) và các quy tắc nghiệp vụ (PB/BRULE) liên quan.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q
from django.utils import timezone



# =============================================================================
# D1 – Tài khoản người dùng (PB-01, PB-24)
# =============================================================================
class User(AbstractUser):
    class VaiTro(models.TextChoices):
        ADMIN = "ADMIN", "Quản trị viên"
        TUYEN_SINH = "TUYEN_SINH", "Tuyển sinh"
        GIA_SU = "GIA_SU", "Gia sư"

    vai_tro = models.CharField("Vai trò", max_length=20, choices=VaiTro.choices)
    ho_ten = models.CharField("Họ tên", max_length=150)
    so_dien_thoai = models.CharField("Số điện thoại", max_length=20, blank=True)
    # Khóa tài khoản = is_active=False (Django tự chặn đăng nhập tài khoản không hoạt động).

    class Meta:
        verbose_name = "Tài khoản"
        verbose_name_plural = "D1 · Tài khoản người dùng"

    def __str__(self):
        return f"{self.ho_ten or self.username} ({self.get_vai_tro_display()})"

    def save(self, *args, **kwargs):
        # Tài khoản tạo bằng `createsuperuser` chưa có vai trò → mặc định là Admin.
        if self.is_superuser and not self.vai_tro:
            self.vai_tro = self.VaiTro.ADMIN
        if not self.ho_ten:
            self.ho_ten = self.get_full_name() or self.username
        super().save(*args, **kwargs)

    @property
    def la_admin(self):
        return self.vai_tro == self.VaiTro.ADMIN

    @property
    def la_tuyen_sinh(self):
        return self.vai_tro == self.VaiTro.TUYEN_SINH

    @property
    def la_gia_su(self):
        return self.vai_tro == self.VaiTro.GIA_SU


# =============================================================================
# D2 – Hồ sơ gia sư (PB-04; BRULE-09, BRULE-10)
# =============================================================================
class MonHoc(models.Model):
    ma = models.CharField("Mã môn", max_length=20, unique=True)
    ten = models.CharField("Tên môn", max_length=100)

    class Meta:
        verbose_name = "Môn học"
        verbose_name_plural = "D2 · Môn học"
        ordering = ["ten"]

    def __str__(self):
        return self.ten


class HoSoGiaSu(models.Model):
    class TrangThai(models.TextChoices):
        CHO_DUYET = "CHO_DUYET", "Chờ duyệt"
        HOAT_DONG = "HOAT_DONG", "Đang hoạt động"
        TAM_NGUNG = "TAM_NGUNG", "Tạm ngừng"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ho_so_gia_su"
    )
    kinh_nghiem = models.TextField("Kinh nghiệm", blank=True)
    trinh_do = models.CharField("Trình độ / bằng cấp", max_length=200, blank=True)
    # Email tài khoản Zoom (license) của gia sư; trống thì dùng host mặc định của trung tâm.
    email_zoom = models.EmailField("Email Zoom", blank=True)
    trang_thai = models.CharField(
        "Trạng thái", max_length=20, choices=TrangThai.choices, default=TrangThai.CHO_DUYET
    )
    cap_nhat_luc = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hồ sơ gia sư"
        verbose_name_plural = "D2 · Hồ sơ gia sư"

    def __str__(self):
        return self.user.ho_ten


class MonGiaSu(models.Model):
    """Môn gia sư đăng ký dạy. Chỉ Admin được duyệt (BRULE-10)."""

    class TrangThai(models.TextChoices):
        CHO_DUYET = "CHO_DUYET", "Chờ duyệt"
        DA_DUYET = "DA_DUYET", "Đã duyệt"
        TU_CHOI = "TU_CHOI", "Bị từ chối"

    ho_so = models.ForeignKey(HoSoGiaSu, on_delete=models.CASCADE, related_name="mon_day")
    mon_hoc = models.ForeignKey(MonHoc, on_delete=models.PROTECT)
    cap_do = models.CharField("Cấp độ dạy", max_length=100, blank=True, help_text="VD: Lớp 6–9, IELTS 6.5")
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.CHO_DUYET)
    duyet_boi = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    duyet_luc = models.DateTimeField(null=True, blank=True)
    ghi_chu_duyet = models.CharField("Ghi chú duyệt / lý do từ chối", max_length=300, blank=True)

    class Meta:
        verbose_name = "Môn dạy của gia sư"
        verbose_name_plural = "D2 · Môn dạy của gia sư"
        constraints = [
            models.UniqueConstraint(fields=["ho_so", "mon_hoc"], name="mon_gia_su_khong_trung"),
        ]

    def __str__(self):
        return f"{self.ho_so} – {self.mon_hoc} ({self.get_trang_thai_display()})"


class LichRanh(models.Model):
    class Thu(models.IntegerChoices):
        T2 = 0, "Thứ 2"
        T3 = 1, "Thứ 3"
        T4 = 2, "Thứ 4"
        T5 = 3, "Thứ 5"
        T6 = 4, "Thứ 6"
        T7 = 5, "Thứ 7"
        CN = 6, "Chủ nhật"

    ho_so = models.ForeignKey(HoSoGiaSu, on_delete=models.CASCADE, related_name="lich_ranh")
    thu = models.IntegerField(choices=Thu.choices)
    tu_gio = models.TimeField()
    den_gio = models.TimeField()

    class Meta:
        verbose_name = "Lịch rảnh"
        verbose_name_plural = "D2 · Lịch rảnh"
        ordering = ["thu", "tu_gio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(den_gio__gt=F("tu_gio")), name="lich_ranh_gio_hop_le",
                violation_error_message="Giờ kết thúc phải sau giờ bắt đầu.",
            ),
        ]

    def __str__(self):
        return f"{self.get_thu_display()} {self.tu_gio:%H:%M}–{self.den_gio:%H:%M}"


# =============================================================================
# D3 – Học viên (PB-02, PB-24)
# =============================================================================
class HocVien(models.Model):
    ho_ten = models.CharField("Họ tên học viên", max_length=150)
    lop = models.CharField("Lớp / trình độ hiện tại", max_length=50, blank=True)
    ten_phu_huynh = models.CharField("Tên phụ huynh", max_length=150)
    # Lưu dạng chuẩn 84xxxxxxxxx để gửi Zalo ZNS.
    sdt_phu_huynh = models.CharField("SĐT phụ huynh (Zalo)", max_length=15)
    dong_y_ghi_hinh = models.BooleanField("Phụ huynh đồng ý ghi hình buổi học", default=False)
    ghi_chu = models.TextField(blank=True)
    tao_boi = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    tao_luc = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Học viên"
        verbose_name_plural = "D3 · Học viên"
        ordering = ["-tao_luc"]

    def __str__(self):
        return self.ho_ten


# =============================================================================
# D4 – Yêu cầu học tập (PB-02, PB-03, PB-07, PB-08)
# =============================================================================
class YeuCauHocTap(models.Model):
    class TrangThai(models.TextChoices):
        MOI = "MOI", "Mới"
        DANG_TIM = "DANG_TIM", "Đang mời gia sư"
        DA_PHAN_CONG = "DA_PHAN_CONG", "Đã có gia sư"
        HOC_THU_XONG = "HOC_THU_XONG", "Học thử"
        CHINH_THUC = "CHINH_THUC", "Đã mở khóa"
        DONG = "DONG", "Đã đóng"

    class KetQuaHocThu(models.TextChoices):
        TIEP_TUC = "TIEP_TUC", "Tiếp tục học chính thức"
        TIM_GIA_SU_KHAC = "TIM_GIA_SU_KHAC", "Tìm gia sư khác"
        DUNG = "DUNG", "Không tiếp tục (đóng yêu cầu)"

    hoc_vien = models.ForeignKey(HocVien, on_delete=models.PROTECT, related_name="yeu_cau")
    mon_hoc = models.ForeignKey(MonHoc, on_delete=models.PROTECT)
    trinh_do = models.CharField("Trình độ / lớp", max_length=100)
    muc_tieu = models.TextField("Mục tiêu học tập")
    lich_mong_muon = models.CharField("Thời gian mong muốn", max_length=200)
    # Các thứ trong tuần học viên muốn học (0 = Thứ 2 … 6 = CN) — dùng để so khớp lịch rảnh gia sư.
    thu_mong_muon = models.JSONField("Thứ mong muốn", default=list, blank=True)
    ly_do_dong = models.CharField("Lý do đóng yêu cầu", max_length=300, blank=True)
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.MOI)
    gia_su = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="yeu_cau_duoc_phan_cong", verbose_name="Gia sư được phân công",
    )
    phan_cong_luc = models.DateTimeField(null=True, blank=True)
    ket_qua_hoc_thu = models.CharField(max_length=20, choices=KetQuaHocThu.choices, blank=True)
    ghi_chu_hoc_thu = models.TextField(blank=True)
    tao_boi = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    tao_luc = models.DateTimeField(auto_now_add=True)
    cap_nhat_luc = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yêu cầu học tập"
        verbose_name_plural = "D4 · Yêu cầu học tập"
        ordering = ["-tao_luc"]

    def __str__(self):
        return f"YC-{self.pk:04d} {self.hoc_vien} – {self.mon_hoc}"

    @property
    def ma(self):
        return f"YC-{self.pk:04d}"

    @property
    def ten_thu_mong_muon(self):
        nhan = dict(LichRanh.Thu.choices)
        return ", ".join(str(nhan.get(t, t)) for t in sorted(self.thu_mong_muon or [])) or "—"


# =============================================================================
# D5 – Lời mời nhận lớp (PB-05, PB-06, PB-22; BRULE-12)
# =============================================================================
class LoiMoi(models.Model):
    class TrangThai(models.TextChoices):
        CHO = "CHO", "Đang chờ"
        ACCEPTED = "ACCEPTED", "Đã nhận"
        REJECTED = "REJECTED", "Đã từ chối"
        VOIDED = "VOIDED", "Đã vô hiệu"
        HET_HAN = "HET_HAN", "Hết hạn"

    yeu_cau = models.ForeignKey(YeuCauHocTap, on_delete=models.CASCADE, related_name="loi_moi")
    gia_su = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loi_moi")
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.CHO)
    gui_luc = models.DateTimeField(auto_now_add=True)
    het_han_luc = models.DateTimeField()
    phan_hoi_luc = models.DateTimeField(null=True, blank=True)
    ly_do_tu_choi = models.CharField("Lý do từ chối", max_length=300, blank=True)
    gui_boi = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "Lời mời nhận lớp"
        verbose_name_plural = "D5 · Lời mời nhận lớp"
        ordering = ["-gui_luc"]
        constraints = [
            # Một gia sư chỉ có tối đa 1 lời mời đang chờ cho cùng một yêu cầu.
            models.UniqueConstraint(
                fields=["yeu_cau", "gia_su"], condition=Q(trang_thai="CHO"),
                name="mot_loi_moi_dang_cho_moi_gia_su",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.het_han_luc:
            gio = settings.NGHIEP_VU["HAN_LOI_MOI_GIO"]
            self.het_han_luc = timezone.now() + timedelta(hours=gio)
        super().save(*args, **kwargs)

    @property
    def con_hieu_luc(self):
        return self.trang_thai == self.TrangThai.CHO and self.het_han_luc > timezone.now()

    def __str__(self):
        return f"Mời {self.gia_su} – {self.yeu_cau}"


# =============================================================================
# D6 – Khóa học (PB-08, PB-09, PB-10, PB-12; BRULE-14..16)
# =============================================================================
class KhoaHoc(models.Model):
    class TrangThai(models.TextChoices):
        DANG_HOC = "DANG_HOC", "Đang học"
        HOAN_THANH = "HOAN_THANH", "Đã hoàn thành"
        TAM_DUNG = "TAM_DUNG", "Tạm dừng"
        HUY = "HUY", "Đã hủy"

    yeu_cau = models.OneToOneField(YeuCauHocTap, on_delete=models.PROTECT, related_name="khoa_hoc")
    hoc_vien = models.ForeignKey(HocVien, on_delete=models.PROTECT, related_name="khoa_hoc")
    gia_su = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="khoa_hoc_phu_trach"
    )
    so_buoi_dang_ky = models.PositiveIntegerField("Số buổi đăng ký")
    so_buoi_da_dung = models.PositiveIntegerField("Số buổi đã hoàn thành", default=0)
    class ThoiLuong(models.IntegerChoices):
        GIO_1 = 60, "1 giờ"
        GIO_1_5 = 90, "1,5 giờ"
        GIO_2 = 120, "2 giờ"

    thoi_luong_phut = models.PositiveIntegerField("Thời lượng mỗi buổi", choices=ThoiLuong.choices,
                                                  default=ThoiLuong.GIO_1_5)
    hoc_phi_moi_buoi = models.PositiveIntegerField("Học phí mỗi buổi (đ)")
    thu_lao_moi_buoi = models.PositiveIntegerField("Thù lao gia sư mỗi buổi (đ)")
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DANG_HOC)
    ghi_chu = models.CharField("Ghi chú / lý do đổi trạng thái", max_length=300, blank=True)
    tao_boi = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    tao_luc = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Khóa học"
        verbose_name_plural = "D6 · Khóa học"
        ordering = ["-tao_luc"]
        constraints = [
            # Lưới an toàn ở tầng database: không bao giờ dùng vượt số buổi đăng ký.
            models.CheckConstraint(
                condition=Q(so_buoi_da_dung__lte=F("so_buoi_dang_ky")),
                name="khoa_hoc_khong_vuot_so_buoi",
            ),
            models.CheckConstraint(condition=Q(so_buoi_dang_ky__gt=0), name="khoa_hoc_so_buoi_duong"),
            # Thù lao gia sư mỗi buổi không vượt học phí mỗi buổi (chặn nhập nhầm).
            models.CheckConstraint(
                condition=Q(thu_lao_moi_buoi__lte=F("hoc_phi_moi_buoi")), name="khoa_hoc_thu_lao_khong_vuot_hoc_phi",
                violation_error_message="Thù lao gia sư mỗi buổi không được lớn hơn học phí mỗi buổi.",
            ),
        ]

    def __str__(self):
        return f"KH-{self.pk:04d} {self.hoc_vien} – {self.yeu_cau.mon_hoc}"

    @property
    def ma(self):
        return f"KH-{self.pk:04d}"

    @property
    def phan_tram(self):
        return round(self.so_buoi_da_dung * 100 / self.so_buoi_dang_ky) if self.so_buoi_dang_ky else 0

    @property
    def tong_hoc_phi(self):
        return self.so_buoi_dang_ky * self.hoc_phi_moi_buoi

    @property
    def so_buoi_con_lai(self):
        return self.so_buoi_dang_ky - self.so_buoi_da_dung

    @property
    def so_buoi_dang_len_lich(self):
        return self.buoi_hoc.filter(trang_thai__in=BuoiHoc.TRANG_THAI_CHIEM_CHO).count()

    @property
    def so_buoi_co_the_xep(self):
        """Còn có thể xếp lịch = đăng ký − đã hoàn tất − đang lên lịch (tránh xếp vượt)."""
        return max(self.so_buoi_con_lai - self.so_buoi_dang_len_lich, 0)


class DoiGiaSu(models.Model):
    """Lịch sử đổi gia sư của một khóa (D6). NVTS thực hiện; từ lần thứ 2 trong cùng khóa cần Admin duyệt."""

    class LyDo(models.TextChoices):
        PHU_HUYNH_YEU_CAU = "PHU_HUYNH_YEU_CAU", "Phụ huynh muốn đổi gia sư"
        KHONG_PHU_HOP = "KHONG_PHU_HOP", "Gia sư chưa phù hợp (chuyên môn, phương pháp)"
        LICH_KHONG_KHOP = "LICH_KHONG_KHOP", "Lịch học không còn khớp"
        GIA_SU_NGHI = "GIA_SU_NGHI", "Gia sư nghỉ / không tiếp tục dạy"
        KHAC = "KHAC", "Lý do khác"

    class TrangThai(models.TextChoices):
        CHO_DUYET = "CHO_DUYET", "Chờ Quản trị viên duyệt"
        DA_THUC_HIEN = "DA_THUC_HIEN", "Đã thực hiện"
        TU_CHOI = "TU_CHOI", "Quản trị viên từ chối"

    khoa_hoc = models.ForeignKey(KhoaHoc, on_delete=models.PROTECT, related_name="lich_su_doi_gia_su")
    gia_su_cu = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    gia_su_moi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="+")
    ly_do = models.CharField("Lý do", max_length=30, choices=LyDo.choices)
    ghi_chu = models.CharField("Ghi chú", max_length=300, blank=True)
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DA_THUC_HIEN)
    tao_boi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    tao_luc = models.DateTimeField(auto_now_add=True)
    duyet_boi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="+")
    duyet_luc = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Đổi gia sư"
        verbose_name_plural = "D6 · Lịch sử đổi gia sư"
        ordering = ["-tao_luc"]

    def __str__(self):
        return f"Đổi GS {self.khoa_hoc.ma}: {self.gia_su_cu} ({self.get_trang_thai_display()})"


# =============================================================================
# D7 – Buổi học (PB-07, PB-11..15, PB-29, PB-31, PB-32)
# Vòng đời: LOI_ZOOM ⇄ DA_LEN_LICH → HOAN_TAT → (hậu kiểm lỗi) DANG_XEM_XET → HOAN_TAT | DA_HUY
#           DA_LEN_LICH → DA_HUY (quá hạn 12h / dời lịch / hủy)
# =============================================================================
class BuoiHoc(models.Model):
    class Loai(models.TextChoices):
        HOC_THU = "HOC_THU", "Học thử"
        CHINH_THUC = "CHINH_THUC", "Chính thức"

    class TrangThai(models.TextChoices):
        LOI_ZOOM = "LOI_ZOOM", "Lỗi Zoom"
        DA_LEN_LICH = "DA_LEN_LICH", "Đã lên lịch"
        HOAN_TAT = "HOAN_TAT", "Hoàn tất"
        DANG_XEM_XET = "DANG_XEM_XET", "Đang xem xét"
        DA_HUY = "DA_HUY", "Đã hủy"

    class LyDoHuy(models.TextChoices):
        QUA_HAN = "QUA_HAN", "Quá hạn xác nhận"
        DOI_LICH = "DOI_LICH", "Dời lịch"
        GIA_SU_HUY = "GIA_SU_HUY", "Gia sư hủy"
        HOC_VIEN_HUY = "HOC_VIEN_HUY", "Học viên xin nghỉ"
        HAU_KIEM = "HAU_KIEM", "Không đạt hậu kiểm"
        ADMIN_HUY = "ADMIN_HUY", "Trung tâm hủy"
        LOI_ZOOM = "LOI_ZOOM", "Không tạo được phòng Zoom"

    class KiemTra(models.TextChoices):
        CHUA_KIEM_TRA = "CHUA_KIEM_TRA", "Chưa kiểm tra"
        HOP_LE = "HOP_LE", "Hợp lệ"
        CO_VAN_DE = "CO_VAN_DE", "Có vấn đề"
        DA_XU_LY = "DA_XU_LY", "Đã xử lý"
        KHONG_DU_LIEU = "KHONG_DU_LIEU", "Không có dữ liệu Zoom"

    class XepLoai(models.TextChoices):
        TOT = "TOT", "Tiếp thu tốt"
        KHA = "KHA", "Tiếp thu cơ bản"
        CAN_HO_TRO = "CAN_HO_TRO", "Cần hỗ trợ thêm"

    class BanGhi(models.TextChoices):
        KHONG_GHI = "KHONG_GHI", "Không ghi hình"
        CHO_XU_LY = "CHO_XU_LY", "Zoom đang xử lý"
        SAN_SANG = "SAN_SANG", "Sẵn sàng"
        HET_HAN = "HET_HAN", "Đã hết hạn"
        LOI = "LOI", "Không lấy được"

    class GuiZalo(models.TextChoices):
        CHUA_GUI = "CHUA_GUI", "Chưa gửi"
        DA_GUI = "DA_GUI", "Đã gửi"
        LOI = "LOI", "Gửi lỗi"

    # Buổi đang "giữ chỗ" trong số buổi của khóa học (dùng cho so_buoi_co_the_xep).
    TRANG_THAI_CHIEM_CHO = [TrangThai.LOI_ZOOM, TrangThai.DA_LEN_LICH]

    loai = models.CharField(max_length=20, choices=Loai.choices)
    khoa_hoc = models.ForeignKey(
        KhoaHoc, null=True, blank=True, on_delete=models.PROTECT, related_name="buoi_hoc"
    )
    yeu_cau = models.ForeignKey(YeuCauHocTap, on_delete=models.PROTECT, related_name="buoi_hoc")
    gia_su = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="buoi_hoc")
    hoc_vien = models.ForeignKey(HocVien, on_delete=models.PROTECT, related_name="buoi_hoc")
    bat_dau = models.DateTimeField("Bắt đầu")
    thoi_luong_phut = models.PositiveIntegerField("Thời lượng (phút)", default=90)
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.LOI_ZOOM)
    ly_do_huy = models.CharField(max_length=20, choices=LyDoHuy.choices, blank=True)
    thay_the_cho = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="buoi_doi_sang",
        help_text="Buổi cũ bị dời lịch sang buổi này",
    )

    # Zoom
    zoom_meeting_id = models.CharField(max_length=50, blank=True)
    zoom_join_url = models.URLField(max_length=500, blank=True)
    zoom_start_url = models.URLField(max_length=1000, blank=True)
    zoom_passcode = models.CharField(max_length=20, blank=True)
    zoom_loi = models.TextField(blank=True)

    # Kết quả buổi học (gia sư nhập)
    noi_dung = models.TextField("Nội dung buổi học", blank=True)
    xep_loai = models.CharField("Đánh giá chung", max_length=20, choices=XepLoai.choices, blank=True)
    danh_gia = models.TextField("Nhận xét học viên", blank=True)
    dan_do_buoi_sau = models.TextField("Dặn dò cho buổi sau", blank=True)
    xac_nhan_luc = models.DateTimeField(null=True, blank=True)
    # Hạn xác nhận = giờ kết thúc + HAN_XAC_NHAN_GIO; quá hạn thì hệ thống tự hủy buổi.
    han_xac_nhan = models.DateTimeField("Hạn xác nhận", null=True, blank=True)
    da_nhac_han = models.BooleanField(default=False)
    mo_lai_luc = models.DateTimeField("Admin mở lại lúc", null=True, blank=True)
    so_thu_tu = models.PositiveIntegerField("Buổi thứ", null=True, blank=True)
    # Thù lao chụp lại lúc tạo buổi (dự kiến) và thời lượng đo được từ Zoom (thực tế).
    thu_lao_du_kien = models.PositiveIntegerField("Thù lao dự kiến (đ)", default=0)
    thoi_luong_thuc_te = models.PositiveIntegerField("Thời lượng thực tế (phút)", null=True, blank=True)

    # Hậu kiểm (chạy SAU khi gia sư xác nhận, không chặn xác nhận)
    kiem_tra = models.CharField(max_length=20, choices=KiemTra.choices, default=KiemTra.CHUA_KIEM_TRA)
    kiem_tra_ghi_chu = models.TextField(blank=True)
    phut_tham_gia_chung = models.PositiveIntegerField(null=True, blank=True)

    # Bản ghi Zoom
    ban_ghi_trang_thai = models.CharField(max_length=20, choices=BanGhi.choices, default=BanGhi.KHONG_GHI)
    ban_ghi_url = models.URLField(max_length=1000, blank=True)
    ban_ghi_passcode = models.CharField(max_length=50, blank=True)
    ban_ghi_het_han = models.DateTimeField(null=True, blank=True)

    # Zalo
    zalo_trang_thai = models.CharField(max_length=20, choices=GuiZalo.choices, default=GuiZalo.CHUA_GUI)

    tao_luc = models.DateTimeField(auto_now_add=True)
    cap_nhat_luc = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buổi học"
        verbose_name_plural = "D7 · Buổi học"
        ordering = ["-bat_dau"]
        constraints = [
            # Buổi chính thức bắt buộc thuộc một khóa học.
            models.CheckConstraint(
                condition=Q(loai="HOC_THU") | Q(khoa_hoc__isnull=False),
                name="buoi_chinh_thuc_phai_co_khoa_hoc",
            ),
        ]

    def __str__(self):
        return f"Buổi {self.get_loai_display().lower()} {self.hoc_vien} {timezone.localtime(self.bat_dau):%d/%m %H:%M}"

    @property
    def ket_thuc(self):
        return self.bat_dau + timedelta(minutes=self.thoi_luong_phut)

    @property
    def ma(self):
        return f"BH-{self.pk:05d}"

    @property
    def cho_xac_nhan(self):
        """Đã qua giờ kết thúc, chưa xác nhận và còn hạn."""
        now = timezone.now()
        return (self.trang_thai == self.TrangThai.DA_LEN_LICH and self.ket_thuc <= now
                and (self.han_xac_nhan is None or now <= self.han_xac_nhan))


# =============================================================================
# D8 – Thù lao gia sư (PB-16, PB-17; đối soát)
# =============================================================================
class ThuLao(models.Model):
    class TrangThai(models.TextChoices):
        TAM_TINH = "TAM_TINH", "Tạm tính"
        TAM_GIU = "TAM_GIU", "Tạm giữ"
        DA_DOI_SOAT = "DA_DOI_SOAT", "Đã đối soát"
        HUY = "HUY", "Đã hủy"

    # OneToOne → mỗi buổi học chỉ sinh đúng một bản ghi thù lao (chống tính trùng, PB-16).
    buoi_hoc = models.OneToOneField(BuoiHoc, on_delete=models.PROTECT, related_name="thu_lao")
    gia_su = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="thu_lao")
    thang = models.DateField("Tháng", help_text="Ngày đầu tháng")
    so_tien = models.PositiveIntegerField("Số tiền (đ)", help_text="Chụp lại mức thù lao lúc hoàn tất")
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.TAM_TINH)
    tao_luc = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Thù lao buổi học"
        verbose_name_plural = "D8 · Thù lao buổi học"
        ordering = ["-thang", "-tao_luc"]

    def __str__(self):
        return f"{self.gia_su} – {self.so_tien:,}đ ({self.get_trang_thai_display()})"


class DieuChinhThuLao(models.Model):
    """Không sửa số đã chốt — mọi thay đổi là một bản ghi điều chỉnh có lý do."""

    gia_su = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dieu_chinh_thu_lao")
    thang = models.DateField()
    buoi_hoc = models.ForeignKey(BuoiHoc, null=True, blank=True, on_delete=models.PROTECT)
    so_tien = models.IntegerField("Số tiền điều chỉnh (đ, âm = trừ)")
    ly_do = models.TextField()
    tao_boi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    tao_luc = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Điều chỉnh thù lao"
        verbose_name_plural = "D8 · Điều chỉnh thù lao"
        ordering = ["-tao_luc"]


class DoiSoatThang(models.Model):
    """Đối soát một tháng của một gia sư. Kiểm soát 2 người:
    NV tuyển sinh kiểm tra (DA_KIEM_TRA) → Admin chốt (DA_CHOT) → khóa sổ tháng đó."""

    class TrangThai(models.TextChoices):
        DA_KIEM_TRA = "DA_KIEM_TRA", "Tuyển sinh đã kiểm tra"
        DA_CHOT = "DA_CHOT", "Đã chốt"

    gia_su = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="doi_soat")
    thang = models.DateField()
    tong_tien = models.IntegerField(help_text="Tổng lúc NVTS kiểm tra; Admin chốt chỉ khi tổng không đổi")
    trang_thai = models.CharField(max_length=20, choices=TrangThai.choices, default=TrangThai.DA_KIEM_TRA)
    kiem_tra_boi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    kiem_tra_luc = models.DateTimeField(null=True, blank=True)
    chot_boi = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    chot_luc = models.DateTimeField(null=True, blank=True)
    ghi_chu = models.TextField(blank=True)

    class Meta:
        verbose_name = "Đối soát tháng"
        verbose_name_plural = "D8 · Đối soát tháng"
        constraints = [
            models.UniqueConstraint(fields=["gia_su", "thang"], name="doi_soat_mot_lan_moi_thang"),
        ]


# =============================================================================
# D9 – Nhật ký hệ thống (PB-23; nhật ký gửi tin Zalo/Email)
# =============================================================================
class NhatKy(models.Model):
    nguoi_thuc_hien = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hanh_dong = models.CharField(max_length=100)
    doi_tuong = models.CharField(max_length=200, blank=True)
    chi_tiet = models.TextField(blank=True)
    thoi_diem = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nhật ký thao tác"
        verbose_name_plural = "D9 · Nhật ký thao tác"
        ordering = ["-thoi_diem"]

    def __str__(self):
        return f"{self.thoi_diem:%d/%m %H:%M} {self.hanh_dong} {self.doi_tuong}"


class NhatKyGuiTin(models.Model):
    class Kenh(models.TextChoices):
        ZALO = "ZALO", "Zalo ZNS"
        EMAIL = "EMAIL", "Email"

    kenh = models.CharField(max_length=10, choices=Kenh.choices)
    nguoi_nhan = models.CharField(max_length=200)
    tieu_de = models.CharField(max_length=200, blank=True)
    noi_dung = models.TextField()
    buoi_hoc = models.ForeignKey(BuoiHoc, null=True, blank=True, on_delete=models.SET_NULL, related_name="tin_da_gui")
    thanh_cong = models.BooleanField(default=False)
    phan_hoi = models.TextField(blank=True, help_text="Kết quả / lỗi trả về từ dịch vụ")
    thoi_diem = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nhật ký gửi tin"
        verbose_name_plural = "D9 · Nhật ký gửi tin"
        ordering = ["-thoi_diem"]
