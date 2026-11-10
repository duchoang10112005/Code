from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password

from .models import BuoiHoc, HocVien, HoSoGiaSu, KhoaHoc, LichRanh, MonGiaSu, MonHoc, User, YeuCauHocTap
from .services.tien_ich import chuan_hoa_sdt


class BootstrapMixin:
    """Tự gắn class Bootstrap cho mọi ô nhập."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            # Thay dòng trống mặc định tiếng Anh của Django ("- Select an option -") bằng tiếng Việt.
            choices = getattr(f, "choices", None)
            if choices and not isinstance(f, forms.ModelChoiceField):
                ds = list(choices)
                if ds and ds[0][0] == "" and str(ds[0][1]).lower().startswith(("-", "select")):
                    f.choices = [("", "— Chọn —")] + ds[1:]
            w = f.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")
        # Nối ô nhập với dòng gợi ý (đọc được bằng trình đọc màn hình).
        for ten_o, f in self.fields.items():
            if f.help_text and self[ten_o].auto_id:
                f.widget.attrs["aria-describedby"] = f"{self[ten_o].auto_id}_goi_y"
            else:
                f.widget.attrs.pop("aria-describedby", None)

    def full_clean(self):
        super().full_clean()
        # Viền đỏ + nối lỗi với ô nhập (quy chuẩn: lỗi hiện ngay tại ô sai).
        for ten in self.errors:
            if ten in self.fields:
                w = self.fields[ten].widget
                w.attrs["class"] = (w.attrs.get("class", "") + " is-invalid").strip()
                w.attrs["aria-invalid"] = "true"
                id_o = self[ten].auto_id
                if id_o:
                    mo_ta = [x for x in [w.attrs.get("aria-describedby"), f"{id_o}_loi"] if x]
                    w.attrs["aria-describedby"] = " ".join(mo_ta)


class GsoMixin:
    """Giao diện mới: ô nhập dùng class .inp của gso.css, lỗi gắn aria-invalid + aria-describedby."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if not isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                w.attrs.setdefault("class", "inp")
            choices = getattr(f, "choices", None)
            if choices and not isinstance(f, forms.ModelChoiceField):
                ds = list(choices)
                if ds and ds[0][0] == "" and str(ds[0][1]).lower().startswith(("-", "select")):
                    f.choices = [("", "— Chọn —")] + ds[1:]

    def full_clean(self):
        super().full_clean()
        for ten in self.errors:
            if ten in self.fields and self[ten].auto_id:
                w = self.fields[ten].widget
                w.attrs["aria-invalid"] = "true"
                w.attrs["aria-describedby"] = f"{self[ten].auto_id}_loi"


class DangNhapForm(GsoMixin, AuthenticationForm):
    """Đăng nhập bằng tên đăng nhập, email hoặc SĐT (SD-01)."""

    error_messages = {
        "invalid_login": "Email hoặc mật khẩu chưa đúng. Kiểm tra lại và thử lần nữa.",
        "inactive": "Tài khoản đã bị khóa.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email hoặc số điện thoại"
        self.fields["username"].widget.attrs.update({"placeholder": "ten@giasuonline.vn", "autofocus": True})
        self.fields["username"].max_length = 150
        self.fields["username"].error_messages["required"] = "Nhập email hoặc số điện thoại."
        self.fields["password"].error_messages["required"] = "Nhập mật khẩu."
        self.tai_khoan_bi_khoa = None

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            # Đúng mật khẩu nhưng tài khoản bị khóa → báo rõ lý do (PB-01, SD-01).
            from core.auth import tim_tai_khoan
            u = tim_tai_khoan(self.cleaned_data.get("username"))
            if u and not u.is_active and u.check_password(self.cleaned_data.get("password") or ""):
                self.tai_khoan_bi_khoa = u
                ly_do = f": {u.ly_do_khoa}" if u.ly_do_khoa else ""
                raise forms.ValidationError(f"Tài khoản đã bị khóa{ly_do}. Liên hệ Quản trị viên để được mở khóa.",
                                            code="inactive")
            raise


def kiem_tra_mat_khau_moi(user, mat_khau):
    """Điều kiện hiển thị trên màn đổi mật khẩu: ≥ 8 ký tự, có chữ hoa, có chữ số, khác mật khẩu hiện tại."""
    loi = []
    if len(mat_khau) < 8:
        loi.append("Mật khẩu cần ít nhất 8 ký tự.")
    if not any(c.isupper() for c in mat_khau):
        loi.append("Mật khẩu cần có chữ hoa.")
    if not any(c.isdigit() for c in mat_khau):
        loi.append("Mật khẩu cần có chữ số.")
    if user.check_password(mat_khau):
        loi.append("Mật khẩu mới phải khác mật khẩu hiện tại.")
    if loi:
        raise forms.ValidationError(loi)


class _QuyTacMatKhau:
    def clean_new_password1(self):
        mk = self.cleaned_data.get("new_password1") or ""
        kiem_tra_mat_khau_moi(self.user, mk)
        return mk


class DoiMatKhauForm(_QuyTacMatKhau, GsoMixin, PasswordChangeForm):
    """Tự đổi mật khẩu (từ menu cá nhân)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Mật khẩu hiện tại"
        self.fields["new_password1"].label = "Mật khẩu mới"
        self.fields["new_password1"].help_text = ""
        self.fields["new_password2"].label = "Nhập lại mật khẩu mới"


class DatMatKhauBatBuocForm(_QuyTacMatKhau, GsoMixin, SetPasswordForm):
    """Lần đăng nhập đầu / sau khi QTV đặt lại mật khẩu: không hỏi lại mật khẩu tạm (SD-02)."""

    error_messages = {"password_mismatch": "Hai mật khẩu chưa khớp."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Mật khẩu mới"
        self.fields["new_password1"].help_text = ""
        self.fields["new_password2"].label = "Nhập lại mật khẩu mới"


class TaoTaiKhoanForm(BootstrapMixin, forms.ModelForm):
    mat_khau = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)
    nhap_lai_mat_khau = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "ho_ten", "email", "so_dien_thoai", "vai_tro"]
        labels = {"username": "Tên đăng nhập", "email": "Email"}

    def clean(self):
        data = super().clean()
        if data.get("vai_tro") == User.VaiTro.GIA_SU and not data.get("email"):
            self.add_error("email", "Gia sư bắt buộc có email để nhận thông báo.")
        mk, mk2 = data.get("mat_khau"), data.get("nhap_lai_mat_khau")
        if mk and mk != mk2:
            self.add_error("nhap_lai_mat_khau", "Mật khẩu nhập lại không khớp.")
        elif mk:
            try:
                validate_password(mk)
            except forms.ValidationError as e:
                self.add_error("mat_khau", e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["mat_khau"])
        if commit:
            user.save()
        return user


class SuaTaiKhoanForm(BootstrapMixin, forms.ModelForm):
    mat_khau_moi = forms.CharField(
        label="Đặt lại mật khẩu", required=False, widget=forms.PasswordInput,
        help_text="Để trống nếu không đổi.",
    )

    class Meta:
        model = User
        fields = ["ho_ten", "email", "so_dien_thoai", "vai_tro"]

    def clean(self):
        data = super().clean()
        if data.get("vai_tro") == User.VaiTro.GIA_SU and not data.get("email"):
            self.add_error("email", "Gia sư bắt buộc có email để nhận thông báo.")
        mk = data.get("mat_khau_moi")
        if mk:
            try:
                validate_password(mk, self.instance)
            except forms.ValidationError as e:
                self.add_error("mat_khau_moi", e)
        return data


# ---------------------------------------------------------------------------
# Phần 2 – Hồ sơ gia sư (PB-04)
# ---------------------------------------------------------------------------
class HoSoGiaSuForm(BootstrapMixin, forms.ModelForm):
    so_dien_thoai = forms.CharField(label="Số điện thoại", max_length=20, required=False)

    class Meta:
        model = HoSoGiaSu
        fields = ["trinh_do", "kinh_nghiem", "email_zoom"]
        widgets = {"kinh_nghiem": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "email_zoom": "Email tài khoản Zoom trung tâm cấp cho bạn. Để trống nếu chưa có.",
            "kinh_nghiem": "Số năm dạy, đối tượng học viên, thành tích nổi bật…",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["so_dien_thoai"].initial = self.instance.user.so_dien_thoai

    def save(self, commit=True):
        ho_so = super().save(commit)
        ho_so.user.so_dien_thoai = self.cleaned_data["so_dien_thoai"]
        if commit:
            ho_so.user.save(update_fields=["so_dien_thoai"])
        return ho_so


class DangKyMonForm(BootstrapMixin, forms.Form):
    mon_hoc = forms.ModelChoiceField(label="Môn học", queryset=MonHoc.objects.none(), empty_label="— Chọn môn —")
    cap_do = forms.CharField(label="Cấp độ dạy", max_length=100,
                             widget=forms.TextInput(attrs={"placeholder": "VD: Lớp 6–9, IELTS 6.5"}))

    def __init__(self, *args, ho_so=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Ẩn môn đã duyệt hoặc đang chờ; môn bị từ chối vẫn được đăng ký lại.
        da_co = ho_so.mon_day.exclude(trang_thai=MonGiaSu.TrangThai.TU_CHOI).values("mon_hoc") if ho_so else []
        self.fields["mon_hoc"].queryset = MonHoc.objects.exclude(pk__in=da_co)


class LichRanhForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LichRanh
        fields = ["thu", "tu_gio", "den_gio"]
        labels = {"thu": "Thứ", "tu_gio": "Từ", "den_gio": "Đến"}
        widgets = {
            "tu_gio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "den_gio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }


class LocGiaSuForm(BootstrapMixin, forms.Form):
    q = forms.CharField(label="Tìm kiếm", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Tên, email gia sư"}))
    mon = forms.ModelChoiceField(label="Môn đã duyệt", queryset=MonHoc.objects.all(), required=False,
                                 empty_label="Mọi môn")
    trang_thai = forms.ChoiceField(label="Trạng thái hồ sơ", required=False,
                                   choices=[("", "Mọi trạng thái")] + list(HoSoGiaSu.TrangThai.choices))
    thu = forms.ChoiceField(label="Rảnh vào", required=False,
                            choices=[("", "Mọi ngày")] + list(LichRanh.Thu.choices))
    cho_duyet = forms.BooleanField(label="Chỉ hồ sơ có môn chờ duyệt", required=False)


# ---------------------------------------------------------------------------
# Phần 3 – Học viên, yêu cầu học tập (PB-02, PB-03, PB-19)
# ---------------------------------------------------------------------------
class HocVienForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = HocVien
        fields = ["ho_ten", "lop", "ten_phu_huynh", "sdt_phu_huynh", "dong_y_ghi_hinh", "ghi_chu"]
        widgets = {"ghi_chu": forms.Textarea(attrs={"rows": 2})}
        help_texts = {
            "sdt_phu_huynh": "Số Zalo của phụ huynh để nhận đánh giá buổi học. VD: 0905 123 456",
            "dong_y_ghi_hinh": "Không đồng ý thì phòng Zoom vẫn được tạo nhưng không ghi hình.",
        }

    def clean_sdt_phu_huynh(self):
        sdt = chuan_hoa_sdt(self.cleaned_data["sdt_phu_huynh"])
        if not sdt:
            raise forms.ValidationError("Số điện thoại không hợp lệ. Ví dụ đúng: 0905 123 456")
        return sdt


class ChonHocVienForm(BootstrapMixin, forms.Form):
    hoc_vien = forms.ModelChoiceField(
        label="Học viên", queryset=HocVien.objects.order_by("ho_ten"), required=False,
        empty_label="— Học viên mới (nhập bên dưới) —",
    )


class YeuCauForm(BootstrapMixin, forms.ModelForm):
    thu_mong_muon = forms.TypedMultipleChoiceField(
        label="Các thứ muốn học", choices=LichRanh.Thu.choices, coerce=int,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Chọn ít nhất một thứ trong tuần."},
    )

    class Meta:
        model = YeuCauHocTap
        fields = ["mon_hoc", "trinh_do", "muc_tieu", "thu_mong_muon", "lich_mong_muon"]
        labels = {"lich_mong_muon": "Khung giờ mong muốn"}
        widgets = {
            "muc_tieu": forms.Textarea(attrs={"rows": 3}),
            "trinh_do": forms.TextInput(attrs={"placeholder": "VD: Lớp 9, mất gốc hình học"}),
            "lich_mong_muon": forms.TextInput(attrs={"placeholder": "VD: Buổi tối 19h–21h"}),
        }

    def __init__(self, *args, khoa_mon=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mon_hoc"].empty_label = "— Chọn môn —"
        if khoa_mon:
            # Đã gửi lời mời theo môn này → không cho đổi môn nữa.
            self.fields["mon_hoc"].disabled = True
            self.fields["mon_hoc"].help_text = "Không đổi được môn vì đã gửi lời mời cho gia sư."


class LocYeuCauForm(BootstrapMixin, forms.Form):
    q = forms.CharField(label="Tìm kiếm", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Mã YC, học viên, phụ huynh"}))
    trang_thai = forms.ChoiceField(label="Trạng thái", required=False,
                                   choices=[("", "Mọi trạng thái")] + list(YeuCauHocTap.TrangThai.choices))
    mon = forms.ModelChoiceField(label="Môn", queryset=MonHoc.objects.all(), required=False, empty_label="Mọi môn")
    can_moi_them = forms.BooleanField(label="Cần mời thêm gia sư", required=False)
    cho_chot = forms.BooleanField(label="Chờ chốt hình thức học", required=False)


# ---------------------------------------------------------------------------
# Phần 4 – Khóa học (PB-07..PB-10)
# ---------------------------------------------------------------------------
class KetQuaHocThuForm(BootstrapMixin, forms.Form):
    ket_qua = forms.ChoiceField(label="Phụ huynh quyết định", choices=YeuCauHocTap.KetQuaHocThu.choices,
                                widget=forms.RadioSelect)
    ghi_chu = forms.CharField(label="Ghi chú", required=False, max_length=300,
                              widget=forms.Textarea(attrs={"rows": 2}),
                              help_text="Bắt buộc khi phụ huynh không tiếp tục.")

    def clean(self):
        d = super().clean()
        if d.get("ket_qua") == YeuCauHocTap.KetQuaHocThu.KHONG_DANG_KY and not d.get("ghi_chu", "").strip():
            self.add_error("ghi_chu", "Cần ghi lý do phụ huynh không tiếp tục.")
        return d


class KhoaHocForm(BootstrapMixin, forms.ModelForm):
    """Tạo khóa: NV tuyển sinh nhập số buổi, thời lượng, học phí và thù lao mỗi buổi.
    (Bảng giá tự tính đang tạm gỡ chờ nhóm nghiên cứu – xem tag Git luu-bang-gia.)"""

    class Meta:
        model = KhoaHoc
        fields = ["so_buoi_dang_ky", "thoi_luong_phut", "hoc_phi_moi_buoi", "thu_lao_moi_buoi"]
        widgets = {"thoi_luong_phut": forms.RadioSelect}
        help_texts = {
            "hoc_phi_moi_buoi": "Số tiền phụ huynh đóng cho mỗi buổi (đồng).",
            "thu_lao_moi_buoi": "Số tiền trả gia sư cho mỗi buổi hợp lệ, không vượt học phí.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["so_buoi_dang_ky"].widget.attrs["min"] = 1

    def clean_so_buoi_dang_ky(self):
        so = self.cleaned_data["so_buoi_dang_ky"]
        if so < 1:
            raise forms.ValidationError("Số buổi đăng ký phải lớn hơn 0.")
        return so

    def clean(self):
        d = super().clean()
        hp, tl = d.get("hoc_phi_moi_buoi"), d.get("thu_lao_moi_buoi")
        if hp is not None and tl is not None and tl > hp:
            self.add_error("thu_lao_moi_buoi", "Thù lao gia sư mỗi buổi không được lớn hơn học phí mỗi buổi.")
        return d


class LocKhoaHocForm(BootstrapMixin, forms.Form):
    q = forms.CharField(label="Tìm kiếm", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Học viên, mã KH"}))
    trang_thai = forms.ChoiceField(label="Trạng thái", required=False,
                                   choices=[("", "Mọi trạng thái")])
    gia_su = forms.ModelChoiceField(label="Gia sư", required=False, empty_label="Mọi gia sư",
                                    queryset=User.objects.filter(vai_tro=User.VaiTro.GIA_SU).order_by("ho_ten"))
    mon = forms.ModelChoiceField(label="Môn", queryset=MonHoc.objects.all(), required=False, empty_label="Mọi môn")
    sap_het = forms.BooleanField(label="Sắp hết buổi (còn ≤ 2)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["trang_thai"].choices = [("", "Mọi trạng thái")] + list(KhoaHoc.TrangThai.choices)


# =============================================================================
# Phần 5 – Buổi học
# =============================================================================
DINH_DANG_GIO = "%Y-%m-%dT%H:%M"


class _GioBatDauField(forms.DateTimeField):
    def __init__(self, **kw):
        kw.setdefault("label", "Ngày giờ bắt đầu")
        kw.setdefault("input_formats", [DINH_DANG_GIO])
        kw.setdefault("widget", forms.DateTimeInput(attrs={"type": "datetime-local", "step": 60},
                                                    format=DINH_DANG_GIO))
        super().__init__(**kw)


class TaoBuoiForm(BootstrapMixin, forms.Form):
    """Gia sư chọn lớp: khóa chính thức (k-<id>) hoặc lớp chờ học thử (t-<id>)."""

    lop = forms.ChoiceField(label="Lớp")
    bat_dau = _GioBatDauField()
    thoi_luong = forms.TypedChoiceField(
        label="Thời lượng buổi học thử", coerce=int, required=False, initial=60,
        choices=[(60, "1 giờ"), (90, "1,5 giờ"), (120, "2 giờ")], widget=forms.RadioSelect,
        help_text="Buổi chính thức luôn theo thời lượng đã đăng ký của khóa.")

    def __init__(self, *args, ds_khoa=(), ds_thu=(), **kwargs):
        super().__init__(*args, **kwargs)
        nhom = []
        if ds_khoa:
            nhom.append(("Khóa chính thức", [
                (f"k-{k.pk}", f"{k.ma} · {k.hoc_vien.ho_ten} · {k.yeu_cau.mon_hoc} "
                              f"(còn xếp được {k.so_buoi_co_the_xep} buổi)") for k in ds_khoa]))
        if ds_thu:
            nhom.append(("Học thử", [(f"t-{y.pk}", f"{y.ma} · {y.hoc_vien.ho_ten} · {y.mon_hoc}") for y in ds_thu]))
        self.fields["lop"].choices = [("", "— Chọn lớp —")] + nhom


class XacNhanBuoiForm(BootstrapMixin, forms.Form):
    noi_dung = forms.CharField(label="Nội dung đã dạy", max_length=1000,
                               widget=forms.Textarea(attrs={"rows": 3}))
    xep_loai = forms.ChoiceField(label="Đánh giá chung", choices=BuoiHoc.XepLoai.choices, widget=forms.RadioSelect)
    danh_gia = forms.CharField(label="Nhận xét học viên", max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
                               help_text="Nội dung này được gửi cho phụ huynh qua Zalo.")
    dan_do_buoi_sau = forms.CharField(label="Dặn dò cho buổi sau", max_length=500, required=False,
                                      widget=forms.Textarea(attrs={"rows": 2}))


class HuyBuoiForm(BootstrapMixin, forms.Form):
    ly_do_huy = forms.ChoiceField(label="Lý do hủy", choices=[
        (BuoiHoc.LyDoHuy.GIA_SU_HUY, "Gia sư bận / có việc đột xuất"),
        (BuoiHoc.LyDoHuy.HOC_VIEN_HUY, BuoiHoc.LyDoHuy.HOC_VIEN_HUY.label)])
    ghi_chu = forms.CharField(label="Ghi chú", max_length=300, required=False)


class DoiLichForm(BootstrapMixin, forms.Form):
    bat_dau = _GioBatDauField(label="Giờ mới")


class LocBuoiForm(BootstrapMixin, forms.Form):
    thang = forms.DateField(label="Tháng", required=False, input_formats=["%Y-%m"],
                            widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"))
    trang_thai = forms.ChoiceField(label="Trạng thái", required=False,
                                   choices=[("", "Mọi trạng thái")] + list(BuoiHoc.TrangThai.choices))
