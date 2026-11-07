from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password

from .models import (CapDo, GoiKhoaHoc, HocVien, HoSoGiaSu, KhoaHoc, LichRanh, LoaiMon, MonGiaSu, MonHoc, User,
                     YeuCauHocTap)
from .services.tien_ich import chuan_hoa_sdt, dinh_dang_phan_tram, dinh_dang_tien


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
        fields = ["mon_hoc", "cap_do", "trinh_do", "muc_tieu", "thu_mong_muon", "lich_mong_muon"]
        labels = {"lich_mong_muon": "Khung giờ mong muốn"}
        help_texts = {"cap_do": "Quyết định học phí mỗi giờ. Khi tạo khóa vẫn đổi được nếu phụ huynh muốn."}
        widgets = {
            "muc_tieu": forms.Textarea(attrs={"rows": 3}),
            "trinh_do": forms.TextInput(attrs={"placeholder": "VD: Lớp 9, mất gốc hình học"}),
            "lich_mong_muon": forms.TextInput(attrs={"placeholder": "VD: Buổi tối 19h–21h"}),
        }

    def __init__(self, *args, khoa_mon=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mon_hoc"].empty_label = "— Chọn môn —"
        self.fields["cap_do"].required = True
        self.fields["cap_do"].empty_label = "— Chọn cấp độ —"
        self.fields["cap_do"].queryset = CapDo.objects.select_related("loai_mon")
        self.fields["cap_do"].label_from_instance = lambda c: f"{c.ten} – {dinh_dang_tien(c.don_gia_gio)}/giờ"
        # data-loai cho JS lọc cấp độ theo môn đã chọn
        self.fields["mon_hoc"].widget.attrs["data-loai-mon"] = "1"
        if khoa_mon:
            # Đã gửi lời mời theo môn này → không cho đổi môn nữa.
            self.fields["mon_hoc"].disabled = True
            self.fields["mon_hoc"].help_text = "Không đổi được môn vì đã gửi lời mời cho gia sư."

    def clean(self):
        d = super().clean()
        _kiem_tra_cap_do(self, d.get("mon_hoc"), d.get("cap_do"))
        return d


def _kiem_tra_cap_do(form, mon, cap_do, ten_truong="cap_do"):
    if mon and cap_do and mon.loai_mon_id != cap_do.loai_mon_id:
        form.add_error(ten_truong, f"Cấp độ \"{cap_do.ten}\" không thuộc loại môn của {mon} "
                                   f"({mon.loai_mon or 'chưa gán loại môn'}).")



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
        if d.get("ket_qua") == YeuCauHocTap.KetQuaHocThu.DUNG and not d.get("ghi_chu", "").strip():
            self.add_error("ghi_chu", "Cần ghi lý do phụ huynh không tiếp tục.")
        return d


class TaoKhoaHocForm(BootstrapMixin, forms.Form):
    """NVTS chỉ chọn cấp độ, gói và khung giờ; học phí / thù lao do hệ thống tính theo Bảng giá."""
    cap_do = forms.ModelChoiceField(label="Cấp độ học", queryset=CapDo.objects.none(), widget=forms.RadioSelect,
                                    empty_label=None)
    so_buoi = forms.TypedChoiceField(label="Gói khóa học", coerce=int, widget=forms.RadioSelect)
    thoi_luong_phut = forms.TypedChoiceField(label="Thời lượng mỗi buổi", coerce=int, widget=forms.RadioSelect,
                                             choices=KhoaHoc.ThoiLuong.choices, initial=KhoaHoc.ThoiLuong.GIO_1_5)

    def __init__(self, *args, goi=None, loai_mon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cap_do"].queryset = CapDo.objects.filter(loai_mon=loai_mon) if loai_mon else CapDo.objects.none()
        self.fields["cap_do"].label_from_instance = lambda c: f"{c.ten} · {dinh_dang_tien(c.don_gia_gio)}/giờ"
        goi = goi or {}
        self.fields["so_buoi"].choices = [
            (so, f"{so} buổi" + (f" – giảm {dinh_dang_phan_tram(g.ty_le_giam)}" if g.ty_le_giam else "")) for so, g in sorted(goi.items())
        ]
        if goi:
            self.fields["so_buoi"].initial = min(goi)


class CapDoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CapDo
        fields = ["loai_mon", "ten", "mo_ta", "don_gia_gio", "ty_le_trung_tam", "thu_tu"]
        labels = {"don_gia_gio": "Đơn giá / giờ (đ)", "ty_le_trung_tam": "Trung tâm giữ lại (%)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["loai_mon"].empty_label = "— Chọn loại môn —"
        if self.instance.pk:  # sửa cấp độ có sẵn: không đổi loại môn
            self.fields["loai_mon"].disabled = True

    def clean_ty_le_trung_tam(self):
        from .services.bang_gia import goi_dang_ap_dung
        tl = self.cleaned_data["ty_le_trung_tam"]
        giam_max = max((g.ty_le_giam for g in goi_dang_ap_dung().values()), default=0)
        if tl < giam_max:
            raise forms.ValidationError(
                f"Phải ≥ mức khuyến mãi lớn nhất đang chạy ({dinh_dang_phan_tram(giam_max)}), nếu không trung tâm sẽ lỗ mỗi buổi.")
        if not 0 <= tl < 100:
            raise forms.ValidationError("Tỉ lệ phải từ 0 đến dưới 100%.")
        return tl


class LoaiMonForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LoaiMon
        fields = ["ten"]
        labels = {"ten": "Tên loại môn mới"}


class GoiKhoaHocForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = GoiKhoaHoc
        fields = ["so_buoi", "ty_le_giam", "hieu_luc_tu", "hieu_luc_den", "quyen_loi"]
        help_texts = {"quyen_loi": "Mỗi dòng một quyền lợi. Để trống = giữ quyền lợi của mức đang áp dụng."}
        widgets = {"quyen_loi": forms.Textarea(attrs={"rows": 3}),
                   "hieu_luc_tu": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "hieu_luc_den": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean(self):
        from .services.bang_gia import gioi_han_giam
        d = super().clean()
        giam, tu, den = d.get("ty_le_giam"), d.get("hieu_luc_tu"), d.get("hieu_luc_den")
        gioi_han = gioi_han_giam()
        if giam is not None and gioi_han is not None and giam > gioi_han:
            self.add_error("ty_le_giam", f"Tối đa {dinh_dang_phan_tram(gioi_han)} (bằng % trung tâm giữ lại nhỏ nhất). "
                                         "Thù lao gia sư tính trên giá gốc nên giảm sâu hơn trung tâm sẽ lỗ.")
        if tu and den and den < tu:
            self.add_error("hieu_luc_den", "Ngày kết thúc phải sau ngày bắt đầu.")
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
