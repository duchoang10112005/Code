# 14 · Hậu kiểm buổi học

**Thay đổi phân vai (Q1):** code cũ – `hau_kiem()` tự đưa buổi không đạt sang `DANG_XEM_XET` và **Admin** xử lý ở `/xem-xet/`. UI mới – **Tuyển sinh** hậu kiểm buổi của gia sư **do chính mình mời** (`HoSoGiaSu.nguoi_moi`); hệ thống chỉ **thu thập dữ liệu + chấm 5 tiêu chí + gắn cảnh báo**; Admin không làm hậu kiểm.

Nguyên tắc giữ nguyên: **"Xác nhận trước, hậu kiểm sau"** – xác nhận hoàn tất không chờ Zoom; thù lao tạo ngay ở trạng thái Tạm tính.

**5 tiêu chí** (trang `Tuyen sinh - Hau kiem buoi hoc.dc.html`):

| # | Tiêu chí | Nguồn dữ liệu | Ngưỡng (`NGHIEP_VU`) |
|---|---|---|---|
| 1 | Gia sư vào đúng giờ | Zoom participants – lần vào đầu tiên của host so với `bat_dau` | trễ ≤ `TRE_TOI_DA_PHUT` (5) |
| 2 | Gia sư tham gia đủ | tổng phút host có mặt / `thoi_luong_phut` | ≥ `NGUONG_THAM_GIA` (67%) |
| 3 | Học viên tham gia đủ | tổng phút người không phải host | ≥ 67% |
| 4 | Phiếu đánh giá đầy đủ | `len(danh_gia)` | ≥ `DO_DAI_NHAN_XET_TOI_THIEU` (30) |
| 5 | Đã gửi nhận xét qua Zalo | `zalo_trang_thai == DA_GUI` | |

> Code cũ dùng **một** chỉ số "gia sư và học viên **cùng** có mặt" (`danh_gia_tham_gia`). Giữ hàm đó để tính `phut_tham_gia_chung` (vẫn hiện trên Cần xem xét), và tách thêm 3 chỉ số riêng cho UI.

## SD-20 · Hệ thống thu thập dữ liệu Zoom và chấm tiêu chí  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    participant SCH as quet_dinh_ky (mỗi 15′)
    participant S as buoi_hoc.hau_kiem [SỬA]
    participant DB as DB BuoiHoc, HauKiemBuoi, ThongBao
    participant ZM as Zoom API
    SCH->>S: hau_kiem(now)
    S->>DB: BuoiHoc HOAN_TAT, HauKiemBuoi.CHUA_KIEM_TRA, chưa chấm, kết thúc ≥ 30′ trước, trong 7 ngày
    loop Mỗi buổi
        S->>ZM: GET /report/meetings/{id}/participants
        alt Zoom chưa tổng hợp xong (404)
            ZM-->>S: ZoomError → bỏ qua, lượt sau thử lại
        else Gói Zoom không có báo cáo (400/401/403)
            ZM-->>S: None
            S->>DB: tieu chí 1-3 = null, BuoiHoc.kiem_tra = KHONG_DU_LIEU
        else Có dữ liệu
            ZM-->>S: danh sách vào/ra
            S->>S: tre_phut, ty_le_gia_su, ty_le_hoc_vien, phut_tham_gia_chung, thoi_luong_thuc_te
        end
        S->>S: tiêu chí 4 (độ dài nhận xét), tiêu chí 5 (zalo_trang_thai)
        S->>DB: HauKiemBuoi cập nhật 5 chỉ số, so_canh_bao
        Note right of DB: KHÔNG đổi trạng thái buổi, KHÔNG tạm giữ thù lao ở bước này
    end
    S->>DB: ThongBao gom cho từng Tuyển sinh: "N buổi chờ hậu kiểm, M buổi có cảnh báo"
    S->>ZM: Lấy bản ghi (giữ code cũ) → ban_ghi_trang_thai SAN_SANG / LOI / HET_HAN
```

## SD-21 · Tuyển sinh hậu kiểm: từng buổi và duyệt nhanh hàng loạt  [MỚI]

- **Màn hình:** `Tuyen sinh - Hau kiem buoi hoc.dc.html` – thẻ số liệu (buổi tuần này, % hợp lệ, cần chú ý), tab Chưa kiểm tra / Có cảnh báo / Hợp lệ / Có vấn đề / Đã xử lý, ô tìm theo mã buổi, **ô tick chọn tất cả** (trạng thái lửng khi chọn một phần), nút "Chọn buổi đạt đủ tiêu chí", panel chi tiết 5 tiêu chí + nội dung đánh giá + "Phụ huynh phản ánh", nút **Hợp lệ** / **Có vấn đề** (lý do + ghi chú).
- **Quyền:** chỉ buổi có `gia_su.ho_so_gia_su.nguoi_moi = user` (xem `03` mục 5).

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh (người mời)
    participant UI as Tuyen sinh - Hau kiem buoi hoc
    participant API as /api/hau-kiem/...
    participant S as services.hau_kiem [MỚI]
    participant DB as DB HauKiemBuoi, BuoiHoc, ThuLao, PhanHoiPhuHuynh, NhatKy
    participant EM as Email + ThongBao
    TS->>UI: Mở trang (mặc định tab Chưa kiểm tra, tuần này)
    UI->>S: danh_sach(ts, tab, q)
    S->>DB: HauKiemBuoi WHERE nguoi_phu_trach = ts (hoặc gia sư chưa có người mời)
    S-->>UI: Dòng + chip "2 cảnh báo"
    alt Kết luận một buổi
        TS->>UI: Chọn buổi → xem 5 tiêu chí, nhận xét, phản ánh phụ huynh
        TS->>API: POST /api/hau-kiem/{buoi}/ ket_luan=HOP_LE
        API->>S: ket_luan(ts, buoi, HOP_LE)
        S->>DB: UPDATE HauKiemBuoi SET HOP_LE WHERE CHUA_KIEM_TRA (có điều kiện)
        S->>DB: BuoiHoc.kiem_tra = HOP_LE, ghi_nhat_ky
        API-->>UI: Dòng chuyển tab Hợp lệ, toast
    else Có vấn đề
        TS->>API: POST ket_luan=CO_VAN_DE, ly_do, ghi_chu (bắt buộc)
        API->>S: ket_luan(...)
        critical transaction.atomic
            S->>DB: HauKiemBuoi CO_VAN_DE
            S->>DB: BuoiHoc HOAN_TAT → DANG_XEM_XET, kiem_tra = CO_VAN_DE
            S->>DB: ThuLao TAM_TINH → TAM_GIU
            S->>DB: ghi_nhat_ky(ts, "Hậu kiểm: buổi có vấn đề", ly_do)
        end
        S->>EM: Gia sư: "Buổi BH-00398 đang được xem xét. Thù lao tạm giữ…" (mời phản hồi)
    else Duyệt nhanh hàng loạt
        TS->>UI: Tick chọn tất cả (hoặc "Chọn buổi đạt đủ tiêu chí")
        UI->>UI: Hộp xác nhận: "Duyệt N buổi · K buổi có cảnh báo" + tùy chọn "Chỉ duyệt buổi không có cảnh báo"
        TS->>API: POST /api/hau-kiem/hang-loat/ ids[], chi_buoi_sach
        API->>S: duyet_hang_loat(ts, ids, chi_buoi_sach)
        loop Mỗi id (bỏ qua id không thuộc quyền / đã kết luận)
            S->>DB: UPDATE HauKiemBuoi SET HOP_LE, hang_loat=True WHERE CHUA_KIEM_TRA AND (so_canh_bao = 0 nếu chi_buoi_sach)
        end
        S->>DB: ghi_nhat_ky(ts, "Hậu kiểm hàng loạt", "N buổi: BH-…")
        API-->>UI: "Đã duyệt 12 buổi · bỏ qua 2 (có cảnh báo / đã kiểm tra)"
    end
    opt Ghi phản ánh phụ huynh
        TS->>API: POST /api/phan-hoi-phu-huynh/ buoi, noi_dung, diem
        API->>DB: PhanHoiPhuHuynh, tăng so_canh_bao của HauKiemBuoi
    end
```

| Tình huống | Kết quả |
|---|---|
| Không có dữ liệu Zoom | Tiêu chí 1–3 hiện "Không có dữ liệu", vẫn kết luận được bằng tay |
| Tuyển sinh A mở link buổi của gia sư do B mời | Xem được (đọc), API kết luận trả 403 "Buổi này do Trần Thu Trang phụ trách hậu kiểm" |
| QTV mở trang | Chỉ xem; không có nút kết luận |
| Kết luận ở 2 tab | Cập nhật có điều kiện → tab sau báo "Buổi đã được kiểm tra" |
| Tháng đã **chốt** đối soát mà kết luận Có vấn đề | Thù lao `DA_DOI_SOAT` không chuyển Tạm giữ được → tạo **điều chỉnh trừ** ở tháng sau (SD-22) |

## SD-22 · Xử lý buổi có vấn đề: vẫn tính hoặc không tính  [SỬA – chuyển từ Admin sang Tuyển sinh]

- Dùng lại logic `ngoai_le.xac_nhan_hop_le()` và `ngoai_le.huy_sau_xem_xet()` của code cũ, đổi quyền từ QTV sang Tuyển sinh phụ trách, gắn vào `HauKiemBuoi`.

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh phụ trách
    participant API as /api/hau-kiem/{buoi}/xu-ly/
    participant S as hau_kiem.xu_ly
    participant DB as DB BuoiHoc, HauKiemBuoi, KhoaHoc, ThuLao, DieuChinhThuLao, NhatKy
    participant EM as Email gia sư
    TS->>API: POST tinh = true/false, ly_do (bắt buộc)
    API->>S: xu_ly(ts, buoi, tinh, ly_do)
    alt tinh = true (gia sư giải trình hợp lý)
        S->>DB: BuoiHoc DANG_XEM_XET → HOAN_TAT, kiem_tra = DA_XU_LY
        S->>DB: ThuLao TAM_GIU → TAM_TINH
        S->>DB: HauKiemBuoi = DA_XU_LY_TINH
        S->>EM: "Buổi BH-… được công nhận, thù lao tính bình thường"
    else tinh = false
        alt ThuLao đã DA_DOI_SOAT (tháng đã chốt)
            S->>DB: DieuChinhThuLao(so_tien = -thu_lao, thang = tháng mở kế tiếp, ly_do)
        else
            S->>DB: ThuLao → HUY
        end
        S->>DB: BuoiHoc → DA_HUY, ly_do_huy = HAU_KIEM
        S->>DB: KhoaHoc so_buoi_da_dung - 1, HOAN_THANH → DANG_HOC nếu cần
        S->>DB: HauKiemBuoi = DA_XU_LY_KHONG_TINH
        S->>EM: "Buổi BH-… không được công nhận… số buổi đã trả lại cho khóa"
    end
    S->>DB: ghi_nhat_ky(ts, ...)
```

> Trên UI, tab "Đã xử lý" hiện 2 nhãn: **Đã xử lý** (vẫn tính) và **Không tính**.
