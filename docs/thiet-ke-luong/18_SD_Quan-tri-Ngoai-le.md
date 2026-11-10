# 18 · Quản trị viên: Cần xem xét, mở lại, sự cố, nhật ký, tìm kiếm

Phạm vi của QTV sau khi đổi phân vai: **quên xác nhận (mở lại buổi tự hủy), lỗi hệ thống, sự cố Zoom, duyệt đổi gia sư lần ≥ 2, duyệt hồ sơ & môn, tài khoản, chốt thù lao**. QTV **không** hậu kiểm buổi học.

## SD-32 · Trang Cần xem xét: hàng đợi hợp nhất + tìm theo mã  [SỬA]

- **Màn hình:** `Quan tri - Can xem xet.dc.html` – tab Tất cả / Mở lại buổi / Lỗi hệ thống / Đổi gia sư / Hồ sơ & môn; ô tìm "Nhập mã buổi BH-00399, mã khóa, tên…" (bỏ dấu, bỏ gạch: `bh00399` = `BH-00399`); nếu mã không nằm trong hàng đợi → thẻ "BH-xxxxx không có yêu cầu xử lý" + link mở buổi.
- **Code cũ:** `ngoai_le.ds_can_xem_xet()` chỉ có buổi `DANG_XEM_XET` + buổi tự hủy trong 7 ngày. **Sửa:** `hang_doi(q, loai)` gộp 5 nguồn.

```mermaid
sequenceDiagram
    autonumber
    actor QTV
    participant UI as Quan tri - Can xem xet
    participant V as /xem-xet/?q=&loai=
    participant S as ngoai_le.hang_doi [MỚI]
    participant DB as DB YeuCauXuLy, DoiGiaSu, HoSoGiaSu, MonGiaSu, BuoiHoc
    QTV->>UI: Gõ "bh399" hoặc chọn tab
    UI->>V: GET (debounce 300ms, cập nhật URL)
    V->>S: hang_doi(q, loai)
    S->>DB: YeuCauXuLy CHO_XU_LY (MO_LAI, LOI_HE_THONG, SU_CO_ZOOM)
    S->>DB: DoiGiaSu CHO_DUYET
    S->>DB: HoSoGiaSu CHO_DUYET có ≥1 môn gửi, MonGiaSu CHO_DUYET
    S->>S: chuẩn hóa q: bỏ dấu, bỏ "-" và khoảng trắng, chữ thường
    S->>S: Nếu q dạng bh/kh/yc + số → so khớp chính xác mã, ngược lại tìm tên gia sư/học viên
    S-->>V: mục (loại, tiêu đề, tuổi chờ, hạn, dữ kiện, trích lời gia sư, hành động)
    alt q là mã buổi tồn tại nhưng không có trong hàng đợi
        V-->>UI: Thẻ "BH-00412 không có yêu cầu xử lý · trạng thái Hoàn tất · Mở buổi"
    else
        V-->>UI: Danh sách sắp theo hạn gần nhất
    end
```

## SD-33 · Mở lại buổi tự hủy (+24 giờ)  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor QTV
    participant UI as Can xem xet (mục Mở lại buổi)
    participant V as /xem-xet/buoi/{pk}/mo-lai/
    participant S as ngoai_le.mo_lai [SỬA]
    participant DB as DB BuoiHoc, KhoaHoc, YeuCauXuLy, NhatKy, ThongBao
    participant EM as Email gia sư
    QTV->>UI: Đọc lời gia sư, dữ kiện Zoom (gia sư x phút y%, học viên…), bấm "Mở lại · thêm 24 giờ", ghi lý do
    UI->>V: POST ly_do
    V->>S: mo_lai(admin, buoi, ly_do)
    alt Không phải DA_HUY + QUA_HAN
        S-->>UI: "Chỉ mở lại được buổi bị hệ thống tự hủy vì quá hạn xác nhận."
    else Quá 7 ngày
        S-->>UI: "Buổi đã hủy quá 7 ngày, không mở lại được nữa."
    else Khóa HUY hoặc hết chỗ (so_buoi_co_the_xep ≤ 0)
        S-->>UI: "Khóa không còn chỗ: đã học…, đang lên lịch… Hủy bớt buổi sắp tới hoặc sửa số buổi trước."
    else Hợp lệ
        S->>DB: UPDATE BuoiHoc SET DA_LEN_LICH, han_xac_nhan = now + 24h, da_nhac_han = False, mo_lai_luc WHERE DA_HUY AND QUA_HAN
        S->>DB: YeuCauXuLy → DA_XU_LY, ket_qua = ly_do
        S->>DB: ghi_nhat_ky(admin, "Mở lại buổi học quá hạn", ly_do)
        S->>EM: "Buổi BH-00399 đã được mở lại. Bạn có tới 21:00 11/11 để xác nhận"
        S->>DB: ThongBao gia sư
    end
    opt Từ chối yêu cầu mở lại
        QTV->>V: POST tu_choi, ly_do
        V->>DB: YeuCauXuLy → TU_CHOI, email gia sư
    end
```

> Buổi mở lại hiển thị lại "Chờ xác nhận" (vì `ket_thuc ≤ now` và `han_xac_nhan` mới) – đúng với Q4, không cần trạng thái mới.

## SD-34 · Lỗi hệ thống và sự cố Zoom  [MỚI]

- **Màn hình:** mục "Lỗi hệ thống" (VD: "BH-00381 · Gia sư Đỗ Thanh Tùng báo lỗi không xác nhận được · HTTP 500 · /buoi-hoc/381/xac-nhan") với nút **"Khôi phục & xác nhận từ bản nháp"**, **"Chuyển kỹ thuật"**; mục sự cố Zoom với **"Tạo lại bằng host khác"**.

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    actor QTV
    participant MW as Middleware GhiSuCo [MỚI]
    participant V as View bất kỳ
    participant S as services.ngoai_le
    participant DB as DB SuCoHeThong, YeuCauXuLy, BanNhapDanhGia, BuoiHoc
    participant ZM as Zoom
    GS->>V: POST /buoi-hoc/381/xac-nhan/
    V--xMW: Exception chưa bắt
    MW->>DB: SuCoHeThong(user, path, 500, traceback rút gọn, form đã lọc mật khẩu)
    opt Đường dẫn gắn với một buổi (/buoi-hoc/{pk}/…)
        MW->>DB: YeuCauXuLy(LOI_HE_THONG, buoi, su_co, han_xu_ly = han_xac_nhan)
        MW->>DB: BuoiHoc.han_xac_nhan += 24h (không tính là quá hạn của gia sư)
    end
    MW-->>GS: Trang 500 thân thiện "Hệ thống đã ghi lại lỗi và báo Quản trị viên. Bản nháp đánh giá của bạn vẫn còn."
    QTV->>S: "Khôi phục & xác nhận từ bản nháp" (lý do)
    S->>DB: Đọc BanNhapDanhGia của buổi
    alt Không có bản nháp / thiếu mục bắt buộc
        S-->>QTV: "Bản nháp chưa đủ 3 mục bắt buộc. Mở lại để gia sư tự xác nhận." (chuyển sang mo_lai)
    else Đủ
        S->>S: xac_nhan_hoan_tat(gia_su của buổi, buoi, du_lieu nháp, bo_qua_han=True, nguoi_thuc_hien=QTV)
        Note right of S: Toàn bộ SD-16: số buổi, thù lao, Zalo, HauKiemBuoi. Nhật ký ghi rõ "QTV khôi phục thay gia sư"
        S->>DB: YeuCauXuLy → DA_XU_LY
    end
    opt Chuyển kỹ thuật
        QTV->>DB: YeuCauXuLy → CHUYEN_KY_THUAT (vẫn hiện, nhãn khác, không tính hạn)
    end
    QTV->>S: Sự cố Zoom → "Tạo lại bằng host khác"
    S->>DB: Chọn TaiKhoanZoom khác đang bật, không trùng giờ
    S->>ZM: xoa_phong(cũ) rồi tao_phong(host mới)
    alt OK
        S->>DB: BuoiHoc DA_LEN_LICH, zoom_* mới, tai_khoan_zoom
        S->>DB: ThongBao gia sư "Phòng Zoom đã được tạo lại, sao chép lại tin nhắn Zalo"
    else Vẫn lỗi
        S-->>QTV: Lỗi Zoom chi tiết, giữ yêu cầu CHO_XU_LY
    end
```

## SD-35 · Nhật ký thao tác và tìm nhanh Ctrl+K  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor U as QTV / Tuyển sinh
    participant UI as Nhat ky thao tac / bảng lệnh Ctrl+K
    participant V as /nhat-ky/ , /api/tim-kiem/
    participant S as tim_kiem.tim [MỚI]
    participant DB as DB NhatKy, YeuCauHocTap, KhoaHoc, BuoiHoc, HocVien, User
    U->>UI: Nhật ký: lọc người, loại đối tượng, khoảng ngày, gõ mã
    UI->>V: GET /nhat-ky/?q=BH-00398&loai=BUOI&tu=&den=
    V->>DB: NhatKy WHERE ma_doi_tuong = … OR hanh_dong/chi_tiet icontains, phân trang 50
    V-->>UI: Dòng "Trần Thu Trang hậu kiểm BH-00398: có vấn đề" + bảng Trước/Sau (gia_tri_cu/moi)
    U->>UI: Ctrl+K, gõ "gia bảo"
    UI->>V: GET /api/tim-kiem/?q=gia bảo
    V->>S: tim(user, q)
    S->>DB: Tìm theo mã (YC/KH/BH) + tên học viên, gia sư, phụ huynh (bỏ dấu)
    S->>S: Lọc theo quyền (gia sư chỉ thấy lớp/buổi của mình, không thấy học viên khác)
    S-->>UI: Nhóm: Yêu cầu, Khóa học, Buổi học, Học viên, Gia sư, Lệnh (Tạo yêu cầu, Đối soát tháng 10)
```

> Nhật ký **chỉ thêm, không sửa, không xóa**. Không có view sửa/xóa `NhatKy`; trong `admin.py` đặt `has_change_permission/has_delete_permission = False`.
