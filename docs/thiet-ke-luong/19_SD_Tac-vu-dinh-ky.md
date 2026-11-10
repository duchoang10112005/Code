# 19 · Tác vụ định kỳ `quet_dinh_ky`

Code cũ: `management/commands/quet_dinh_ky.py` chạy bằng Windows Task Scheduler mỗi 15 phút: `quet_han()` → `quet_loi_moi_het_han()` → `hau_kiem()`. Ngoài ra `quet_han()` và `quet_loi_moi_het_han()` còn được gọi "lười" khi mở trang chủ/trang lời mời – **giữ cách này** để demo không phụ thuộc lịch chạy.

**Sửa:** chạy mỗi **5 phút** (vì có mở/đóng phòng Zoom theo phút), tách thành các bước độc lập; mỗi bước tự bắt lỗi để một bước lỗi không chặn bước sau; dùng **cập nhật có điều kiện** nên chạy chồng 2 lần cũng không gửi trùng.

## SD-36 · Một lượt quét

```mermaid
sequenceDiagram
    autonumber
    participant SCH as quet_dinh_ky (mỗi 5 phút)
    participant S as services
    participant DB as DB
    participant ZM as Zoom API
    participant EM as Email + ThongBao
    SCH->>S: 1. quet_loi_moi_het_han()
    S->>DB: LoiMoi CHO, het_han_luc ≤ now → HET_HAN
    S->>DB: Yêu cầu DANG_TIM không còn lời mời CHO → ThongBao Tuyển sinh "cần mời thêm" (một lần)
    SCH->>S: 2. mo_dong_phong(now) [MỚI]
    S->>DB: BuoiHoc DA_LEN_LICH, bat_dau - 10′ ≤ now, phong_mo_luc null
    S->>DB: phong_mo_luc = now (link /lop/ bắt đầu chuyển hướng, SD-14)
    S->>DB: BuoiHoc có ket_thuc + 5′ ≤ now, phong_dong_luc null
    S->>ZM: PUT /meetings/{id}/status end
    S->>DB: phong_dong_luc = now
    SCH->>S: 3. quet_han(now)
    S->>DB: Nhắc: DA_LEN_LICH, đã kết thúc, han_xac_nhan - 3h ≤ now, da_nhac_han False → True
    S->>EM: Gia sư "Nhắc xác nhận buổi BH-…, hạn 21:30"
    S->>DB: Tự hủy: DA_LEN_LICH, han_xac_nhan < now → DA_HUY + QUA_HAN
    S->>EM: Gia sư "Buổi … đã bị hủy do quá hạn… liên hệ trong 7 ngày" + nút Xin mở lại
    S->>DB: LOI_ZOOM đã qua giờ bắt đầu → DA_HUY + LOI_ZOOM
    S->>EM: Gia sư "Buổi … bị hủy vì chưa có phòng Zoom. Hãy tạo buổi bù"
    SCH->>S: 4. hau_kiem(now)  (SD-20)
    S->>ZM: participants, recordings
    S->>DB: HauKiemBuoi 5 chỉ số, ban_ghi_*
    SCH->>S: 5. nhac_viec(now) [MỚI]
    S->>DB: NhacViec han_luc ≤ now, chưa xong → ThongBao người phụ trách (một lần/ngày)
    S->>DB: Khóa DANG_HOC còn ≤ 2 buổi, chưa có NhacViec HOI_GIA_HAN → tạo NhacViec cho Tuyển sinh phụ trách
    S->>DB: YeuCauXuLy MO_LAI quá han_xu_ly → TU_CHOI tự động ("Quá 7 ngày")
    SCH->>S: 6. het_han_ban_ghi(now)
    S->>DB: SAN_SANG và ban_ghi_het_han < now → HET_HAN
    SCH->>S: 7. tam_nghi_het_han(today) [MỚI]
    S->>DB: HoSoGiaSu tam_nghi_den < hôm nay → tam_nghi_den = null (lại được đề xuất)
    SCH-->>SCH: In tổng kết, ghi NhatKy(None, "Quét định kỳ", số liệu) nếu có thay đổi
```

## Ma trận thời gian của một buổi học 19:00–20:30

| Mốc | Sự kiện | Ai/cái gì làm |
|---|---|---|
| Lúc tạo buổi | `han_xac_nhan` = 20:30 + 12h = **08:30 hôm sau** | `_tao()` |
| 18:50 | Phòng mở, `/lop/<ma>` chuyển hướng vào Zoom; nút "Mở phòng Zoom" bật | Bước 2 / SD-14 |
| 19:00–20:30 | "Đang học" (hiển thị) | suy ra |
| 20:30 | Phiếu đánh giá mở, "Chờ xác nhận", đồng hồ đếm ngược | suy ra |
| 20:35 | Phòng Zoom bị kết thúc | Bước 2 |
| 05:30 | Email + thông báo nhắc (còn 3h) – "Sắp tự hủy" | Bước 3 |
| 08:30 | Quá hạn → **Tự hủy** (`DA_HUY` + `QUA_HAN`) | Bước 3 |
| ≥ 21:00 sau khi xác nhận | Hậu kiểm lấy dữ liệu Zoom (chờ 30′ Zoom tổng hợp) | Bước 4 |
| Trong 7 ngày | Gia sư xin mở lại → QTV mở lại +24h | SD-19, SD-33 |

## Cấu hình chạy

- Windows (máy demo): Task Scheduler → `python manage.py quet_dinh_ky` mỗi 5 phút.
- Linux/hosting: cron `*/5 * * * * cd /app && python manage.py quet_dinh_ky`.
- Chế độ demo: `THOI_LUONG_BUOI_DEMO=1` (đã có) để chạy trọn luồng trong vài phút.
