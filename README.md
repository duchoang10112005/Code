# Hệ thống quản lý và vận hành Trung tâm gia sư trực tuyến

Đồ án học phần **Quản trị dự án TMĐT (ELC 3013)** – Khoa TMĐT, Trường ĐH Kinh tế, ĐH Đà Nẵng – Lớp 49K22.1.
Giảng viên hướng dẫn: TS. Trương Hồng Tuấn.

## Nhóm thực hiện
| Thành viên | Vai trò |
|---|---|
| Hoàng Trung Đức | Nhóm trưởng |
| Trần Đình Phước Hưng | Thành viên |
| Lê Trường Đại | Thành viên |

## Giới thiệu
Web MVP giúp trung tâm gia sư số hóa toàn bộ quy trình: tiếp nhận yêu cầu của phụ huynh, ghép gia sư, học thử, mở khóa chính thức, tổ chức buổi học trực tuyến, đánh giá, tính thù lao và đối soát.

**3 vai trò có tài khoản:** Nhân viên tuyển sinh, Gia sư, Admin. Phụ huynh và học viên không có tài khoản.

**Luồng chính:** tiếp nhận yêu cầu → lọc và đề xuất gia sư → gia sư Accept/Reject (Accept hợp lệ đầu tiên thắng) → học thử hoặc đăng ký chính thức → tạo khóa → tạo buổi học → đánh giá và xác nhận hoàn tất → tự cập nhật số buổi và thù lao → NV tuyển sinh đối soát.

**Tích hợp dịch vụ ngoài** (có chế độ giả lập `fake` để chạy khi chưa có tài khoản):
- **Zoom API:** gia sư tạo buổi học thì hệ thống tự tạo phòng Zoom và lấy link.
- **Zalo ZNS:** gia sư lưu đánh giá thì hệ thống tự gửi đánh giá cho phụ huynh.
- **Email:** thông báo cho gia sư.

**Ngoài phạm vi:** app di động, AI matching, thanh toán online, nền tảng video riêng, kế toán, cổng phụ huynh.

## Công nghệ
Python 3 · Django 6 · SQLite · Bootstrap 5 · Zoom Server-to-Server OAuth · Zalo ZNS

## Cấu trúc thư mục
```
.
├── config/                # Cấu hình Django (settings, urls, wsgi)
├── core/                  # App chính
│   ├── models.py          # Mô hình dữ liệu (D1–D9 và các bảng bổ sung)
│   ├── migrations/        # Migration tạo và cập nhật schema
│   ├── views/             # Trang HTML theo nghiệp vụ
│   ├── api/               # API JSON cho thao tác tương tác
│   ├── services/          # Quy tắc nghiệp vụ
│   ├── integrations/      # Adapter Zoom, Zalo (fake/real)
│   ├── management/commands/   # seed_demo, quet_dinh_ky, thu_zoom, thu_zalo...
│   └── tests/             # Kiểm thử tự động
├── templates/             # Giao diện (Django template)
├── static/                # CSS, JS
├── database/schema.sql    # Schema SQLite đã xuất
├── docs/                  # Tài liệu thiết kế luồng, phân vai, bằng chứng kiểm thử
├── README_DEMO.md         # Hướng dẫn chạy thử chi tiết, bật Zoom/Zalo thật
├── .env.example           # Mẫu biến môi trường
├── requirements.txt
└── manage.py
```

## Cài đặt và chạy
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Mở http://127.0.0.1:8000

Chạy kiểm thử:
```powershell
python manage.py test core
```

## Database và migration
- Schema nằm trong `core/migrations/` và được tạo bằng `python manage.py migrate`.
- Dữ liệu mẫu nạp bằng `python manage.py seed_demo` (thêm `seed_mo_rong` nếu cần nhiều dữ liệu hơn).
- Bản schema SQL đã xuất sẵn tại [`database/schema.sql`](database/schema.sql).
- File `db.sqlite3` không đưa lên Git. Mỗi người tự tạo bằng hai lệnh trên.

## Tài khoản demo
Mật khẩu chung: `Demo@2026` (chỉ dùng trên máy dev).

| Tên đăng nhập | Vai trò |
|---|---|
| admin | Admin |
| tuyensinh | Nhân viên tuyển sinh |
| giasu1, giasu2, giasu3 | Gia sư |

## Chế độ Zoom / Zalo
Đặt trong `.env`: `ZOOM_MODE=fake|real`, `ZALO_MODE=fake|real`. Mặc định là `fake`. Cách bật chế độ thật xem [README_DEMO.md](README_DEMO.md).
Không đưa file `.env` (chứa khóa Zoom, Zalo) lên Git.

## Tài liệu liên quan
- [`docs/phan_vai.md`](docs/phan_vai.md): phân vai NV tuyển sinh / Admin / Hệ thống.
- [`docs/thiet-ke-luong/`](docs/thiet-ke-luong/): kiến trúc, thay đổi database, URL/API, sơ đồ tuần tự.
- [`docs/kiem-thu-giao-dien/`](docs/kiem-thu-giao-dien/): kịch bản và bằng chứng kiểm thử.
