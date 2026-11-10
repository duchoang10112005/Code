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


class TaoTaiKhoanForm(GsoMixin, forms.ModelForm):
    """SD-03: để trống mật khẩu → hệ thống sinh mật khẩu tạm và bắt đổi khi đăng nhập lần đầu."""

    mat_khau = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, required=False)
    nhap_lai_mat_khau = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput, required=False)
    gui_email = forms.BooleanField(label="Gửi email mật khẩu tạm cho người dùng", required=False, initial=True)

    class Meta:
        model = User
        fields = ["ho_ten", "email", "so_dien_thoai", "vai_tro", "username"]
        labels = {"username": "Tên đăng nhập", "email": "Email", "ho_ten": "Họ tên", "so_dien_thoai": "Số điện thoại"}
        help_texts = {"username": "Để trống thì dùng email."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].required = False
        self.fields["ho_ten"].required = True
        self.mat_khau_tam = None

    def clean_email(self):
        e = (self.cleaned_data.get("email") or "").strip().lower()
        if e and User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Email này đã có tài khoản.")
        return e

    def clean(self):
        data = super().clean()
        if not data.get("username") and data.get("email"):
            data["username"] = data["email"]
            if User.objects.filter(username__iexact=data["username"]).exists():
                self.add_error("email", "Email này đã có tài khoản.")
        if not data.get("username") and not self.has_error("email"):
            self.add_error("username", "Nhập tên đăng nhập hoặc email.")
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
        from core.services.tai_khoan import mat_khau_tam
        user = super().save(commit=False)
        user.username = self.cleaned_data["username"]
        if self.cleaned_data.get("mat_khau"):
            user.set_password(self.cleaned_data["mat_khau"])
        else:
            self.mat_khau_tam = mat_khau_tam()
            user.set_password(self.mat_khau_tam)
            user.phai_doi_mat_khau = True
        if commit:
            user.save()
        return user


class SuaTaiKhoanForm(GsoMixin, forms.ModelForm):
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
class HoSoGiaSuForm(GsoMixin, forms.ModelForm):
    """Thông tin cá nhân trên "Hồ sơ của tôi" (SD-26)."""

    so_dien_thoai = forms.CharField(label="Số điện thoại / Zalo", max_length=20, required=False)

    class Meta:
        model = HoSoGiaSu
        fields = ["trinh_do", "truong_hoc", "kinh_nghiem", "email_zoom", "so_lop_toi_da", "tam_nghi_den",
                  "muc_tieu_buoi_thang"]
        labels = {"trinh_do": "Học vấn / bằng cấp", "truong_hoc": "Trường", "kinh_nghiem": "Giới thiệu với phụ huynh"}
        widgets = {"kinh_nghiem": forms.Textarea(attrs={"rows": 3}),
                   "tam_nghi_den": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        help_texts = {"email_zoom": "Email tài khoản Zoom cá nhân (nếu có). Để trống nếu chưa có.",
                      "tam_nghi_den": "Trong thời gian tạm nghỉ, trung tâm không gửi lời mời mới cho bạn."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["so_dien_thoai"].initial = self.instance.user.so_dien_thoai
        for ten in ("so_lop_toi_da", "muc_tieu_buoi_thang"):
            self.fields[ten].required = False

    def clean(self):
        d = super().clean()
        for ten in ("so_lop_toi_da", "muc_tieu_buoi_thang"):  # không gửi → giữ giá trị cũ
            if d.get(ten) in (None, ""):
                d[ten] = getattr(self.instance, ten)
        return d

    def save(self, commit=True):
        ho_so = super().save(commit)
        if commit and "so_dien_thoai" in self.data:
            ho_so.user.so_dien_thoai = self.cleaned_data["so_dien_thoai"]
            ho_so.user.save(update_fields=["so_dien_thoai"])
        return ho_so


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
class HocVienForm(GsoMixin, forms.ModelForm):
    class Meta:
        model = HocVien
        fields = ["ho_ten", "lop", "gioi_tinh", "truong", "ten_phu_huynh", "sdt_phu_huynh", "dong_y_ghi_hinh", "ghi_chu"]
        labels = {"sdt_phu_huynh": "SĐT / Zalo phụ huynh", "lop": "Lớp hiện tại"}
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


KHUNG_CHOICES = [(f"{t}-{k}", f"{t}-{k}") for t in range(7) for k in ("SANG", "CHIEU", "TOI_SOM", "TOI")]


class YeuCauForm(GsoMixin, forms.ModelForm):
    """Tạo / sửa yêu cầu (SD-05): lưới 7 ngày × 4 khung giờ → khung_mong_muon (+ thu_mong_muon, lich_mong_muon tự sinh)."""

    khung_mong_muon = forms.MultipleChoiceField(
        label="Lịch mong muốn", choices=KHUNG_CHOICES, widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Chọn ít nhất 1 ô khung giờ trên lưới."})

    class Meta:
        model = YeuCauHocTap
        fields = ["mon_hoc", "cap_do", "trinh_do", "muc_tieu", "khung_mong_muon", "ghi_chu", "thu_lao_du_kien"]
        labels = {"muc_tieu": "Mục tiêu học tập", "trinh_do": "Trình độ hiện tại",
                  "thu_lao_du_kien": "Thù lao dự kiến / buổi (đ)"}
        widgets = {"muc_tieu": forms.Textarea(attrs={"rows": 2, "placeholder": "VD: Lấy lại gốc đại số, đạt 8 điểm học kỳ I"}),
                   "ghi_chu": forms.Textarea(attrs={"rows": 2, "placeholder": "VD: Học viên hơi nhút nhát, ưu tiên gia sư kiên nhẫn"})}

    def __init__(self, *args, khoa_mon=False, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import CapDo
        self.fields["mon_hoc"].empty_label = "Chọn môn"
        self.fields["mon_hoc"].queryset = MonHoc.objects.filter(dang_mo=True).order_by("ten")
        self.fields["cap_do"].queryset = CapDo.objects.filter(dang_mo=True).select_related("mon_hoc")
        self.fields["cap_do"].empty_label = "Chọn cấp độ"
        self.fields["trinh_do"].required = False
        self.fields["thu_lao_du_kien"].help_text = "Gia sư thấy trong lời mời. Để trống = thỏa thuận khi mở khóa."
        if khoa_mon:
            self.fields["mon_hoc"].disabled = True
            self.fields["mon_hoc"].help_text = "Không đổi được môn vì đã gửi lời mời cho gia sư."

    def clean(self):
        d = super().clean()
        mon, cap = d.get("mon_hoc"), d.get("cap_do")
        if cap and mon and cap.mon_hoc_id not in (None, mon.pk):
            self.add_error("cap_do", "Cấp độ không thuộc môn đã chọn.")
        if not cap and not (d.get("trinh_do") or "").strip():
            self.add_error("cap_do", "Chọn cấp độ.")
        if cap and not (d.get("trinh_do") or "").strip():
            d["trinh_do"] = cap.ten
        khung = d.get("khung_mong_muon") or []
        d["khung_mong_muon"] = sorted(khung, key=lambda x: (int(x.split("-")[0]), ["SANG", "CHIEU", "TOI_SOM", "TOI"].index(x.split("-")[1])))
        d["thu_mong_muon"] = sorted({int(x.split("-")[0]) for x in khung})
        d["lich_mong_muon"] = mo_ta_khung(d["khung_mong_muon"])[:200]
        return d

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.thu_mong_muon = self.cleaned_data["thu_mong_muon"]
        obj.lich_mong_muon = self.cleaned_data["lich_mong_muon"]
        if commit:
            obj.save()
        return obj


def mo_ta_khung(khung):
    """["1-TOI","3-TOI","5-SANG"] → "T3, T5 19:00–21:00 · T7 08:00–11:00"."""
    gio = {"SANG": "08:00–11:00", "CHIEU": "14:00–17:00", "TOI_SOM": "17:30–19:00", "TOI": "19:00–21:00"}
    thu = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    theo_khung = {}
    for x in khung:
        t, k = x.split("-")
        theo_khung.setdefault(k, []).append(thu[int(t)])
    return " · ".join(f"{', '.join(v)} {gio[k]}" for k, v in sorted(theo_khung.items(), key=lambda i: list(gio).index(i[0])))


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
class KetQuaHocThuForm(GsoMixin, forms.Form):
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


THU_CHOICES = [("", "—"), ("0", "T2"), ("1", "T3"), ("2", "T4"), ("3", "T5"), ("4", "T6"), ("5", "T7"), ("6", "CN")]


class KhoaHocForm(GsoMixin, forms.ModelForm):
    """Mở khóa (SD-12): số buổi, thời lượng, học phí, thù lao, lịch cố định (tối đa 3 buổi/tuần), nhóm Zalo."""

    lich_thu_1 = forms.ChoiceField(choices=THU_CHOICES, required=False)
    lich_gio_1 = forms.TimeField(required=False, input_formats=["%H:%M"])
    lich_thu_2 = forms.ChoiceField(choices=THU_CHOICES, required=False)
    lich_gio_2 = forms.TimeField(required=False, input_formats=["%H:%M"])
    lich_thu_3 = forms.ChoiceField(choices=THU_CHOICES, required=False)
    lich_gio_3 = forms.TimeField(required=False, input_formats=["%H:%M"])

    class Meta:
        model = KhoaHoc
        fields = ["so_buoi_dang_ky", "thoi_luong_phut", "hoc_phi_moi_buoi", "thu_lao_moi_buoi", "zalo_nhom",
                  "ghi_chu_phu_huynh"]
        widgets = {"thoi_luong_phut": forms.RadioSelect, "ghi_chu_phu_huynh": forms.Textarea(attrs={"rows": 2})}
        help_texts = {
            "hoc_phi_moi_buoi": "Số tiền phụ huynh đóng cho mỗi buổi (đồng). Gia sư không thấy.",
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
        lich = []
        for i in (1, 2, 3):
            thu, gio = d.get(f"lich_thu_{i}"), d.get(f"lich_gio_{i}")
            if thu not in (None, "") and gio:
                lich.append({"thu": int(thu), "gio": f"{gio:%H:%M}"})
            elif (thu not in (None, "")) != bool(gio):
                self.add_error(f"lich_gio_{i}", "Chọn đủ thứ và giờ cho buổi cố định này.")
        d["lich_co_dinh"] = lich
        return d

    def du_lieu_khoa(self):
        d = {k: self.cleaned_data[k] for k in self.Meta.fields}
        d["lich_co_dinh"] = self.cleaned_data.get("lich_co_dinh", [])
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


class TaoBuoiForm(GsoMixin, forms.Form):
    """Tạo một hoặc nhiều buổi (SD-13). lop: "k-<id>" khóa chính thức hoặc "t-<id>" lớp chờ học thử."""

    lop = forms.CharField(label="Lớp")
    hoc_bu_cho = forms.IntegerField(label="Buổi cần bù", required=False)
    ngay = forms.DateField(label="Ngày học", input_formats=["%Y-%m-%d", "%d/%m/%Y"],
                           widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    gio = forms.TimeField(label="Giờ bắt đầu", input_formats=["%H:%M"])
    so_buoi = forms.IntegerField(label="Số buổi (lặp hằng tuần)", min_value=1, required=False, initial=1)
    thoi_luong = forms.TypedChoiceField(label="Thời lượng buổi học thử", coerce=int, required=False,
                                        choices=[(60, "60 phút"), (90, "90 phút"), (120, "120 phút")])

    def clean_lop(self):
        v = self.cleaned_data["lop"]
        loai, _, pk = v.partition("-")
        if loai not in ("k", "t") or not pk.isdigit():
            raise forms.ValidationError("Hãy chọn lớp.")
        return v

    def ke_hoach(self):
        """Danh sách giờ bắt đầu (aware) theo ngày + giờ + số tuần lặp."""
        from datetime import datetime, timedelta
        from django.utils import timezone
        d = self.cleaned_data
        dau = timezone.make_aware(datetime.combine(d["ngay"], d["gio"]))
        return [dau + timedelta(weeks=i) for i in range(d.get("so_buoi") or 1)]


class XacNhanBuoiForm(GsoMixin, forms.Form):
    """Phiếu đánh giá buổi học (SD-15, SD-16)."""

    noi_dung = forms.CharField(label="Nội dung đã dạy", max_length=1000,
                               widget=forms.Textarea(attrs={"rows": 3, "placeholder":
                                                            "VD: Phương trình bậc hai – công thức nghiệm, bài tập 1–5"}))
    xep_loai = forms.ChoiceField(label="Mức tiếp thu", choices=BuoiHoc.XepLoai.choices, widget=forms.RadioSelect)
    danh_gia = forms.CharField(label="Nhận xét tiến độ", max_length=1000, min_length=30,
                               widget=forms.Textarea(attrs={"rows": 4, "placeholder":
                                                            "Điểm học viên làm tốt, điểm cần cải thiện, thái độ học tập…"}),
                               error_messages={"min_length": "Nhận xét gửi phụ huynh cần ít nhất 30 ký tự."})
    dan_do_buoi_sau = forms.CharField(label="Bài tập về nhà", max_length=500, required=False,
                                      widget=forms.Textarea(attrs={"rows": 3, "placeholder": "VD: Làm bài 6–10 trang 42"}))
    ghi_chu_tuyen_sinh = forms.CharField(label="Ghi chú cho Tuyển sinh", max_length=500, required=False,
                                         widget=forms.Textarea(attrs={"rows": 3, "placeholder":
                                                                      "VD: Học viên vào trễ 5 phút do mạng yếu"}))
    gui_zalo_phu_huynh = forms.BooleanField(label="Gửi nhận xét cho phụ huynh qua Zalo", required=False, initial=True)


class HuyBuoiForm(GsoMixin, forms.Form):
    ly_do_huy = forms.ChoiceField(label="Lý do hủy", choices=[
        (BuoiHoc.LyDoHuy.GIA_SU_HUY, "Gia sư bận / có việc đột xuất"),
        (BuoiHoc.LyDoHuy.HOC_VIEN_HUY, BuoiHoc.LyDoHuy.HOC_VIEN_HUY.label)])
    ghi_chu = forms.CharField(label="Ghi chú", max_length=300, required=False)


class DoiLichForm(GsoMixin, forms.Form):
    bat_dau = _GioBatDauField(label="Giờ mới")


class LocBuoiForm(BootstrapMixin, forms.Form):
    thang = forms.DateField(label="Tháng", required=False, input_formats=["%Y-%m"],
                            widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"))
    trang_thai = forms.ChoiceField(label="Trạng thái", required=False,
                                   choices=[("", "Mọi trạng thái")] + list(BuoiHoc.TrangThai.choices))


class DangKyGiaSuForm(GsoMixin, forms.Form):
    """Gia sư tự đăng ký qua link mời (SD-04)."""

    ho_ten = forms.CharField(label="Họ tên", max_length=150)
    email = forms.EmailField(label="Email")
    so_dien_thoai = forms.CharField(label="Số điện thoại / Zalo", max_length=20)
    truong_hoc = forms.CharField(label="Trường / học vấn", max_length=200, required=False,
                                 widget=forms.TextInput(attrs={"placeholder": "VD: SV năm 4 Sư phạm Toán · ĐHSP Đà Nẵng"}))
    mat_khau = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)
    nhap_lai = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput)

    def clean(self):
        d = super().clean()
        mk = d.get("mat_khau") or ""
        if mk and mk != d.get("nhap_lai"):
            self.add_error("nhap_lai", "Hai mật khẩu chưa khớp.")
        if mk:
            if len(mk) < 8 or not any(c.isupper() for c in mk) or not any(c.isdigit() for c in mk):
                self.add_error("mat_khau", "Mật khẩu cần ít nhất 8 ký tự, có chữ hoa và chữ số.")
        return d
