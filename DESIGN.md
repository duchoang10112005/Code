# DESIGN – Giao diện "Sổ liên lạc"

Hệ thống quản lý Trung tâm Gia sư Trực tuyến · Django + Bootstrap 5.3 · Be Vietnam Pro · ưu tiên máy tính.
Mã nguồn chuẩn: `static/css/app.css`. Trang xem trước: `/quy-chuan-giao-dien/` (chỉ bật khi DEBUG).

## Ý tưởng
Mỗi ngày làm việc là một trang trong cuốn sổ liên lạc: bìa sổ xanh đậm, mỗi hồ sơ có một nhãn vở viền kép,
và hệ thống "phê" bằng mực đỏ vào những chỗ cần xử lý. Không dùng kiểu bảng điều khiển SaaS với hàng card số liệu.

## Màu (chỉ dùng biến `--gs-*`, không gõ mã màu trong template)
| Biến | Giá trị | Dùng cho |
|---|---|---|
| `--gs-cover` | #1D3A7A | Menu trái (bìa sổ), nút chính, đường kẻ dưới tiêu đề nhóm và đầu bảng |
| `--gs-ink` | #1E40AF | Link, mã hồ sơ, dữ liệu |
| `--gs-red` | #B71C1C | **Chỉ** cho lời phê (việc cần làm) và số đếm cần xử lý |
| `--gs-bg` / `--gs-surface` | #EEF2F9 / #FFF | Nền giấy / trang giấy |
| `--gs-text` / `--gs-text-muted` | #16213B / #45557D | Chữ chính / phụ (đều ≥ 7:1) |
| `--gs-tag` | #8AA0D0 | Viền kép của nhãn vở |

## Thành phần
- **Nhãn bìa** (`.nhan-bia`): đầu menu, ghi SỔ QUẢN TRỊ, SỔ TUYỂN SINH hoặc SỔ GIA SƯ, kèm tên người dùng.
- **Nhãn vở** (`.nhan-vo`): định danh hồ sơ gồm mã · tên · lớp · môn, viền kép 3px.
- **Lời phê** (`.loi-phe`): chữ mực đỏ kèm biểu tượng bút. `.loi-phe.yen` (chữ xám) dùng khi chưa cần làm gì. Không dùng viền màu bên trái.
- **Nhãn trạng thái** (`.nhan-tt.tone-*`): phân biệt bằng nét kẻ cộng chữ.
  - Nét liền: đang chạy hoặc đã xong.
  - Nét đứt: đang chờ.
  - Gạch ngang: lỗi hoặc đã đóng.
- **Hàng việc** (`.nhom`, `.nhom-dau`, `.dong-viec`): dùng ở trang chủ của cả 3 vai trò.
  - Số đếm nằm ở tiêu đề nhóm. Nhóm gấp (`.gap`) có số đếm lớn hơn một bậc và bằng mực đỏ.
  - Mỗi dòng có 4 phần: nhãn vở · tình trạng · lời phê · 1 hành động.
- **Hộp xác nhận**: thêm `data-xac-nhan="..."` (và `data-nut="..."`) vào `<form>` hoặc nút submit. Không dùng `confirm()`. Nút được focus sẵn là "Quay lại".
- **Form** (`partials/form_fields.html`):
  - tóm tắt lỗi ở đầu form, tự nhận focus, có link tới từng ô sai;
  - lỗi hiện ngay dưới ô, nối với ô bằng `aria-describedby`, kèm `aria-invalid`.

## Quy tắc
- Lưới 8px. Khoảng cách phía trên tiêu đề lớn hơn phía dưới.
- Mỗi trang chỉ có 1 nút chính. Không đặt dòng chữ nhỏ (kicker) phía trên tiêu đề.
- Không dùng card số liệu làm khung trang, chữ gradient, hiệu ứng kính hay emoji (biểu tượng lấy từ bootstrap-icons).
- Chỉ có 1 chuyển động: các nhóm việc hiện dần khi mở trang. Chuyển động tắt khi người dùng bật `prefers-reduced-motion`.
- Chữ trong giao diện không chứa mã nội bộ (PB-xx) hay lộ trình kiểu "Phần N".
- Tiêu đề tab trình duyệt có dạng `<Trang> · <Tên hệ thống>`.
- Sửa CSS thì tăng `PHIEN_BAN_CSS` trong `core/context_processors.py`.
