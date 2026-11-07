# Chạy thử hệ thống (dành cho cả nhóm)

## Lần đầu sau khi clone / pull
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Mở http://127.0.0.1:8000

> Nếu đã có database cũ từ trước Phần 1, xóa `db.sqlite3` rồi chạy lại `migrate` và `seed_demo`.

## Tài khoản demo (chỉ dùng trên máy dev)
Mật khẩu chung: `Demo@2026`

| Tên đăng nhập | Vai trò | Ghi chú |
|---|---|---|
| admin | Admin | Có thể vào thêm /django-admin/ để tra dữ liệu |
| tuyensinh | Nhân viên tuyển sinh | |
| giasu1 | Gia sư | Toán, Vật lý (đã duyệt) |
| giasu2 | Gia sư | Tiếng Anh (đã duyệt), IELTS (chờ duyệt) |
| giasu3 | Gia sư | Toán tiểu học, Ngữ văn (đã duyệt) |

## Chạy test
```bash
python manage.py test core
```

## Chế độ Zoom / Zalo / Email
Đặt trong `.env`:
- `ZOOM_MODE=fake` / `ZALO_MODE=fake`: giả lập, không cần tài khoản thật (mặc định).
- `EMAIL_MODE=console`: email thông báo in ra cửa sổ terminal đang chạy `runserver`.
