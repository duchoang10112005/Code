# 16 · Hồ sơ gia sư, giờ rảnh, đăng ký môn

Code cũ: `services/gia_su.py` (tiến trình 2.0 – PB-04, BRULE-09/10). Quy tắc giữ: gia sư **không** sửa/xóa môn đã duyệt; chỉ QTV duyệt/từ chối/thu hồi môn và đổi trạng thái hồ sơ; hồ sơ chỉ "Đang hoạt động" khi có ≥ 1 môn đã duyệt.

## SD-26 · Cập nhật hồ sơ và lưới giờ rảnh  [SỬA]

- **Màn hình:** `Gia su - Ho so cua toi.dc.html` – thông tin cá nhân, học vấn, kinh nghiệm, email Zoom, số lớp tối đa, tạm nghỉ đến ngày; **lưới giờ rảnh** 7 ngày × 4 khung (chú thích "Rảnh (N khung)", ô đang dạy khóa lại).

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Gia su - Ho so cua toi
    participant API as /api/ho-so/gio-ranh/ [MỚI]
    participant S as gia_su.dat_luoi_gio_ranh [MỚI]
    participant DB as DB LichRanh, BuoiHoc, KhoaHoc, NhatKy
    GS->>UI: Bấm các ô lưới rồi "Lưu giờ rảnh"
    UI->>API: POST khung[] = ["0-TOI","2-TOI",...]
    API->>S: dat_luoi_gio_ranh(ho_so, khung)
    S->>DB: Khung đang có lịch cố định / buổi sắp tới của khóa DANG_HOC
    alt Bỏ chọn khung đang dạy
        S-->>UI: Cảnh báo "T4 tối đang dạy KH-0005. Giờ rảnh chỉ dùng để đề xuất lớp mới, lịch đang dạy không đổi." (vẫn lưu)
    end
    critical transaction.atomic
        S->>DB: Xóa LichRanh không còn trong danh sách
        S->>DB: Tạo LichRanh mới (khung → tu_gio/den_gio)
    end
    S->>DB: ghi_nhat_ky(gs, "Cập nhật giờ rảnh", "N khung")
    API-->>UI: "Đã lưu · Rảnh (10 khung)"
```

| Tình huống | Kết quả |
|---|---|
| Đặt "Tạm nghỉ đến 20/11" | Không xuất hiện trong đề xuất (SD-06); lời mời đang chờ → VOIDED qua `huy_loi_moi_cua_gia_su(…, "Gia sư tạm nghỉ")`; buổi đã xếp **không** tự hủy (cảnh báo gia sư tự báo hủy hoặc Tuyển sinh đổi gia sư) |
| Đổi `so_lop_toi_da` thấp hơn số lớp đang dạy | Cho lưu; trạng thái thành "Kín lịch" |

## SD-27 · Đăng ký môn mới – popup 4 bước (bài test + minh chứng)  [SỬA lớn]

- **Màn hình:** popup lớn giữa màn hình trên `Gia su - Ho so cua toi`: **Bước 1** Chọn môn + cấp độ (danh mục do trung tâm cấu hình) → **Bước 2** Làm bài test (link riêng của môn, số câu, thời gian, điểm đạt) → nhập điểm + ảnh/link kết quả → **Bước 3** Minh chứng (nhiều mục: loại + tệp hoặc link https) → **Bước 4** Xem lại và gửi. Danh sách môn có trạng thái Chờ duyệt / Đã duyệt / Bị từ chối (Gửi lại) / Đã rút.

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Popup dang ky mon (4 buoc)
    participant V as /ho-so/mon/dang-ky/ (multipart)
    participant S as gia_su.dang_ky_mon [SỬA]
    participant DB as DB MonHoc, CapDo, MonGiaSu, MinhChung, NhatKy, ThongBao
    participant FS as Lưu tệp MEDIA_ROOT
    GS->>UI: Bước 1 – chọn môn, cấp độ
    UI->>DB: (khi mở trang) MonHoc dang_mo + CapDo theo môn, loại môn đã DA_DUYET/CHO_DUYET
    GS->>UI: Bước 2 – mở bai_test_url (tab mới), làm bài, nhập điểm, tải ảnh hoặc dán link kết quả
    UI->>UI: Điểm < diem_dat → cảnh báo "Chưa đạt ngưỡng 7,0 – vẫn gửi được, QTV sẽ cân nhắc"
    GS->>UI: Bước 3 – thêm minh chứng (Thẻ SV, Bảng điểm, Bằng cấp…), mỗi mục tệp ≤ 5MB hoặc link https
    GS->>UI: Bước 4 – xem lại, "Gửi đăng ký"
    UI->>V: POST mon, cap_do[], diem_test, anh/link, minh_chung[]
    V->>S: dang_ky_mon(ho_so, du_lieu, tep)
    alt Môn đã DA_DUYET hoặc CHO_DUYET
        S-->>UI: "Bạn đã đăng ký môn Toán (chờ duyệt)."
    else Thiếu kết quả test / không có minh chứng / link không phải https / tệp sai định dạng
        S-->>UI: Lỗi theo bước, popup quay lại đúng bước
    else Hợp lệ
        critical transaction.atomic
            S->>FS: Lưu ảnh kết quả, tệp minh chứng
            alt Môn từng TU_CHOI hoặc DA_RUT
                S->>DB: Cập nhật bản ghi cũ về CHO_DUYET ("Gửi lại"), xóa ghi_chu_duyet
            else
                S->>DB: MonGiaSu(CHO_DUYET, diem_test, gui_luc)
            end
            S->>DB: cap_do_duyet = cấp độ đã chọn (đề nghị), MinhChung x N
            S->>DB: ghi_nhat_ky(gs, "Đăng ký môn dạy")
        end
        S->>DB: ThongBao QTV "Phạm Ngọc Lan đăng ký thêm Tiếng Anh 9"
        S-->>UI: Đóng popup, thẻ môn mới "Chờ duyệt"
    end
```

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant V as /ho-so/mon/{pk}/rut/
    participant S as gia_su.rut_mon [SỬA]
    participant DB as DB MonGiaSu, NhatKy
    GS->>V: POST rút môn
    alt Môn DA_DUYET
        S-->>V: "Môn đã được duyệt không thể tự rút. Vui lòng liên hệ Quản trị viên."
    else CHO_DUYET hoặc TU_CHOI
        S->>DB: trang_thai = DA_RUT (giữ bản ghi + minh chứng để tra cứu, không delete như cũ)
        S->>DB: ghi_nhat_ky
    end
```

## SD-28 · Quản trị viên duyệt hồ sơ và môn  [SỬA]

- **Màn hình:** `Quan tri - Ho so gia su.dc.html` (thông tin, minh chứng, kết quả test, lưới giờ rảnh, lớp đang dạy) và mục "Hồ sơ & môn" trên `Quan tri - Can xem xet`.

```mermaid
sequenceDiagram
    autonumber
    actor QTV
    participant UI as Quan tri - Ho so gia su
    participant V as /gia-su/mon/{pk}/xu-ly/ , /gia-su/{pk}/trang-thai/
    participant S as services.gia_su
    participant DB as DB MonGiaSu, HoSoGiaSu, LoiMoi, YeuCauHocTap, NhatKy
    participant EM as Email gia sư
    QTV->>UI: Xem điểm test, mở minh chứng (tệp/link)
    alt Duyệt môn
        QTV->>V: POST duyet, cap_do_duyet[] (có thể bớt cấp độ), ghi_chu
        V->>S: duyet_mon(admin, mg, cap_do, ghi_chu)
        S->>DB: Kiểm tra chưa DA_DUYET (chống F5), cập nhật DA_DUYET, duyet_boi/luc
        S->>EM: "Môn Tiếng Anh 9 đã được duyệt…"
        opt Hồ sơ đang CHO_DUYET và đây là môn duyệt đầu tiên
            UI-->>QTV: Gợi ý "Kích hoạt hồ sơ để gia sư nhận lời mời"
        end
    else Từ chối / thu hồi môn
        QTV->>V: POST tu_choi, ly_do (bắt buộc)
        V->>S: tu_choi_mon(admin, mg, ly_do)
        S->>DB: TU_CHOI, ghi_chu_duyet
        opt Môn đang DA_DUYET (thu hồi)
            S->>S: huy_loi_moi_cua_gia_su(user, "Bị thu hồi môn", mon)
            Note right of S: Vô hiệu lời mời môn đó, gỡ phân công lớp chưa mở khóa, hủy buổi học thử chưa học
        end
        opt Không còn môn DA_DUYET
            S->>DB: Hồ sơ → TAM_NGUNG
        end
        S->>EM: Email lý do + hướng dẫn gửi lại
    else Đổi trạng thái hồ sơ
        QTV->>V: POST HOAT_DONG / TAM_NGUNG
        V->>S: doi_trang_thai_ho_so(admin, ho_so, moi)
        alt HOAT_DONG mà chưa có môn duyệt
            S-->>UI: "Cần duyệt ít nhất 1 môn trước khi cho gia sư hoạt động."
        else TAM_NGUNG
            S->>S: huy_loi_moi_cua_gia_su(…)
        end
    end
    S->>DB: ghi_nhat_ky(admin, …)
```

| Tình huống | Kết quả |
|---|---|
| QTV bấm Duyệt 2 lần | Lần 2: "Môn … đã được duyệt rồi." |
| Gán lại Tuyển sinh phụ trách | `POST /gia-su/{pk}/nguoi-phu-trach/` [MỚI] – chỉ QTV, ghi nhật ký; buổi chưa kiểm tra chuyển `HauKiemBuoi.nguoi_phu_trach` sang người mới |
