# 12 · Học thử và mở khóa học

Code cũ: `services/khoa_hoc.py` (tiến trình 4.0: 4.1 ghi kết quả học thử, 4.2 tạo khóa). Buổi học thử do **gia sư** tạo (SD-13, `tao_buoi_hoc_thu`).

Dòng tiến trình trên `Tuyen sinh - Chi tiet yeu cau.dc.html`: **Mới → Đang mời gia sư → Đã có gia sư → Học thử → Đã mở khóa**. Ở bước "Đã có gia sư" có 2 lối: chờ gia sư tạo buổi học thử, hoặc **"Đăng ký chính thức luôn"** (nhánh A).

## SD-10 · Đăng ký chính thức luôn (nhánh A, bỏ học thử)  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Tuyen sinh - Chi tiet yeu cau
    participant V as /yeu-cau/{pk}/dang-ky-thang/ [MỚI]
    participant S as khoa_hoc.danh_dau_dang_ky_thang [MỚI]
    participant DB as DB YeuCauHocTap, BuoiHoc, NhatKy
    TS->>UI: "Đăng ký chính thức luôn" → hộp thoại xác nhận
    UI->>V: POST
    V->>S: danh_dau_dang_ky_thang(ts, yc)
    alt yc không ở DA_PHAN_CONG
        S-->>UI: "Chỉ dùng khi yêu cầu đã có gia sư"
    else Đã có buổi học thử chưa hủy
        S-->>UI: "Yêu cầu này đã có buổi học thử. Ghi kết quả học thử thay vì đăng ký thẳng."
    else
        S->>DB: yc.dang_ky_thang = True (vẫn DA_PHAN_CONG)
        S->>DB: ghi_nhat_ky(ts, "Đăng ký chính thức không học thử")
        S-->>UI: Bước tiếp theo "Mở khóa học" (mở drawer SD-12)
    end
```

> Code cũ đã cho tạo khóa thẳng từ `DA_PHAN_CONG` khi chưa có buổi học thử (`co_the_tao_khoa` nhánh A). Cờ `dang_ky_thang` chỉ để UI hiện đúng bước và **chặn gia sư tạo buổi học thử** sau khi đã chốt đăng ký thẳng (`yeu_cau_co_the_hoc_thu` lọc `dang_ky_thang=False`).

## SD-11 · Ghi kết quả học thử (4 kết quả)  [SỬA]

- **Màn hình:** drawer "Ghi kết quả học thử" trên `Trang chu Tuyen sinh` và `Tuyen sinh - Chi tiet yeu cau` (3 thẻ chọn: Đồng ý đăng ký / Không đăng ký / Cần thêm thời gian; thêm lựa chọn phụ "Tìm gia sư khác").
- **Điều kiện:** có buổi học thử `HOAN_TAT` với gia sư hiện tại (`buoi_hoc_thu_hoan_tat`).

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Drawer ket qua hoc thu
    participant API as /api/yeu-cau/{pk}/ket-qua-hoc-thu/
    participant S as khoa_hoc.ghi_ket_qua_hoc_thu
    participant DB as DB YeuCauHocTap, BuoiHoc, NhacViec, NhatKy, ThongBao
    participant ZM as Zoom
    participant EM as Email
    TS->>UI: Gọi phụ huynh, chọn kết quả, ghi chú
    UI->>API: POST ket_qua, ghi_chu
    API->>S: ghi_ket_qua_hoc_thu(ts, yc, ket_qua, ghi_chu)
    alt Chưa có buổi học thử hoàn tất
        S-->>UI: "Chưa có buổi học thử hoàn tất với gia sư hiện tại"
    else KHONG_DANG_KY mà thiếu ghi chú
        S-->>UI: errors.ghi_chu "Cần ghi lý do phụ huynh không tiếp tục"
    else DONG_Y
        S->>DB: UPDATE yc SET HOC_THU_XONG, ket_qua=DONG_Y WHERE DA_PHAN_CONG
        S-->>UI: "Đã ghi: phụ huynh đồng ý đăng ký. Bước tiếp theo: Mở khóa học"
    else CAN_THEM_THOI_GIAN
        S->>DB: yc giữ DA_PHAN_CONG, ket_qua=CAN_THEM_THOI_GIAN, nhac_goi_lai_luc = now + 2 ngày
        S->>DB: NhacViec(GOI_LAI_PHU_HUYNH, ts, han_luc)
        S-->>UI: "Đã ghi: cần thêm thời gian. Nhắc gọi lại sau 2 ngày"
    else TIM_GIA_SU_KHAC
        S->>DB: yc → DANG_TIM, gia_su=None
        S->>DB: huy_buoi_thu_chua_hoc(yc, gs) + on_commit xóa phòng Zoom
        S->>ZM: xoa_phong (nếu còn buổi chưa học)
        S->>EM: Email gia sư "Kết quả học thử YC-xxxx"
    else KHONG_DANG_KY
        S->>DB: yc → DONG, ly_do_dong = "Không đăng ký sau học thử: ghi chú"
        S->>DB: hủy buổi thử chưa học, LoiMoi CHO → VOIDED
        S->>EM: Email gia sư
    end
    S->>DB: ghi_nhat_ky(ts, "Ghi kết quả học thử")
```

| Tình huống | Kết quả |
|---|---|
| `CAN_THEM_THOI_GIAN` rồi gọi lại được | Ghi kết quả lần nữa (cho phép ghi đè khi `ket_qua_hoc_thu = CAN_THEM_THOI_GIAN`); `NhacViec.xong_luc = now` |
| Quá hạn nhắc mà chưa gọi | Tác vụ định kỳ (SD-36) đẩy lên nhóm "Gấp, cần xử lý ngay" trên trang chủ Tuyển sinh |
| Ghi kết quả ở 2 tab | Cập nhật có điều kiện → tab sau báo "Yêu cầu không còn ở trạng thái Đã có gia sư" |

## SD-12 · Mở khóa học chính thức  [SỬA]

- **Màn hình:** drawer "Mở khóa học" (từ `Tuyen sinh - Chi tiet yeu cau`): số buổi, thời lượng 60/90/120, học phí/buổi, thù lao/buổi, **lịch cố định**, **tên nhóm Zalo lớp**, ghi chú phụ huynh.

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Drawer Mo khoa hoc
    participant V as /yeu-cau/{pk}/tao-khoa/
    participant S as khoa_hoc.tao_khoa_hoc
    participant DB as DB YeuCauHocTap, KhoaHoc, NhatKy, ThongBao
    participant EM as Email
    TS->>UI: Nhập số buổi, thời lượng, học phí, thù lao, lịch cố định, nhóm Zalo
    UI->>UI: Kiểm tra thù lao ≤ học phí, số buổi > 0
    UI->>V: POST
    V->>S: tao_khoa_hoc(ts, yc, du_lieu)
    alt Đã học thử nhưng chưa ghi DONG_Y
        S-->>UI: "Yêu cầu này đã học thử: cần ghi kết quả Đồng ý trước khi tạo khóa."
    else Gia sư không còn đủ điều kiện (bị khóa / thu hồi môn)
        S-->>UI: "Gia sư … không còn đủ điều kiện dạy môn …"
    else Hợp lệ
        critical transaction.atomic
            S->>DB: UPDATE yc SET CHINH_THUC WHERE trang_thai = (cũ)
            S->>DB: KhoaHoc(DANG_HOC, ma_lop = KH-xxxx, lich_co_dinh, zalo_nhom, tuyen_sinh_phu_trach = ts)
            Note right of DB: CheckConstraint thu_lao ≤ hoc_phi, so_buoi > 0. OneToOne yeu_cau chặn tạo 2 khóa
            S->>DB: ghi_nhat_ky(ts, "Tạo khóa học chính thức", nhánh A hoặc sau học thử)
        end
        S->>DB: ThongBao gia sư
        S->>EM: Email gia sư "Khóa học mới KH-xxxx" (không có học phí)
        V-->>UI: 302 /khoa-hoc/{pk}/
    end
```

| Tình huống | Kết quả |
|---|---|
| Bấm "Mở khóa" 2 lần | Lần 2: `IntegrityError` (OneToOne) → "Yêu cầu này đã có khóa học." |
| Thù lao > học phí | Lỗi ô nhập (form) + `CheckConstraint` ở DB |
| Lịch cố định trùng giờ rảnh gia sư? | Chỉ gợi ý; kiểm tra thật khi gia sư tạo buổi (SD-13) |
