# 03 · URL, View, API theo từng màn hình

Cột **URL** giữ URL cũ (`core/urls.py`) nếu đã có. **[MỚI]** = thêm. API JSON đặt trong `core/api/` (file theo nhóm), đăng ký dưới tiền tố `/api/`.

## 1. Chung

| Màn hình UI | URL | View / API | Service | SD |
|---|---|---|---|---|
| `Dang nhap.dc.html` | `/dang-nhap/` | `chung.DangNhapView` [SỬA: chuyển hướng `/doi-mat-khau/` nếu `phai_doi_mat_khau`] | – | SD-01 |
| (đổi mật khẩu) | `/doi-mat-khau/` | `chung.DoiMatKhauView` [SỬA: tắt cờ sau khi đổi] | – | SD-02 |
| Trang chủ (theo vai trò) | `/` | `chung.trang_chu` [SỬA: tách 3 hàm `trang_chu_gia_su/ tuyen_sinh/ admin` + context mới] | `quet_han`, `quet_loi_moi_het_han` | |
| Chuông thông báo | `GET /api/thong-bao/` · `POST /api/thong-bao/da-doc/` [MỚI] | `api.chung` | `thong_bao.ds_chua_doc`, `danh_dau_da_doc` | |
| Bảng lệnh Ctrl+K | `GET /api/tim-kiem/?q=` [MỚI] | `api.chung.tim_kiem` | `tim_kiem.tim(user, q)` [MỚI] | SD-35 |
| Đăng ký gia sư qua link | `/dang-ky-gia-su/<ma>/` [MỚI] | `gia_su.dang_ky_qua_ma` | `gia_su.dang_ky_tai_khoan` [MỚI] | SD-04 |

## 2. Gia sư

| Màn hình UI | URL | View / API | Service | SD |
|---|---|---|---|---|
| `Trang chu Gia su v2` | `/` | `trang_chu_gia_su` | thống kê tháng, `khoa_co_the_xep` | |
| `Gia su - Loi moi nhan lop` | `/loi-moi/` | `yeu_cau.loi_moi_cua_toi` [SỬA: thêm chi tiết khớp giờ, đếm ngược] | `quet_loi_moi_het_han` | SD-08 |
| ↳ Nhận lớp | `POST /loi-moi/<pk>/nhan/` (+ `/api/loi-moi/<pk>/nhan/`) | `yeu_cau.nhan_lop` [SỬA: bắt buộc `cam_ket`, nhận `ghi_chu_gia_su`] | `yeu_cau.chap_nhan` | SD-08 |
| ↳ Từ chối | `POST /loi-moi/<pk>/tu-choi/` | `yeu_cau.tu_choi_loi_moi` [SỬA: lý do bắt buộc từ danh mục] | `yeu_cau.tu_choi` | SD-08 |
| Lớp của tôi | `/lop-cua-toi/`, `/lop-cua-toi/khoa/<pk>/` | giữ | | |
| `Gia su - Tao buoi hoc v2` | `/buoi-hoc/tao/` | `buoi_hoc.tao` [SỬA: nhiều buổi, học bù] | `buoi_hoc.tao_nhieu_buoi` [MỚI] → `tao_buoi_chinh_thuc` / `tao_buoi_hoc_thu` | SD-13 |
| ↳ Kiểm tra trước khi tạo | `POST /api/buoi-hoc/kiem-tra-lich/` [MỚI] | trả từng buổi: OK / trùng / quá 22:00 / ngoài giờ rảnh (cảnh báo) | `buoi_hoc.kiem_tra_ke_hoach` [MỚI] | SD-13 |
| ↳ Thử lại Zoom | `POST /buoi-hoc/<pk>/thu-lai-zoom/` | giữ | `thu_lai_zoom` | SD-13 |
| ↳ Sao chép tin nhắn Zalo | `GET /api/buoi-hoc/<pk>/tin-nhan-lop/` [MỚI] | | `buoi_hoc.noi_dung_moi_vao_lop` [MỚI] | SD-13 |
| `Gia su - Chi tiet buoi hoc v2` | `/buoi-hoc/<pk>/` | `buoi_hoc.chi_tiet` [SỬA] | | SD-15 |
| ↳ Mở phòng Zoom (host) | `/buoi-hoc/<pk>/mo-phong/` | giữ (+ kiểm tra cửa sổ 10′) | `lay_link_mo_phong` | SD-14 |
| ↳ Tự lưu nháp | `POST /api/buoi-hoc/<pk>/nhap/` [MỚI] (mỗi 10 giây khi gõ) | | `buoi_hoc.luu_nhap` | SD-15 |
| ↳ Xác nhận hoàn tất | `POST /buoi-hoc/<pk>/xac-nhan/` | `buoi_hoc.xac_nhan` [SỬA form] | `xac_nhan_hoan_tat(gia_su, buoi, du_lieu, bo_qua_han=False, nguoi_thuc_hien=None)` [SỬA – 2 tham số mới cho QTV khôi phục, SD-34] | SD-16 |
| ↳ Gửi lại Zalo | `POST /api/buoi-hoc/<pk>/gui-lai-zalo/` [MỚI] | | `gui_zalo_danh_gia` | SD-16 |
| ↳ Báo hủy | `POST /buoi-hoc/<pk>/huy/` | giữ | `huy_buoi` | SD-17 |
| ↳ Dời lịch | `POST /buoi-hoc/<pk>/doi-lich/` | giữ | `doi_lich` | SD-18 |
| ↳ Xin mở lại (buổi tự hủy) | `POST /buoi-hoc/<pk>/xin-mo-lai/` [MỚI] | | `ngoai_le.gui_yeu_cau_xu_ly(MO_LAI)` | SD-19 |
| ↳ Báo sự cố | `POST /buoi-hoc/<pk>/bao-su-co/` [MỚI] | | `gui_yeu_cau_xu_ly(LOI_HE_THONG/SU_CO_ZOOM)` | SD-34 |
| Link lớp cố định (phụ huynh/học viên) | `/lop/<ma_lop>/` [MỚI, không cần đăng nhập] | `buoi_hoc.vao_lop` | `buoi_hoc.buoi_dang_mo(ma_lop)` | SD-14 |
| `Gia su - Thu nhap` | `/thu-nhap/` | `thu_lao.thu_nhap` [SỬA: theo tháng, trạng thái từng buổi] | `thu_lao.tong_hop` | SD-29 |
| `Gia su - Ho so cua toi` | `/ho-so/` | `gia_su.ho_so_cua_toi` | | SD-26 |
| ↳ Lưu thông tin | `POST /ho-so/cap-nhat/` | giữ | | SD-26 |
| ↳ Lưới giờ rảnh | `POST /api/ho-so/gio-ranh/` [MỚI – thay `lich/them`, `lich/xoa` bằng gửi cả lưới] | | `gia_su.dat_luoi_gio_ranh` [MỚI] | SD-26 |
| ↳ Đăng ký môn (4 bước) | `POST /ho-so/mon/dang-ky/` [SỬA: multipart, nhiều minh chứng] | | `gia_su.dang_ky_mon` [SỬA] | SD-27 |
| ↳ Rút môn / Gửi lại | `POST /ho-so/mon/<pk>/rut/`, `/ho-so/mon/<pk>/gui-lai/` [MỚI] | | `rut_mon` [SỬA], `gui_lai_mon` [MỚI] | SD-27 |

## 3. Tuyển sinh

| Màn hình UI | URL | View / API | Service | SD |
|---|---|---|---|---|
| `Trang chu Tuyen sinh` | `/` | `trang_chu_tuyen_sinh` [SỬA: nhóm việc theo mức gấp, % yêu cầu có gia sư, lịch hạn] | | |
| ↳ Ghi kết quả học thử (drawer) | `POST /api/yeu-cau/<pk>/ket-qua-hoc-thu/` | | `khoa_hoc.ghi_ket_qua_hoc_thu` [SỬA] | SD-11 |
| `Tuyen sinh - Yeu cau hoc tap` | `/yeu-cau/` | `yeu_cau.danh_sach` [SỬA: tab trạng thái + đếm, cột "Bước tiếp theo"] | | |
| ↳ Đóng yêu cầu (+ Hoàn tác) | `POST /yeu-cau/<pk>/dong/` | | `dong_yeu_cau` | SD-09 |
| `Tuyen sinh - Tao yeu cau` | `/yeu-cau/tao/` | `yeu_cau.tao` [SỬA: lưới khung giờ, preview] | `tao_yeu_cau` | SD-05 |
| ↳ Tìm học viên đã có | `GET /api/hoc-vien/?q=` [MỚI] | | | SD-05 |
| ↳ Đếm gia sư phù hợp (preview) | `GET /api/yeu-cau/dem-gia-su/?mon=&cap_do=&khung=` [MỚI] | | `de_xuat_gia_su` (chỉ đếm) | SD-05 |
| `Tuyen sinh - Chi tiet yeu cau` | `/yeu-cau/<pk>/` | `yeu_cau.chi_tiet` [SỬA: điểm khớp, dòng thời gian] | `de_xuat_gia_su` [SỬA: điểm 0–100] | SD-06 |
| ↳ Gửi / mời thêm | `POST /yeu-cau/<pk>/gui-loi-moi/` | giữ | `gui_loi_moi` [SỬA lưu điểm khớp] | SD-07 |
| ↳ Đăng ký chính thức luôn | `POST /yeu-cau/<pk>/dang-ky-thang/` [MỚI] | | `khoa_hoc.danh_dau_dang_ky_thang` | SD-10 |
| ↳ Mở khóa học | `POST /yeu-cau/<pk>/tao-khoa/` | giữ (+ lịch cố định, nhóm Zalo) | `tao_khoa_hoc` [SỬA] | SD-12 |
| ↳ Sửa yêu cầu | `/yeu-cau/<pk>/sua/` | giữ | | |
| `Tuyen sinh - Hoc vien` | `/hoc-vien/` | `yeu_cau.hoc_vien_danh_sach` [SỬA: tab tình trạng, "Tôi phụ trách"] | | |
| ↳ Khung chi tiết bên phải | `GET /api/hoc-vien/<pk>/` [MỚI] | | khóa, yêu cầu, 3 buổi gần nhất | |
| `Tuyen sinh - Gia su` | `/gia-su/` | `gia_su.danh_sach` [SỬA: tình trạng Đang nhận lớp/Kín lịch/Tạm nghỉ/Chờ duyệt, "Tôi mời"] | | |
| ↳ Khung chi tiết | `GET /api/gia-su/<pk>/` [MỚI] | | môn đã duyệt, lưới giờ rảnh, lớp đang dạy, tỷ lệ đúng hạn | |
| ↳ Mời gia sư đăng ký | `POST /api/ma-moi/` [MỚI] | | `gia_su.tao_ma_moi` | SD-04 |
| `Tuyen sinh - Khoa hoc` | `/khoa-hoc/` | `khoa_hoc.danh_sach` [SỬA: tab, "Sắp hết buổi"] | | |
| `Tuyen sinh - Chi tiet khoa hoc` | `/khoa-hoc/<pk>/` | `khoa_hoc.chi_tiet` | | |
| ↳ Đổi trạng thái | `POST /khoa-hoc/<pk>/trang-thai/` | giữ (+ HOAN_THANH) | `doi_trang_thai_khoa` [SỬA] | SD-23 |
| ↳ Gia hạn / sửa số buổi | `POST /khoa-hoc/<pk>/sua-so-buoi/` | [SỬA quyền: TS gia hạn, QTV sửa nhập nhầm] | `khoa_hoc.gia_han` [MỚI], `ngoai_le.sua_so_buoi` | SD-24 |
| ↳ Đổi gia sư | `POST /khoa-hoc/<pk>/doi-gia-su/` | [SỬA form: chọn gia sư mới, thù lao mới] | `ngoai_le.de_nghi_doi_gia_su` [SỬA] | SD-25 |
| `Tuyen sinh - Hau kiem buoi hoc` | `/hau-kiem/` [MỚI] | `hau_kiem.danh_sach` (chỉ buổi của gia sư mình mời) | | SD-21 |
| ↳ Kết luận 1 buổi | `POST /api/hau-kiem/<buoi_pk>/` [MỚI] | | `hau_kiem.ket_luan` [MỚI] | SD-21 |
| ↳ Duyệt nhanh hàng loạt | `POST /api/hau-kiem/hang-loat/` [MỚI] | | `hau_kiem.duyet_hang_loat` [MỚI] | SD-21 |
| ↳ Ghi phản ánh phụ huynh | `POST /api/phan-hoi-phu-huynh/` [MỚI] | | | SD-21 |
| `Quan tri - Doi soat thu lao` (TS dùng chung) | `/doi-soat/?thang=` | `thu_lao.doi_soat` | | SD-30 |
| ↳ Kiểm tra 1 gia sư | `POST /doi-soat/gia-su/<pk>/kiem-tra/` | giữ | `thu_lao.kiem_tra` | SD-30 |
| ↳ Điều chỉnh | `POST /doi-soat/gia-su/<pk>/dieu-chinh/` | giữ | `them_dieu_chinh` | SD-30 |

## 4. Quản trị viên

| Màn hình UI | URL | View / API | Service | SD |
|---|---|---|---|---|
| `Trang chu Quan tri vien` | `/` | `trang_chu_admin` [SỬA: nhóm ngoại lệ mới] | `ngoai_le.ds_can_xem_xet` [SỬA] | |
| `Quan tri - Can xem xet` | `/xem-xet/?q=&loai=` | `ngoai_le.xem_xet` [SỬA: hợp nhất 5 loại + tìm kiếm] | `ngoai_le.hang_doi(q, loai)` [MỚI] | SD-32 |
| ↳ Mở lại · thêm 24 giờ | `POST /xem-xet/buoi/<pk>/mo-lai/` | giữ | `ngoai_le.mo_lai` [SỬA: đóng `YeuCauXuLy`] | SD-33 |
| ↳ Khôi phục & xác nhận từ bản nháp | `POST /xem-xet/yeu-cau/<pk>/khoi-phuc/` [MỚI] | | `ngoai_le.khoi_phuc_tu_nhap` [MỚI] | SD-34 |
| ↳ Tạo lại phòng bằng host khác | `POST /xem-xet/yeu-cau/<pk>/tao-lai-zoom/` [MỚI] | | `buoi_hoc.tao_lai_zoom(host)` [MỚI] | SD-34 |
| ↳ Duyệt / từ chối đổi gia sư | `POST /xem-xet/doi-gia-su/<pk>/` | giữ | `duyet_doi_gia_su` [SỬA] | SD-25 |
| `Quan tri - Ho so gia su` | `/gia-su/<pk>/` | `gia_su.chi_tiet` | | SD-28 |
| ↳ Duyệt / từ chối môn | `POST /gia-su/mon/<pk>/xu-ly/` | giữ (+ chọn cấp độ duyệt) | `duyet_mon` [SỬA], `tu_choi_mon` | SD-28 |
| ↳ Đổi trạng thái hồ sơ | `POST /gia-su/<pk>/trang-thai/` | giữ | `doi_trang_thai_ho_so` | SD-28 |
| `Quan tri - Doi soat thu lao` | `/doi-soat/` | | | SD-31 |
| ↳ Chốt tháng | `POST /doi-soat/chot-thang/` [MỚI – chốt tất cả gia sư đã kiểm tra] | | `thu_lao.chot` (vòng lặp) | SD-31 |
| ↳ Đánh dấu đã chi trả | `POST /doi-soat/chi-tra/` [MỚI] | | `thu_lao.danh_dau_chi_tra` [MỚI] | SD-31 |
| ↳ Xuất CSV | `/doi-soat/csv/` | giữ | | |
| `Quan tri - Tai khoan` | `/tai-khoan/` | giữ + drawer tạo | `tai_khoan.tao` [MỚI service] | SD-03 |
| ↳ Khóa / mở khóa (lý do) | `POST /tai-khoan/<pk>/doi-trang-thai/` | [SỬA: lý do bắt buộc] | `tai_khoan.khoa` → `huy_loi_moi_cua_gia_su` | SD-03 |
| ↳ Đặt lại mật khẩu | `POST /tai-khoan/<pk>/dat-lai-mat-khau/` [MỚI] | | `tai_khoan.dat_lai_mat_khau` | SD-03 |
| `Quan tri - Nhat ky thao tac` | `/nhat-ky/?q=&loai=&nguoi=&tu=&den=` | `tai_khoan.nhat_ky` [SỬA bộ lọc] | | SD-35 |

## 5. Phân quyền dữ liệu theo người phụ trách [MỚI]

`vai_tro_required` chỉ chặn theo vai trò. UI mới cần thêm **lọc theo người** – viết các hàm trong `core/permissions.py`:

| Hàm | Quy tắc |
|---|---|
| `qs_buoi_cua_gia_su(user)` | Gia sư chỉ thấy buổi `gia_su=user` (đã có, BRULE-23) |
| `qs_hau_kiem_cua_ts(user)` | Buổi có `gia_su.ho_so_gia_su.nguoi_moi = user`; Admin thấy tất cả nhưng **không có nút kết luận** |
| `co_the_ket_luan_hau_kiem(user, buoi)` | `user.la_tuyen_sinh` và `buoi.gia_su.ho_so_gia_su.nguoi_moi_id == user.pk`; gia sư chưa có người mời → mọi Tuyển sinh |
| Bộ lọc "Tôi phụ trách" | `tuyen_sinh_phu_trach=user` (Học viên, Khóa học) · "Tôi mời" = `nguoi_moi=user` (Gia sư) – chỉ là bộ lọc, Tuyển sinh vẫn xem được tất cả |
| Ẩn trường nhạy cảm | Gia sư: không có `sdt_phu_huynh`, `hoc_phi_moi_buoi`. Tuyển sinh: không có `host_key` |
