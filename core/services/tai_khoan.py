"""Tài khoản (SD-03): mật khẩu tạm, khóa / mở khóa, đặt lại mật khẩu."""

import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import HoSoGiaSu, User
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email

_KY_TU = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"  # bỏ 0/O/1/l/I dễ nhầm


def mat_khau_tam(do_dai=10):
    while True:
        mk = "".join(secrets.choice(_KY_TU) for _ in range(do_dai))
        if any(c.isupper() for c in mk) and any(c.isdigit() for c in mk) and any(c.islower() for c in mk):
            return mk


def dam_bao_ho_so(user):
    if user.la_gia_su:
        HoSoGiaSu.objects.get_or_create(user=user)


def gui_mat_khau(user, mk, lan_dau=True):
    gui_email(user, "Tài khoản Gia Sư Online" if lan_dau else "Mật khẩu tạm mới",
              f"Chào {user.ho_ten},\n\nTên đăng nhập: {user.username}\nMật khẩu tạm: {mk}\n\n"
              "Lần đăng nhập đầu tiên hệ thống sẽ yêu cầu bạn đặt mật khẩu mới.")


def khoa(admin, user, ly_do=""):
    if user == admin:
        raise ValidationError("Không thể tự khóa tài khoản của chính mình.")
    from core.services.yeu_cau import huy_loi_moi_cua_gia_su
    ly_do = (ly_do or "").strip()[:300]
    with transaction.atomic():
        User.objects.filter(pk=user.pk).update(is_active=False, ly_do_khoa=ly_do, khoa_luc=timezone.now())
        ghi_nhat_ky(admin, "Khóa tài khoản", user.username, ly_do, loai="TAI_KHOAN")
    huy_loi_moi_cua_gia_su(user, "Tài khoản bị khóa")


def mo_khoa(admin, user):
    User.objects.filter(pk=user.pk).update(is_active=True, ly_do_khoa="", khoa_luc=None)
    ghi_nhat_ky(admin, "Mở khóa tài khoản", user.username, loai="TAI_KHOAN")


def dat_lai_mat_khau(admin, user):
    mk = mat_khau_tam()
    user.set_password(mk)
    user.phai_doi_mat_khau = True
    user.save(update_fields=["password", "phai_doi_mat_khau"])
    ghi_nhat_ky(admin, "Đặt lại mật khẩu", user.username, "Mật khẩu tạm, bắt đổi khi đăng nhập", loai="TAI_KHOAN")
    gui_mat_khau(user, mk, lan_dau=False)
    return mk
