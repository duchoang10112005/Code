"""Gửi email thông báo cho người dùng (chủ yếu là gia sư) và lưu nhật ký gửi tin (D9).

Lỗi gửi email KHÔNG làm hỏng thao tác nghiệp vụ chính: chỉ ghi lại để gửi lại sau.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

from core.models import NhatKyGuiTin

logger = logging.getLogger(__name__)


def gui_email(user, tieu_de, noi_dung, buoi_hoc=None):
    if not user.email:
        NhatKyGuiTin.objects.create(
            kenh=NhatKyGuiTin.Kenh.EMAIL, nguoi_nhan=str(user), tieu_de=tieu_de,
            noi_dung=noi_dung, buoi_hoc=buoi_hoc, thanh_cong=False,
            phan_hoi="Tài khoản chưa có email",
        )
        return False

    try:
        send_mail(tieu_de, noi_dung, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        ok, phan_hoi = True, "OK"
    except Exception as exc:  # mạng lỗi, sai mật khẩu SMTP…
        logger.warning("Gửi email thất bại tới %s: %s", user.email, exc)
        ok, phan_hoi = False, str(exc)

    NhatKyGuiTin.objects.create(
        kenh=NhatKyGuiTin.Kenh.EMAIL, nguoi_nhan=user.email, tieu_de=tieu_de,
        noi_dung=noi_dung, buoi_hoc=buoi_hoc, thanh_cong=ok, phan_hoi=phan_hoi,
    )
    return ok
