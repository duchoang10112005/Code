# 20 · Ma trận tình huống và kiểm thử

Dùng làm checklist khi Claude Code sửa code, và làm bằng chứng kiểm thử / UAT cho hồ sơ cuối kỳ. Cột **Test** ghi file test hiện có (giữ, sửa) hoặc file mới cần viết.

Test hiện có trong `Code/core/tests/`: `test_pb01_tai_khoan`, `test_pb02_pb06_yeu_cau`, `test_pb04_ho_so_gia_su`, `test_pb07_pb10_khoa_hoc`, `test_pb11_pb15_buoi_hoc`, `test_pb16_pb17_thu_lao`, `test_pb33_ngoai_le`, `test_rang_buoc_du_lieu`.
Test mới đề xuất: `test_hau_kiem`, `test_doi_gia_su_v2`, `test_dang_ky_mon_v2`, `test_tao_nhieu_buoi`, `test_vao_lop`, `test_su_co`, `test_api_json`, `test_phan_quyen_nguoi_phu_trach`.

## 1. Tài khoản & phân quyền

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| TK-01 | Đăng nhập đúng, mỗi vai trò | Về đúng trang chủ vai trò | 01 | pb01 (giữ) |
| TK-02 | Tài khoản bị khóa đăng nhập | Báo bị khóa kèm lý do | 01 | pb01 (sửa) |
| TK-03 | Bị khóa khi đang dùng | Request kế tiếp bị đăng xuất | 01 | pb01 (giữ) |
| TK-04 | Tài khoản mới có `phai_doi_mat_khau` | Mọi trang chuyển về đổi mật khẩu | 02 | pb01 (mới) |
| TK-05 | Khóa gia sư đang có lời mời chờ và lớp chưa mở khóa | Lời mời VOIDED, yêu cầu về DANG_TIM, buổi thử chưa học hủy | 03 | pb01 / pb33 |
| TK-06 | QTV tự khóa chính mình | Bị chặn | 03 | pb01 |
| TK-07 | Đăng ký qua link mời hết hạn | Báo link không hiệu lực | 04 | mới |
| TK-08 | Đăng ký qua link hợp lệ | Hồ sơ CHO_DUYET, `nguoi_moi` = Tuyển sinh tạo link | 04 | mới |
| TK-09 | Gia sư mở URL của Tuyển sinh/QTV | 403 | – | pb01 (giữ) |
| TK-10 | Gia sư gọi API lấy chi tiết học viên | Không có SĐT phụ huynh, học phí | 03 §5 | test_api_json |

## 2. Yêu cầu & lời mời

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| YC-01 | Tạo yêu cầu thiếu khung giờ | Lỗi "chọn ít nhất 1 ô" | 05 | pb02 (sửa) |
| YC-02 | SĐT `+84 912 345 678` | Lưu `84912345678` | 05 | pb02 (giữ) |
| YC-03 | Đề xuất: gia sư tạm nghỉ | Hiện cờ "Tạm nghỉ", không tick được | 06 | pb02 (mới) |
| YC-04 | Điểm khớp: đúng môn, cấp độ, trùng 3/3, còn chỗ | 100 | 06 | pb02 (mới) |
| YC-05 | Hai Tuyển sinh gửi lời mời cùng gia sư cùng lúc | Chỉ 1 lời mời CHO | 07 | pb02 (giữ) |
| YC-06 | Hai gia sư Accept cùng lúc | 1 người DA_PHAN_CONG, người kia VOIDED + thông báo "người khác đã nhận" | 08 | pb02 (giữ) |
| YC-07 | Accept khi lời mời đã hết hạn | "Lời mời không còn hiệu lực" | 08 | pb02 (giữ) |
| YC-08 | Accept không tick cam kết | Lỗi form | 08 | pb02 (mới) |
| YC-09 | Từ chối không chọn lý do | Lỗi form | 08 | pb02 (mới) |
| YC-10 | Đóng yêu cầu đã có gia sư | Bị chặn | 09 | pb02 (giữ) |
| YC-11 | Đóng rồi Hoàn tác trong 6 giây | Không có request, dữ liệu không đổi | 09 | kiểm thử tay (UAT) |

## 3. Học thử & mở khóa

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| KH-01 | Đăng ký thẳng khi đã có buổi thử | Bị chặn | 10 | pb07 (mới) |
| KH-02 | Đăng ký thẳng xong, gia sư tạo buổi thử | Bị chặn | 10/13 | pb07 (mới) |
| KH-03 | Ghi kết quả khi chưa có buổi thử hoàn tất | Bị chặn | 11 | pb07 (giữ) |
| KH-04 | DONG_Y | HOC_THU_XONG, mở khóa được | 11 | pb07 (sửa giá trị) |
| KH-05 | CAN_THEM_THOI_GIAN | Giữ DA_PHAN_CONG, tạo NhacViec +2 ngày, ghi lại được lần nữa | 11 | pb07 (mới) |
| KH-06 | TIM_GIA_SU_KHAC | DANG_TIM, gỡ gia sư, hủy buổi thử chưa học, xóa Zoom | 11 | pb07 (giữ) |
| KH-07 | KHONG_DANG_KY thiếu ghi chú | Bị chặn | 11 | pb07 (sửa) |
| KH-08 | Mở khóa 2 lần | "Yêu cầu này đã có khóa học." | 12 | pb07 (giữ) |
| KH-09 | Thù lao > học phí | Lỗi form + CheckConstraint | 12 | rang_buoc (giữ) |
| KH-10 | Mở khóa sinh `ma_lop` | `ma_lop = KH-xxxx`, unique | 12 | pb07 (mới) |

## 4. Buổi học

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| BH-01 | Tạo 3 buổi lặp tuần, hợp lệ | 3 buổi DA_LEN_LICH, mã liên tiếp, nhãn "Buổi 6/16, 7/16, 8/16" | 13 | test_tao_nhieu_buoi |
| BH-02 | Một buổi trùng giờ buổi của chính gia sư | Chặn buổi đó, các buổi khác vẫn tạo | 13 | test_tao_nhieu_buoi |
| BH-03 | Số buổi giao nhau ≥ số host Zoom | Chặn "Khung giờ này đã có buổi khác dùng phòng Zoom" | 13 | pb11 (giữ) |
| BH-04 | Kết thúc sau 22:00 | Tạo được (đã bỏ giới hạn giờ kết thúc) | 13 | test_BH04 |
| BH-05 | Ngoài giờ rảnh | Tạo được, có cảnh báo | 13 | mới |
| BH-06 | Vượt số buổi còn xếp được | Chặn (trừ học bù / dời lịch) | 13 | pb11 (giữ) |
| BH-07 | Zoom lỗi khi tạo | LOI_ZOOM, thử lại OK → DA_LEN_LICH | 13 | pb11 (giữ) |
| BH-08 | LOI_ZOOM tới giờ học | Tự hủy LOI_ZOOM + email | 36 | pb11 (giữ) |
| BH-09 | Học bù cho buổi đã bù rồi | Chặn (OneToOne) | 13 | mới |
| BH-10 | Tin nhắn Zalo lớp | Có link cố định, Meeting ID, passcode; **không** có host key | 13 | test_vao_lop |
| BH-11 | `/lop/<ma>` trước giờ 15′ | Trang chờ | 14 | test_vao_lop |
| BH-12 | `/lop/<ma>` trước giờ 5′ | 302 tới join_url | 14 | test_vao_lop |
| BH-13 | Gia sư mở phòng sớm hơn 10′ | Báo giờ mở | 14 | test_vao_lop |
| BH-14 | Tự lưu nháp rồi tải lại trang | Phiếu nạp lại đúng | 15 | test_api_json |
| BH-15 | Xác nhận trước giờ kết thúc | Bị chặn | 16 | pb11 (giữ) |
| BH-16 | Xác nhận bấm 2 lần | Lần 2 báo đã thay đổi; số buổi +1 đúng 1 lần; 1 ThuLao | 16 | pb11 (giữ) |
| BH-17 | Nhận xét < 30 ký tự | Lỗi form | 16 | pb11 (mới) |
| BH-18 | Xác nhận buổi cuối | Khóa HOAN_THANH | 16 | pb11 (giữ) |
| BH-19 | Zalo lỗi khi xác nhận | Buổi vẫn HOAN_TAT, zalo LOI, NhatKyGuiTin thất bại | 16 | pb11 (giữ) |
| BH-20 | Tắt gửi Zalo | zalo CHUA_GUI, không gọi ZNS | 16 | mới |
| BH-21 | Xác nhận khi tháng đã chốt | ThuLao ghi tháng kế tiếp | 16 | pb16 (giữ) |
| BH-22 | Hủy buổi đã bắt đầu | Bị chặn | 17 | pb11 (giữ) |
| BH-23 | Dời lịch sang giờ trùng | Buổi cũ giữ nguyên, phòng Zoom cũ còn | 18 | pb11 (giữ) |
| BH-24 | Quá hạn 12h | Tự hủy QUA_HAN, email | 36 | pb11 (giữ) |
| BH-25 | Còn 3h tới hạn | Nhắc đúng 1 lần (`da_nhac_han`) | 36 | pb11 (giữ) |
| BH-26 | Xin mở lại buổi chưa tự hủy | Bị chặn | 19 | test_su_co |
| BH-27 | Xin mở lại lần 2 khi đang chờ | Bị chặn | 19 | test_su_co |

## 5. Hậu kiểm

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| HK-01 | Xác nhận xong | Tạo HauKiemBuoi CHUA_KIEM_TRA, `nguoi_phu_trach` = người mời gia sư | 16 | test_hau_kiem |
| HK-02 | Zoom chưa tổng hợp (404) | Bỏ qua, lượt sau thử lại | 20 | test_hau_kiem |
| HK-03 | Gói Zoom không có báo cáo | Tiêu chí 1–3 null, kiem_tra KHONG_DU_LIEU | 20 | pb11 (sửa) |
| HK-04 | Gia sư vào trễ 8′ | Tiêu chí 1 không đạt, `so_canh_bao` ≥ 1, **buổi vẫn HOAN_TAT, thù lao vẫn Tạm tính** | 20 | test_hau_kiem |
| HK-05 | Tuyển sinh không phải người mời kết luận | 403 | 21 | test_phan_quyen_nguoi_phu_trach |
| HK-06 | Gia sư chưa có người mời | Mọi Tuyển sinh kết luận được | 21 | test_phan_quyen_nguoi_phu_trach |
| HK-07 | QTV gọi API kết luận | 403 | 21 | test_phan_quyen_nguoi_phu_trach |
| HK-08 | Kết luận Có vấn đề thiếu lý do | Bị chặn | 21 | test_hau_kiem |
| HK-09 | Có vấn đề | Buổi DANG_XEM_XET, ThuLao TAM_GIU, email gia sư | 21 | test_hau_kiem |
| HK-10 | Duyệt hàng loạt 10 buổi, 2 có cảnh báo, chọn "chỉ buổi sạch" | 8 HOP_LE, 2 giữ nguyên | 21 | test_hau_kiem |
| HK-11 | Duyệt hàng loạt có id của người khác / đã kết luận | Bỏ qua, đếm vào "bỏ qua" | 21 | test_hau_kiem |
| HK-12 | Xử lý: vẫn tính | HOAN_TAT, TAM_TINH | 22 | pb33 (chuyển) |
| HK-13 | Xử lý: không tính, tháng chưa chốt | DA_HUY HAU_KIEM, ThuLao HUY, khóa -1 buổi | 22 | pb33 (chuyển) |
| HK-14 | Xử lý: không tính, tháng đã chốt | Tạo DieuChinhThuLao âm ở tháng mở kế tiếp | 22 | test_hau_kiem |
| HK-15 | Kiểm tra đối soát khi còn buổi Tạm giữ | Bị chặn | 30 | pb16 (giữ) |

## 6. Khóa học & đổi gia sư

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| KD-01 | Tạm dừng | Buổi tương lai hủy + xóa Zoom; buổi đã dạy chưa xác nhận giữ | 23 | pb07 (giữ) |
| KD-02 | Hoàn thành sớm | HOAN_THANH, hủy buổi tương lai | 23 | mới |
| KD-03 | Tiếp tục khi yêu cầu đang chờ gia sư mới | Bị chặn | 23 | pb07 (giữ) |
| KD-04 | Tuyển sinh gia hạn +12 | so_buoi_dang_ky +12, HOAN_THANH → DANG_HOC, GiaHanKhoa | 24 | mới |
| KD-05 | Tuyển sinh giảm số buổi | 403 / bị chặn | 24 | mới |
| KD-06 | QTV giảm dưới đã học + đang lên lịch | Bị chặn | 24 | pb33 (giữ) |
| KD-07 | Đổi gia sư lần 1 | Thực hiện ngay: buổi tương lai chuyển gia sư mới, thù lao mới; khóa vẫn DANG_HOC | 25 | test_doi_gia_su_v2 |
| KD-08 | Đổi gia sư lần 2 | CHO_DUYET, buổi vẫn của gia sư cũ tới khi duyệt | 25 | test_doi_gia_su_v2 |
| KD-09 | Buổi tương lai trùng lịch gia sư mới | Buổi đó hủy, xóa Zoom; buổi khác chuyển | 25 | test_doi_gia_su_v2 |
| KD-10 | Gia sư mới bị khóa trước khi QTV duyệt | Duyệt bị chặn | 25 | test_doi_gia_su_v2 |
| KD-11 | "Chưa có gia sư mới" | Chạy luồng cũ (TAM_DUNG, DANG_TIM, mời lại, `nhan_lai_khoa`) | 25 | pb33 (giữ) |

## 7. Hồ sơ & môn

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| HS-01 | Lưu lưới giờ rảnh | LichRanh đúng khung, unique (ho_so, thu, khung) | 26 | pb04 (sửa) |
| HS-02 | Đặt tạm nghỉ | Lời mời chờ VOIDED, không được đề xuất | 26 | pb04 (mới) |
| HS-03 | Đăng ký môn thiếu kết quả test | Bị chặn ở bước 2 | 27 | test_dang_ky_mon_v2 |
| HS-04 | Minh chứng link `http://` | Bị chặn (chỉ https) | 27 | test_dang_ky_mon_v2 |
| HS-05 | Tệp > 5MB / sai định dạng | Bị chặn | 27 | test_dang_ky_mon_v2 |
| HS-06 | Gửi lại môn bị từ chối | Cùng bản ghi về CHO_DUYET | 27 | pb04 (giữ) |
| HS-07 | Rút môn đã duyệt | Bị chặn | 27 | pb04 (giữ) |
| HS-08 | Rút môn chờ duyệt | DA_RUT (không xóa) | 27 | pb04 (sửa) |
| HS-09 | Thu hồi môn đã duyệt | Lời mời môn đó VOIDED, gỡ phân công lớp chưa mở khóa; hết môn → TAM_NGUNG | 28 | pb04 (giữ) |
| HS-10 | Kích hoạt hồ sơ chưa có môn duyệt | Bị chặn | 28 | pb04 (giữ) |

## 8. Thù lao

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| TL-01 | Điều chỉnh sau khi đã kiểm tra | Bản kiểm tra bị xóa, phải kiểm tra lại | 30 | pb16 (giữ) |
| TL-02 | Người kiểm tra tự chốt | Bị chặn | 31 | pb16 (giữ) |
| TL-03 | Chốt tháng khi một gia sư đổi số sau kiểm tra | Gia sư đó bị bỏ qua, các gia sư khác chốt | 31 | pb16 (mới) |
| TL-04 | Đánh dấu chi trả tháng chưa chốt | Bị chặn | 31 | pb16 (mới) |
| TL-05 | Điều chỉnh vào tháng đã chốt | Bị chặn, gợi ý tháng sau | 30 | pb16 (giữ) |

## 9. Quản trị & sự cố

| # | Tình huống | Kết quả mong đợi | SD | Test |
|---|---|---|---|---|
| QT-01 | Tìm `bh399` | Ra BH-00399 | 32 | test_su_co |
| QT-02 | Tìm mã không có trong hàng đợi | Thẻ "không có yêu cầu xử lý" + link | 32 | test_su_co |
| QT-03 | Mở lại buổi > 7 ngày | Bị chặn | 33 | pb33 (giữ) |
| QT-04 | Mở lại khi khóa hết chỗ | Bị chặn, nêu số liệu | 33 | pb33 (giữ) |
| QT-05 | Mở lại thiếu lý do | Bị chặn | 33 | pb33 (giữ) |
| QT-06 | Lỗi 500 khi xác nhận | SuCoHeThong + YeuCauXuLy, hạn xác nhận +24h | 34 | test_su_co |
| QT-07 | Khôi phục từ bản nháp đủ mục | Buổi HOAN_TAT, nhật ký ghi QTV thay gia sư | 34 | test_su_co |
| QT-08 | Khôi phục khi nháp thiếu | Chuyển sang mở lại | 34 | test_su_co |
| QT-09 | Tạo lại Zoom bằng host khác | Phòng mới, host mới, thông báo gia sư | 34 | test_su_co |
| QT-10 | Mọi thao tác QTV | Có dòng NhatKy kèm lý do | – | pb33 (giữ) |

## 10. Kịch bản demo end-to-end (bảo vệ cuối kỳ)

1. Tuyển sinh tạo link mời → gia sư đăng ký → đăng ký môn (bài test + minh chứng) → QTV duyệt môn và kích hoạt (SD-04, 27, 28).
2. Tuyển sinh tạo yêu cầu → đề xuất có điểm khớp → mời 2 gia sư → gia sư A nhận, B thấy "vô hiệu" (SD-05…08).
3. Gia sư tạo buổi học thử → phòng Zoom + tin nhắn Zalo → xác nhận hoàn tất → Tuyển sinh ghi "Đồng ý" → mở khóa (SD-13, 16, 11, 12).
4. Gia sư tạo 3 buổi lặp tuần → vào lớp qua link cố định → xác nhận → phụ huynh nhận ZNS (SD-13, 14, 16).
5. Để một buổi quá hạn (chế độ demo 1 phút) → tự hủy → gia sư xin mở lại → QTV mở lại → gia sư xác nhận (SD-36, 19, 33).
6. Hậu kiểm: duyệt nhanh hàng loạt, đánh dấu 1 buổi có vấn đề → xử lý không tính (SD-21, 22).
7. Tuyển sinh kiểm tra thù lao → QTV chốt → đánh dấu chi trả (SD-30, 31).
8. Đổi gia sư lần 2 → QTV duyệt ở Cần xem xét (SD-25).
