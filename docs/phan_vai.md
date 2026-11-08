# Phân vai NV tuyển sinh / Admin / Hệ thống

Tài liệu này là căn cứ cho Phần 5–6 và cho hồ sơ dự án (RTM, demo).

Hệ thống của trung tâm FUNiX tách việc thành 3 nhóm: Hannix (tư vấn tuyển sinh), Hannah và vận hành (học vụ, xử lý ngoại lệ), và hệ thống tự động. MVP của nhóm chỉ có 3 vai trò nên gộp lại như sau:

- **NV tuyển sinh là người chăm khách.** NVTS lo một lớp từ lúc tiếp nhận yêu cầu đến khi kết thúc khóa. Mọi việc liên quan đến phụ huynh đều qua NVTS, kể cả việc đổi gia sư.
- **Admin là người giữ luật.** Admin không làm việc hằng ngày của NVTS. Admin chỉ làm những việc sau:
  - quản lý dữ liệu nền: tài khoản, duyệt môn cho gia sư;
  - xử lý ngoại lệ;
  - sửa dữ liệu đã khóa;
  - chốt thù lao tháng.

  **Mọi thao tác của Admin đều bắt buộc ghi lý do và được lưu vào nhật ký.**
- **Hệ thống** làm phần tự động: đề xuất gia sư, Zoom, Zalo, đếm hạn, tự hủy buổi, hậu kiểm, tính thù lao.

## Ai làm gì trong từng bước

| Bước | NV tuyển sinh | Admin | Hệ thống |
|---|---|---|---|
| 1. Tiếp nhận yêu cầu | Nhập yêu cầu: học viên, môn, mục tiêu, lịch | Sửa yêu cầu đã khóa (bắt buộc lý do) | Chuẩn hóa SĐT Zalo |
| 2. Tìm ghép gia sư | Chọn gia sư từ danh sách đề xuất, gửi lời mời, mời thêm | Xem các yêu cầu chờ quá 24h; **gán thẳng** gia sư ("Vận hành chốt") | Đề xuất gia sư theo quy tắc, lời mời hết hạn sau 24h, người nhận hợp lệ đầu tiên được lớp |
| 3. Học thử | Gọi phụ huynh, ghi kết quả học thử | — | Gia sư tạo buổi học thử, có phòng Zoom |
| 4. Mở khóa | Tạo khóa: số buổi, học phí, thù lao | **Sửa số buổi** khi nhập nhầm | Theo dõi số buổi còn lại và số buổi còn xếp được |
| 5. Buổi học | Theo dõi khóa sắp hết buổi để gọi phụ huynh gia hạn | Trang **Cần xem xét**: công nhận hoặc không công nhận buổi không đạt hậu kiểm; **mở lại** buổi bị tự hủy (trong 7 ngày) | Tạo Zoom, gửi Zalo, tự hủy buổi quá 12h chưa xác nhận, nhắc trước hạn 3h, hậu kiểm Zoom |
| 6. Đổi gia sư | Thực hiện: chọn lý do, mời gia sư mới | Duyệt khi khóa đổi gia sư **từ lần thứ 2** | Hủy các buổi sắp tới của gia sư cũ, giữ nguyên số buổi còn lại cho gia sư mới |
| 7. Thù lao tháng | **Kiểm tra** từng gia sư, thêm khoản điều chỉnh | **Chốt tháng**. Người chốt phải khác người kiểm tra | Tự cộng thù lao từ các buổi hoàn tất; tạm giữ thù lao của buổi đang xem xét |
| 8. Tổng quan | Trang "Việc cần làm hôm nay" | Dashboard ngoại lệ trên trang chủ | — |

## Điểm khác so với file "Prompt CAP 2"

| Mục trong Prompt | Hệ thống | Lý do |
|---|---|---|
| 3.1 Admin quản lý tài khoản **học viên** | Bỏ. Admin chỉ quản lý tài khoản NVTS và gia sư | Phạm vi đã chốt: phụ huynh và học viên không có tài khoản |
| 3.3 Quá 12h thì "chưa hoàn tất", Admin mở lại | Quá 12h hệ thống **tự hủy** buổi. Admin mở lại được trong 7 ngày, kèm lý do. Gia sư có thêm 24h để xác nhận | Có hạn mở lại rõ ràng nên tháng đối soát không bị kéo dài |
| 3.5 Admin làm toàn bộ việc đổi gia sư | NVTS làm, Admin giám sát; từ lần thứ 2 thì cần Admin duyệt | NVTS là người nói chuyện với phụ huynh. Admin vẫn kiểm soát những khóa phải đổi nhiều lần |
| 3.6 Dashboard có "tổng số" | Dashboard đưa **việc cần xử lý** lên đầu, tổng số chỉ là dòng phụ | Đúng nguyên tắc "việc cần làm trước, số liệu sau" |

## Zoom ở bản MVP
- Dùng 1 tài khoản Zoom và 1 app Server-to-Server OAuth (hướng dẫn trong `README_DEMO.md`). Tối đa 1 buổi học tại một thời điểm trên toàn trung tâm.
- FUNiX dùng nhóm nhiều tài khoản Zoom và "link lớp cố định". MVP chưa làm phần này. Hướng nâng cấp:
  1. thêm bảng tài khoản Zoom;
  2. khi tạo buổi, chọn tài khoản còn trống trong khung giờ;
  3. làm trang `/vao-lop/<mã>` tự chuyển tới phòng của buổi gần nhất.
