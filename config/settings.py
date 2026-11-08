"""
Cấu hình Django cho Hệ thống quản lý Trung tâm gia sư trực tuyến.

Các giá trị bí mật / thay đổi theo máy (SECRET_KEY, khóa Zoom, Zalo, mật khẩu email)
được đọc từ file `.env` (không đưa lên Git). Xem mẫu trong `.env.example`.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Bảo mật ---------------------------------------------------------------
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-chi-dung-khi-dev-hay-dat-SECRET_KEY-trong-file-env",
)
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]


# --- Ứng dụng ---------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.ChanTaiKhoanBiKhoaMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.thong_tin_chung",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Cơ sở dữ liệu ----------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # DB_PATH: dùng database khác (VD thử seed_demo trên bản sạch) mà không đụng db.sqlite3.
        "NAME": os.getenv("DB_PATH") or BASE_DIR / "db.sqlite3",
    }
}


# --- Tài khoản & đăng nhập (D1) --------------------------------------------
AUTH_USER_MODEL = "core.User"
LOGIN_URL = "dang_nhap"
LOGIN_REDIRECT_URL = "trang_chu"
LOGOUT_REDIRECT_URL = "dang_nhap"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Khi chạy test: dùng thuật toán băm nhanh cho đỡ chờ (không ảnh hưởng hệ thống thật).
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# --- Ngôn ngữ & thời gian ---------------------------------------------------
LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True


# --- File tĩnh --------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Email (thông báo cho gia sư) ------------------------------------------
# Mặc định: in email ra terminal (dev). Muốn gửi thật: đặt EMAIL_MODE=smtp trong .env.
if os.getenv("EMAIL_MODE", "console") == "smtp":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Địa chỉ gốc của hệ thống, dùng để tạo link đầy đủ trong email gửi gia sư / NVTS.
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Trung tâm gia sư <no-reply@giasu.local>")


# --- Tích hợp ngoài: Zoom & Zalo -------------------------------------------
# "fake" = giả lập (demo/test không cần mạng), "real" = gọi API thật.
ZOOM_MODE = os.getenv("ZOOM_MODE", "fake")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")
ZOOM_HOST_EMAIL_MAC_DINH = os.getenv("ZOOM_HOST_EMAIL_MAC_DINH", "")

ZALO_MODE = os.getenv("ZALO_MODE", "fake")
ZALO_ACCESS_TOKEN = os.getenv("ZALO_ACCESS_TOKEN", "")
ZALO_TEMPLATE_ID = os.getenv("ZALO_TEMPLATE_ID", "")


# --- Tham số nghiệp vụ (chỉnh được, không cần sửa code) --------------------
NGHIEP_VU = {
    # Gia sư và học viên phải cùng có mặt >= tỉ lệ này của thời lượng buổi học (hậu kiểm).
    "NGUONG_THAM_GIA": float(os.getenv("NGUONG_THAM_GIA", "0.67")),
    # Quá số giờ này sau giờ kết thúc mà chưa xác nhận → tự hủy buổi học.
    "HAN_XAC_NHAN_GIO": int(os.getenv("HAN_XAC_NHAN_GIO", "12")),
    # Lời mời nhận lớp hết hạn sau số giờ này.
    "HAN_LOI_MOI_GIO": int(os.getenv("HAN_LOI_MOI_GIO", "24")),
    # Bản ghi Zoom được lưu bao nhiêu ngày.
    "NGAY_LUU_BAN_GHI": int(os.getenv("NGAY_LUU_BAN_GHI", "30")),
    # Gửi email nhắc gia sư khi còn số giờ này là hết hạn xác nhận.
    "NHAC_TRUOC_HAN_GIO": int(os.getenv("NHAC_TRUOC_HAN_GIO", "3")),
    # Số phòng Zoom chạy cùng lúc = số tài khoản Zoom có license. MVP: 1 tài khoản → 1 buổi tại một thời điểm.
    "SO_PHONG_ZOOM_DONG_THOI": int(os.getenv("SO_PHONG_ZOOM_DONG_THOI", "1")),
    # Admin chỉ được mở lại buổi bị tự hủy trong số ngày này; khi mở lại gia sư có thêm số giờ này.
    "NGAY_MO_LAI_TOI_DA": int(os.getenv("NGAY_MO_LAI_TOI_DA", "7")),
    "GIO_XAC_NHAN_KHI_MO_LAI": int(os.getenv("GIO_XAC_NHAN_KHI_MO_LAI", "24")),
}
