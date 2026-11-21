"""Gửi email thông báo cho người dùng (chủ yếu là gia sư) và lưu nhật ký gửi tin (D9).

Lỗi gửi email KHÔNG làm hỏng thao tác nghiệp vụ chính: chỉ ghi lại để gửi lại sau.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from core.models import NhatKyGuiTin

logger = logging.getLogger(__name__)


def gui_email(user, tieu_de, noi_dung, buoi_hoc=None, html=None):
    """noi_dung: bản văn bản thường; html (tùy chọn): bản đẹp hiển thị trong Gmail."""
    if not user.email:
        NhatKyGuiTin.objects.create(
            kenh=NhatKyGuiTin.Kenh.EMAIL, nguoi_nhan=str(user), tieu_de=tieu_de,
            noi_dung=noi_dung, buoi_hoc=buoi_hoc, thanh_cong=False,
            phan_hoi="Tài khoản chưa có email",
        )
        return False

    try:
        m = EmailMultiAlternatives(tieu_de, noi_dung, settings.DEFAULT_FROM_EMAIL, [user.email])
        if html:
            m.attach_alternative(html, "text/html")
        m.send(fail_silently=False)
        ok, phan_hoi = True, "OK"
    except Exception as exc:  # mạng lỗi, sai mật khẩu SMTP…
        logger.warning("Gửi email thất bại tới %s: %s", user.email, exc)
        ok, phan_hoi = False, str(exc)

    NhatKyGuiTin.objects.create(
        kenh=NhatKyGuiTin.Kenh.EMAIL, nguoi_nhan=user.email, tieu_de=tieu_de,
        noi_dung=noi_dung, buoi_hoc=buoi_hoc, thanh_cong=ok, phan_hoi=phan_hoi,
    )
    return ok


def thong_bao(user, tieu_de, noi_dung="", url="", loai="KHAC"):
    """Thông báo trong ứng dụng (chuông). Không bao giờ làm hỏng nghiệp vụ chính."""
    from core.models import ThongBao

    if user is None:
        return None
    try:
        return ThongBao.objects.create(nguoi_nhan=user, tieu_de=tieu_de[:200], noi_dung=noi_dung,
                                       url=url[:300], loai=loai)
    except Exception as exc:  # pragma: no cover
        logger.warning("Không tạo được thông báo cho %s: %s", user, exc)
        return None


def thong_bao_quan_tri(tieu_de, noi_dung="", url="", loai="XEM_XET"):
    from core.models import User

    for u in User.objects.filter(vai_tro=User.VaiTro.ADMIN, is_active=True):
        thong_bao(u, tieu_de, noi_dung, url, loai)


def ds_chua_doc(user, gioi_han=20):
    return user.thong_bao.filter(da_doc=False)[:gioi_han]


def danh_dau_da_doc(user, ids=None):
    qs = user.thong_bao.filter(da_doc=False)
    if ids:
        qs = qs.filter(pk__in=ids)
    return qs.update(da_doc=True)
