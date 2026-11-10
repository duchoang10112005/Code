# Thiết kế luồng hệ thống – Gia Sư Online (UI mới × backend Django cũ)

Bộ tài liệu này nối **bộ UI mới** (thư mục `GiaSuOnline-UI/pages/*.dc.html`) với **mã nguồn Django hiện có** (thư mục `Code/`). Mục đích: để Claude Code (hoặc thành viên nhóm) đọc xong là biết **mỗi màn hình gọi URL nào, view nào, service nào, ghi bảng nào, gọi dịch vụ ngoài nào, và xử lý tình huống lỗi ra sao**, rồi sửa backend + database cho khớp UI mới.

> Phiên bản: 10/11/2026 · Căn cứ: `Code/core/models.py`, `core/services/*.py`, `core/views/*.py`, `core/urls.py`, `core/integrations/*.py`, `config/settings.py`, `docs/phan_vai.md`, `Sprint2_DFD/DFD_MoTa.md` và 26 màn hình UI mới.

## Đọc theo thứ tự

| File | Nội dung | Khi nào đọc |
|---|---|---|
| `01_Kien-truc-va-quy-uoc.md` | Kiến trúc tầng (UI → View/API → Service → Model → Dịch vụ ngoài), quy ước code bắt buộc giữ (cập nhật có điều kiện, transaction, nhật ký, email không làm hỏng nghiệp vụ), ký hiệu dùng trong sơ đồ | Đọc đầu tiên |
| `02_Thay-doi-Database.md` | Bảng/trường **thêm mới**, **đổi**, **giữ nguyên**; ERD; đổi nhãn trạng thái; thứ tự migration | Trước khi viết migration |
| `03_URL-API-theo-man-hinh.md` | Mỗi màn hình UI ↔ URL ↔ view ↔ service; danh sách **API JSON mới** cho phần tương tác (drawer, Ctrl+K, tick hàng loạt, tự lưu nháp…) | Khi làm từng màn hình |
| `10_SD_Tai-khoan.md` | SD-01…SD-04: đăng nhập theo vai trò, đổi mật khẩu bắt buộc, tạo/khóa tài khoản, gia sư đăng ký qua link mời | |
| `11_SD_Yeu-cau-Loi-moi.md` | SD-05…SD-09: tạo yêu cầu + học viên, đề xuất gia sư có điểm khớp, gửi lời mời, gia sư nhận/từ chối (người nhận hợp lệ đầu tiên thắng), đóng yêu cầu + hoàn tác | |
| `12_SD_Hoc-thu-Mo-khoa.md` | SD-10…SD-12: đăng ký thẳng (nhánh A), ghi kết quả học thử (4 kết quả, có nhắc gọi lại), mở khóa học | |
| `13_SD_Buoi-hoc.md` | SD-13…SD-19: tạo nhiều buổi + Zoom + link lớp cố định + tin nhắn Zalo, vào lớp (mở trước 10′, đóng sau 5′), tự lưu nháp đánh giá, xác nhận hoàn tất → số buổi + thù lao + ZNS, báo hủy, dời lịch/học bù, xin mở lại | |
| `14_SD_Hau-kiem.md` | SD-20…SD-22: hệ thống thu thập dữ liệu Zoom và chấm 5 tiêu chí, Tuyển sinh hậu kiểm từng buổi, duyệt nhanh hàng loạt, xử lý buổi có vấn đề | |
| `15_SD_Khoa-hoc-Doi-gia-su.md` | SD-23…SD-25: đổi trạng thái khóa, gia hạn / sửa số buổi, đổi gia sư (chọn sẵn gia sư mới, Admin duyệt từ lần 2) | |
| `16_SD_Ho-so-Gia-su.md` | SD-26…SD-28: cập nhật hồ sơ & giờ rảnh, đăng ký môn 4 bước (bài test + nhiều minh chứng), Admin duyệt hồ sơ/môn | |
| `17_SD_Thu-lao.md` | SD-29…SD-31: thu nhập gia sư, Tuyển sinh kiểm tra + điều chỉnh, Admin chốt và đánh dấu chi trả | |
| `18_SD_Quan-tri-Ngoai-le.md` | SD-32…SD-35: trang Cần xem xét (tìm theo mã buổi), mở lại buổi tự hủy, lỗi hệ thống (khôi phục từ bản nháp), lỗi Zoom, nhật ký thao tác, Ctrl+K | |
| `19_SD_Tac-vu-dinh-ky.md` | SD-36: lệnh `quet_dinh_ky` (mỗi 5–15 phút): nhắc hạn, tự hủy, hết hạn lời mời, mở/đóng phòng Zoom, hậu kiểm, nhắc gọi lại, hết hạn bản ghi | |
| `20_Ma-tran-tinh-huong.md` | Bảng tình huống → kết quả mong đợi → test cần viết (dùng làm checklist kiểm thử, UAT) | Khi viết test |

## Ký hiệu nhanh

- **SD-xx**: mã sơ đồ tuần tự (sequence diagram). Mỗi SD có: màn hình UI, tác nhân, điều kiện trước, sơ đồ Mermaid, bảng dữ liệu ghi, tình huống ngoại lệ.
- **[CŨ]** = đã có trong `Code/`, giữ nguyên hoặc chỉ đổi nhãn. **[SỬA]** = có trong code nhưng phải sửa. **[MỚI]** = phải viết mới.
- Tên bảng dùng tên model Django (`BuoiHoc`, `LoiMoi`…). Tên hàm service ghi đúng như trong `core/services/`.
- Sơ đồ viết bằng **Mermaid** (`sequenceDiagram`, `erDiagram`, `stateDiagram-v2`). Mở bằng VS Code (extension Markdown Preview Mermaid), GitHub, hoặc dán vào https://mermaid.live.

## Cách giao cho Claude Code

1. Chép cả thư mục này vào `Code/docs/thiet-ke-luong/` (hoặc để nguyên ở `D:\CAP 2\Thiet ke luong`).
2. Thêm vào `Code/CLAUDE.md` một dòng: *"Trước khi sửa backend cho UI mới, đọc `docs/thiet-ke-luong/README.md` rồi file tương ứng. Mọi trạng thái, quy tắc và tình huống phải khớp các SD-xx."*
3. Giao việc theo từng đợt, ví dụ: *"Làm Đợt 1 trong `02_Thay-doi-Database.md` mục 7: viết migration, sửa model, chạy lại toàn bộ test."* → *"Làm SD-13 và SD-15: tạo nhiều buổi và xác nhận hoàn tất theo sơ đồ."*
4. Mỗi đợt xong: chạy `python manage.py test core`, đối chiếu với `20_Ma-tran-tinh-huong.md`.

## Những quyết định cần nhóm chốt

Các điểm dưới đây UI mới và code cũ khác nhau, tài liệu đã chọn một phương án (ghi rõ lý do trong file tương ứng). Nhóm đọc và đổi nếu không đồng ý:

| # | Vấn đề | Phương án trong tài liệu |
|---|---|---|
| Q1 | Hậu kiểm: code cũ để hệ thống tự đưa buổi vào "Đang xem xét" và Admin xử lý; UI mới giao **Tuyển sinh** hậu kiểm gia sư mình mời | Hệ thống chỉ **chấm tiêu chí** và gắn cờ; Tuyển sinh phụ trách kết luận. Admin chỉ nhận buổi mở lại / lỗi hệ thống (SD-20…22) |
| Q2 | Đổi gia sư: code cũ hủy buổi tương lai rồi mời lại từ đầu; UI mới chọn sẵn gia sư mới và **chuyển các buổi đã xếp** sang người mới | Theo UI mới: NVTS chọn gia sư mới đã đồng ý, chuyển buổi khi thực hiện; lần ≥2 cần Admin duyệt (SD-25) |
| Q3 | Kết quả học thử: code cũ có Tiếp tục / Tìm gia sư khác / Dừng; UI mới có Đồng ý đăng ký / Không đăng ký / Cần thêm thời gian | Gộp 4 giá trị: `DONG_Y`, `KHONG_DANG_KY`, `CAN_THEM_THOI_GIAN` (tạo nhắc gọi lại sau 2 ngày), `TIM_GIA_SU_KHAC` (giữ lại vì vẫn cần) (SD-11) |
| Q4 | Buổi học "Chờ xác nhận" và "Tự hủy": code cũ suy ra, ghi chú cũ đề xuất thêm trạng thái thật | **Không thêm trạng thái DB**, giữ suy ra bằng thuộc tính + nhãn hiển thị (ít rủi ro migration, test cũ vẫn chạy). Lý do ở `02` mục 4 |
| Q5 | Zoom: 1 tài khoản, tối đa 1 buổi cùng lúc; UI có host key, link lớp cố định | Thêm bảng `TaiKhoanZoom` (nhiều host, có host key) + `KhoaHoc.ma_lop`; tham số `SO_PHONG_ZOOM_DONG_THOI` = số host đang bật. Chạy được với 1 host như cũ |
| Q6 | Mở lại buổi tự hủy: trang Chi tiết buổi học v2 ghi "Khi **Tuyển sinh** mở lại buổi", còn trang Cần xem xét và yêu cầu của nhóm giao **Admin** | Theo yêu cầu: **Admin** mở lại; sửa câu chữ trên trang Chi tiết buổi học v2 |
| Q7 | "Đánh giá PH 4,9" trên trang Gia sư: phụ huynh không có tài khoản | Thêm bảng `PhanHoiPhuHuynh` do Tuyển sinh nhập sau cuộc gọi / phản ánh Zalo; điểm trung bình tính từ bảng này. Có thể bỏ ô này nếu không làm |
