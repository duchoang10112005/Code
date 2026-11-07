from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password

from .models import HocVien, HoSoGiaSu, LichRanh, MonGiaSu, MonHoc, User, YeuCauHocTap
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
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")

    def full_clean(self):
        super().full_clean()
        # Viền đỏ cho ô nhập bị lỗi (quy chuẩn: lỗi hiện ngay tại ô sai).
        for ten in self.errors:
            if ten in self.fields:
                w = self.fields[ten].widget
                w.attrs["class"] = (w.attrs.get("class", "") + " is-invalid").strip()


class DangNhapForm(BootstrapMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Sai tên đăng nhập hoặc mật khẩu.",
        "inactive": "Tài khoản đã bị khóa. Vui lòng liên hệ Admin.",
    }

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            # Đúng mật khẩu nhưng tài khoản bị khóa → báo rõ lý do (PB-01).
            username, password = self.cleaned_data.get("username"), self.cleaned_data.get("password")
            u = User.objects.filter(username=username).first()
            if u and not u.is_active and u.check_password(password):
                raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
            raise


class DoiMatKhauForm(BootstrapMixin, PasswordChangeForm):
    pass


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
