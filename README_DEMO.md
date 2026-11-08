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

## Bật Zoom API thật (1 tài khoản Zoom của trung tâm)
Bản MVP dùng **một** tài khoản Zoom. Mọi buổi học đều tạo phòng dưới tài khoản này, gia sư không cần tài khoản Zoom riêng:
- Gia sư mở phòng bằng nút **Mở phòng (gia sư)**. Hệ thống lấy link host mới mỗi lần bấm, vì link host chỉ dùng được khoảng 2 giờ.
- Học viên vào phòng bằng link join mà gia sư gửi qua Zalo.

1. Đăng nhập https://marketplace.zoom.us bằng tài khoản Zoom của trung tâm, chọn **Develop → Build App → Server-to-Server OAuth App**.
2. Đặt tên app (ví dụ "Gia su MVP"). Trong mục **Scopes**, thêm các quyền:
   - `meeting:write:admin`, `meeting:read:admin`: tạo, xóa phòng và lấy link host;
   - `user:read:admin`;
   - `report:read:admin` và `recording:read:admin`: chỉ dùng được khi có gói Pro.
3. Bấm **Activate**. Chép **Account ID, Client ID, Client Secret** vào `.env`:
   ```
   ZOOM_MODE=real
   ZOOM_ACCOUNT_ID=...
   ZOOM_CLIENT_ID=...
   ZOOM_CLIENT_SECRET=...
   ZOOM_HOST_EMAIL_MAC_DINH=email-tai-khoan-zoom@...
   ```
4. Chạy `python manage.py thu_zoom`. Lệnh này tạo rồi xóa một phòng thử. Thấy dòng "Kết nối Zoom hoạt động" là xong.

**Giới hạn theo gói Zoom:**
| | Free | Pro |
|---|---|---|
| Tạo / xóa phòng qua API | Có | Có |
| Thời lượng mỗi buổi | Tối đa 40 phút | Không giới hạn |
| Hậu kiểm (danh sách người tham gia) | Không có: buổi được ghi "Không có dữ liệu Zoom" và giữ như gia sư xác nhận | Có |
| Bản ghi cloud | Không | Có |

Một tài khoản Zoom chỉ mở được một phòng tại một thời điểm, nên hệ thống chặn hai buổi trùng giờ trên toàn trung tâm. Khi trung tâm có nhiều tài khoản, tăng `SO_PHONG_ZOOM_DONG_THOI` trong `.env`. Nhưng muốn thật sự chạy song song thì code phải được nâng cấp để mỗi buổi chọn một tài khoản Zoom còn trống.

## Việc chạy định kỳ
`python manage.py quet_dinh_ky` làm 3 việc:
- nhắc gia sư sắp hết hạn xác nhận và tự hủy buổi quá 12h;
- hậu kiểm Zoom, lấy bản ghi;
- cho lời mời quá hạn hết hiệu lực.

Phần nhắc hạn và tự hủy cũng tự chạy mỗi khi có người mở trang. Phần hậu kiểm Zoom thì cần đặt Windows Task Scheduler chạy lệnh này 15 phút một lần, hoặc chạy tay trước khi demo.
