# 17 · Thù lao và đối soát tháng

Code cũ: `services/thu_lao.py` (tiến trình 6.0, PB-16/17, PB-26..28). Giữ nguyên công thức: **Tổng tháng = Tạm tính + Đã đối soát + Điều chỉnh** (Tạm giữ không tính). Kiểm soát 2 người: Tuyển sinh kiểm tra → QTV chốt (người chốt ≠ người kiểm tra). Tháng đã chốt thì khóa sổ, thay đổi sau đó ghi điều chỉnh vào tháng kế tiếp.

Dải 4 bước trên `Quan tri - Doi soat thu lao.dc.html`: **Tự động theo buổi hoàn tất → Tuyển sinh kiểm tra (x/y gia sư) → Quản trị viên chốt → Chi trả cho gia sư**.

## SD-29 · Gia sư xem thu nhập  [SỬA hiển thị]

- **Màn hình:** `Gia su - Thu nhap.dc.html` – chọn tháng, tổng tạm tính/đã đối soát/tạm giữ/điều chỉnh, danh sách buổi với trạng thái Tạm tính · Tạm giữ · Đã đối soát · Đã hủy · **Chờ bạn xác nhận** (buổi đã dạy chưa xác nhận → link tới SD-16).

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant V as /thu-nhap/?thang=
    participant S as thu_lao.tong_hop(thang, gia_su)
    participant DB as DB ThuLao, DieuChinhThuLao, DoiSoatThang, BuoiHoc
    GS->>V: GET
    V->>S: tong_hop(thang, gs)
    S->>DB: ThuLao theo tháng (trừ HUY) gom theo trạng thái
    S->>DB: DieuChinhThuLao, DoiSoatThang của tháng
    V->>DB: BuoiHoc của gs đang cho_xac_nhan (thêm dòng "Chờ bạn xác nhận", chưa có tiền)
    V-->>GS: Tổng + bảng buổi + trạng thái tháng (Đang mở / Đã kiểm tra / Đã chốt / Đã chi trả)
```

## SD-30 · Tuyển sinh kiểm tra từng gia sư, thêm điều chỉnh  [GIỮ]

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Doi soat thu lao
    participant S as services.thu_lao
    participant DB as DB ThuLao, DieuChinhThuLao, DoiSoatThang, NhatKy
    alt Thêm điều chỉnh
        TS->>UI: Dialog: gia sư, số tiền (+/−), lý do
        UI->>S: them_dieu_chinh(ts, gs, thang, so_tien, ly_do)
        alt Tháng đã chốt
            S-->>UI: "Tháng 10/2026 đã chốt. Hãy ghi điều chỉnh vào tháng 11/2026."
        else
            S->>DB: DieuChinhThuLao
            S->>DB: Xóa DoiSoatThang DA_KIEM_TRA của gia sư đó (phải kiểm tra lại)
        end
    else Kiểm tra
        TS->>UI: Nút kiểm tra ở dòng gia sư
        UI->>S: kiem_tra(ts, gs, thang)
        alt Còn buổi Tạm giữ (hậu kiểm Có vấn đề chưa xử lý)
            S-->>UI: "Còn 1 buổi đang tạm giữ. Xử lý xong mới kiểm tra được." (link tới Hậu kiểm)
        else
            S->>DB: DoiSoatThang(DA_KIEM_TRA, tong_tien chụp lại, kiem_tra_boi)
        end
    end
    S->>DB: ghi_nhat_ky
```

## SD-31 · Quản trị viên chốt tháng và đánh dấu chi trả  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor QTV
    participant UI as Doi soat thu lao
    participant V as /doi-soat/chot-thang/ [MỚI] , /doi-soat/chi-tra/ [MỚI]
    participant S as services.thu_lao
    participant DB as DB DoiSoatThang, ThuLao, NhatKy
    participant EM as Email gia sư
    QTV->>UI: "Chốt thù lao tháng"
    alt Chưa kiểm tra hết gia sư
        UI-->>QTV: Nút khóa: "Cần kiểm tra hết gia sư trước khi chốt"
    else
        UI->>V: POST thang
        loop Mỗi gia sư DA_KIEM_TRA
            V->>S: chot(admin, gs, thang)
            alt Tổng đã đổi sau khi kiểm tra
                S-->>V: Bỏ qua, báo "cần kiểm tra lại"
            else Người chốt = người kiểm tra
                S-->>V: Bỏ qua, báo "kiểm soát 2 người"
            else
                S->>DB: DoiSoatThang → DA_CHOT, ThuLao TAM_TINH → DA_DOI_SOAT
                S->>EM: "Thù lao tháng 10/2026 đã được chốt: 12 buổi, tổng …"
            end
        end
        V-->>UI: "Đã chốt thù lao tháng 10/2026 · 17.040.000đ" (+ danh sách bỏ qua nếu có)
    end
    QTV->>V: Sau khi chuyển khoản: "Đánh dấu đã chi trả", chung_tu
    V->>S: danh_dau_chi_tra(admin, thang, chung_tu)
    S->>DB: DoiSoatThang DA_CHOT → DA_CHI_TRA, chi_tra_boi/luc
    S->>DB: ghi_nhat_ky
```

| Tình huống | Kết quả |
|---|---|
| Buổi tháng đã chốt bị hậu kiểm "không tính" | Tạo `DieuChinhThuLao` âm ở tháng mở kế tiếp (SD-22) |
| Gia sư xác nhận buổi tháng 10 vào ngày 01/11 khi tháng 10 đã chốt | `thang_ghi_nhan()` dồn sang tháng 11 (đã có) |
| Xuất CSV | `/doi-soat/csv/` giữ nguyên, thêm cột trạng thái chi trả |
