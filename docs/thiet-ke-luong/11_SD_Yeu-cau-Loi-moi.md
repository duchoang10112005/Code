# 11 · Yêu cầu học tập và lời mời nhận lớp

Code cũ: `services/yeu_cau.py` (tiến trình 3.0 trên DFD: 3.1 tiếp nhận, 3.2 đề xuất, 3.3 gửi lời mời, 3.4 xử lý phản hồi).

## SD-05 · Tạo yêu cầu học tập (học viên mới hoặc đã có)  [SỬA]

- **Màn hình:** `Tuyen sinh - Tao yeu cau.dc.html` (form trong khung trắng, khung "Xem trước yêu cầu" bên phải, lưới 7 ngày × 4 khung giờ).
- **Thay đổi:** lưới khung giờ → `khung_mong_muon` (JSON) + tự điền `thu_mong_muon`, `lich_mong_muon`; học viên có `gioi_tinh`, `truong`, `tuyen_sinh_phu_trach`; preview đếm số gia sư phù hợp.

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Tuyen sinh - Tao yeu cau
    participant API as /api/hoc-vien/ , /api/yeu-cau/dem-gia-su/
    participant V as /yeu-cau/tao/ yeu_cau.tao
    participant S as services.yeu_cau
    participant DB as DB HocVien, YeuCauHocTap, NhatKy
    TS->>UI: Chọn "Học viên mới" hoặc "Đã có trong hệ thống"
    opt Đã có trong hệ thống
        UI->>API: GET /api/hoc-vien/?q=tên hoặc SĐT
        API->>DB: HocVien ho_ten/sdt icontains (bỏ dấu, bỏ khoảng trắng)
        API-->>UI: Danh sách gợi ý (tên, lớp, yêu cầu trước, phụ huynh)
    end
    TS->>UI: Chọn môn, cấp độ, mục tiêu, bấm ô lưới khung giờ, phụ huynh, SĐT
    UI->>UI: Cập nhật "Xem trước": đánh dấu mục đã điền
    UI->>API: GET dem-gia-su?mon&cap_do&khung (debounce 400ms)
    API->>S: de_xuat_gia_su(yc tạm) chỉ đếm
    API-->>UI: "Có 4 gia sư phù hợp"
    TS->>UI: Tạo yêu cầu (Ctrl+Enter)
    UI->>V: POST form
    V->>V: HocVienForm.clean_sdt_phu_huynh() chuẩn hóa 84xxxxxxxxx
    alt Thiếu mục bắt buộc / SĐT sai / không chọn khung giờ
        V-->>UI: Hộp lỗi đầu form "Còn N mục cần sửa" + lỗi cạnh từng ô
    else Hợp lệ
        V->>S: tao_yeu_cau(ts, hoc_vien, du_lieu)
        critical transaction.atomic
            S->>DB: HocVien.create (nếu mới, tuyen_sinh_phu_trach=ts)
            S->>DB: YeuCauHocTap(MOI, khung_mong_muon, thu_mong_muon, lich_mong_muon)
            S->>DB: ghi_nhat_ky(ts, "Tiếp nhận yêu cầu học tập")
        end
        V-->>UI: 302 /yeu-cau/{pk}/ + "Đã tiếp nhận YC-0031. Chọn gia sư bên dưới để gửi lời mời."
    end
```

| Tình huống | Kết quả |
|---|---|
| SĐT có `+84`, khoảng trắng | Chuẩn hóa về `84912345678`; hiển thị lại dạng `0912 345 678` |
| Học viên đã có, chọn rồi bấm "Đổi" | Bỏ chọn, quay lại ô tìm |
| Học viên đã có đang có yêu cầu mở cùng môn | Cảnh báo (không chặn): "Võ Khánh Linh đã có YC-0029 môn Toán đang mời gia sư" |

## SD-06 · Đề xuất gia sư có điểm khớp  [SỬA]

- **Màn hình:** `Tuyen sinh - Chi tiet yeu cau.dc.html` – bảng "Gia sư được đề xuất" (điểm 94/86/78…, chip Đúng môn / Đúng cấp độ / Trùng 3/3 giờ / Đang nhận lớp).
- **Code cũ:** `de_xuat_gia_su(yc)` sắp xếp theo số **thứ** trùng, số khóa đang dạy, tên. **Sửa:** tính theo **khung giờ** và trả điểm 0–100.

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant V as /yeu-cau/{pk}/ chi_tiet
    participant S as yeu_cau.de_xuat_gia_su
    participant DB as DB HoSoGiaSu, MonGiaSu, LichRanh, KhoaHoc, LoiMoi
    TS->>V: GET
    V->>S: quet_loi_moi_het_han() rồi de_xuat_gia_su(yc)
    S->>DB: gia_su_du_dieu_kien(mon): HOAT_DONG, is_active, môn DA_DUYET
    S->>DB: loại tam_nghi_den >= hôm nay (vẫn trả về, gắn cờ "Tạm nghỉ")
    loop Mỗi gia sư
        S->>S: dung_cap_do = cấp độ yêu cầu thuộc cap_do_duyet
        S->>S: trung = |khung_mong_muon ∩ khung rảnh| / |khung_mong_muon|
        S->>S: so_khoa DANG_HOC so với so_lop_toi_da
        S->>S: diem = 40 đúng môn + 20 đúng cấp độ + 30 x trung + 10 nếu còn chỗ
    end
    S-->>V: Sắp xếp diem giảm dần, kèm lời mời gần nhất của từng gia sư
    V-->>TS: Bảng đề xuất, chip lý do, "Khớp nhất" cho điểm cao nhất, ô tick bị khóa nếu đang có lời mời chờ hoặc tạm nghỉ
```

> Điểm chỉ để **sắp xếp và giải thích** (không AI – PB-05). Lưu lại `diem_khop`, `chi_tiet_khop` vào `LoiMoi` lúc gửi (SD-07) để sau này đối chiếu.

## SD-07 · Gửi lời mời / mời thêm  [SỬA nhỏ]

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Tuyen sinh - Chi tiet yeu cau
    participant V as /yeu-cau/{pk}/gui-loi-moi/
    participant S as yeu_cau.gui_loi_moi
    participant DB as DB LoiMoi, YeuCauHocTap, NhatKy, ThongBao
    participant EM as Email
    TS->>UI: Tick N gia sư → "Gửi lời mời (N)" hoặc "Mời thêm"
    UI->>V: POST gia_su_ids[]
    V->>S: gui_loi_moi(ts, yc, ids)
    S->>DB: quet_loi_moi_het_han()
    critical transaction.atomic
        S->>DB: Kiểm tra lại yc.trang_thai in (MOI, DANG_TIM)
        loop Mỗi gia sư còn đủ điều kiện, chưa có lời mời CHO
            S->>DB: LoiMoi(CHO, het_han_luc = now + 24h, diem_khop, chi_tiet_khop) trong savepoint
            Note right of DB: UniqueConstraint "một lời mời đang chờ / gia sư / yêu cầu" chặn 2 TS bấm cùng lúc
        end
        S->>DB: yc MOI → DANG_TIM (update có điều kiện)
        S->>DB: ghi_nhat_ky(ts, "Gửi lời mời nhận lớp")
    end
    S->>DB: ThongBao cho từng gia sư
    S->>EM: gui_email từng gia sư (link /loi-moi/, hạn 24h)
    S-->>V: (moi, bo_qua)
    V-->>UI: "Đã gửi 3 lời mời · hết hạn sau 24 giờ" + (nếu có) "Bỏ qua 1 gia sư: đang có lời mời chờ hoặc không còn đủ điều kiện"
```

| Tình huống | Kết quả |
|---|---|
| Không chọn ai | "Hãy chọn ít nhất một gia sư." |
| Yêu cầu vừa được nhận / đóng ở tab khác | "Chỉ gửi lời mời cho yêu cầu đang Mới hoặc Đang mời gia sư." |
| Gia sư vừa bị thu hồi môn | Bị lọc khỏi `hop_le`, đếm vào `bo_qua` |
| Gửi email lỗi | Lời mời vẫn tạo; `NhatKyGuiTin(thanh_cong=False)`; gia sư vẫn thấy chuông + trang Lời mời |

## SD-08 · Gia sư nhận hoặc từ chối lời mời ("Accept hợp lệ đầu tiên thắng")  [SỬA]

- **Màn hình:** `Gia su - Loi moi nhan lop.dc.html` (danh sách bên trái, chi tiết bên phải: đếm ngược, lưới khớp giờ, mục tiêu, ghi chú phụ huynh, thù lao/buổi; nhận lớp phải tick cam kết; từ chối phải chọn lý do).
- **Thêm:** `cam_ket`, `ghi_chu_gia_su`, lý do từ chối bắt buộc; thông báo cho Tuyển sinh; thù lao/buổi lấy từ đâu → **đề xuất** `YeuCauHocTap.thu_lao_du_kien` [MỚI, nhập khi tạo yêu cầu, có thể để trống = "Thỏa thuận khi mở khóa"].

```mermaid
sequenceDiagram
    autonumber
    actor GS1 as Gia sư A
    actor GS2 as Gia sư B
    participant UI as Gia su - Loi moi nhan lop
    participant V as /loi-moi/{pk}/nhan/
    participant S as yeu_cau.chap_nhan
    participant DB as DB LoiMoi, YeuCauHocTap, KhoaHoc, NhatKy, ThongBao
    participant EM as Email
    GS1->>UI: Mở lời mời, đọc chi tiết, tick "Tôi cam kết…", ghi chú (tùy chọn)
    GS2->>UI: Cùng lúc mở lời mời cùng yêu cầu
    par Hai người bấm "Nhận lớp" gần như cùng lúc
        GS1->>V: POST cam_ket=1
        GS2->>V: POST cam_ket=1
    end
    V->>S: chap_nhan(GS1, lm1)
    S->>DB: la_du_dieu_kien(GS1, mon)?
    critical transaction.atomic (GS1)
        S->>DB: UPDATE LoiMoi SET ACCEPTED WHERE pk=lm1 AND CHO AND het_han_luc > now  → 1 dòng
        S->>DB: UPDATE YeuCau SET DA_PHAN_CONG, gia_su=GS1 WHERE DANG_TIM AND gia_su IS NULL → 1 dòng
        S->>DB: UPDATE LoiMoi khác của yêu cầu: CHO → VOIDED
        S->>DB: nhan_lai_khoa(GS1, yc) nếu yêu cầu đã có khóa (luồng đổi gia sư cũ)
        S->>DB: ghi_nhat_ky(GS1, "Nhận lớp (Accept)")
    end
    S->>DB: ThongBao + EM cho yc.tao_boi "YC-0029 đã có gia sư nhận"
    S-->>GS1: "Bạn đã nhận lớp Toán 8 – Võ Khánh Linh. Bước tiếp: Tuyển sinh chốt lớp"
    V->>S: chap_nhan(GS2, lm2)
    S->>DB: UPDATE LoiMoi lm2 WHERE CHO → 0 dòng (đã bị VOIDED ở bước trên)
    S-->>GS2: "Lời mời đã vô hiệu. Một gia sư khác đã nhận lớp này trước (lúc 11:46)"
```

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Gia su - Loi moi nhan lop
    participant V as /loi-moi/{pk}/tu-choi/
    participant S as yeu_cau.tu_choi
    participant DB as DB LoiMoi, YeuCauHocTap, NhatKy, ThongBao
    GS->>UI: "Từ chối" → hộp thoại chọn lý do (bắt buộc), ghi thêm
    UI->>V: POST ly_do
    V->>S: tu_choi(gs, lm, ly_do)
    S->>DB: UPDATE LoiMoi SET REJECTED WHERE CHO AND chưa hết hạn
    alt 0 dòng
        S-->>UI: "Lời mời không còn hiệu lực."
    else
        S->>DB: ghi_nhat_ky
        opt Yêu cầu không còn lời mời CHO nào
            S->>DB: ThongBao cho Tuyển sinh "YC-0027 cần mời thêm gia sư"
        end
        S-->>UI: Trạng thái "Đã từ chối", không mở lại được
    end
```

| Tình huống | Kết quả |
|---|---|
| Hết 24h mà chưa phản hồi | `quet_loi_moi_het_han()` → `HET_HAN` (chạy khi mở trang + tác vụ định kỳ); UI đếm ngược chạy về 0 thì tự đổi nhãn "Hết hạn", nút bị khóa |
| Không tick cam kết | Lỗi tại ô tick, không gửi request |
| Gia sư bị thu hồi môn trong lúc lời mời còn chờ | Lời mời đã bị `VOIDED` bởi `huy_loi_moi_cua_gia_su`; nếu còn sót thì `la_du_dieu_kien` chặn: "Bạn chưa đủ điều kiện nhận lớp môn này" |
| Đã kín lịch (`so_khoa ≥ so_lop_toi_da`) | Cảnh báo (không chặn) "Bạn đang dạy 4/4 lớp", lý do từ chối gợi ý "Đã đủ số lớp đang dạy" |

## SD-09 · Đóng yêu cầu (có Hoàn tác)  [SỬA nhỏ]

- **Màn hình:** `Tuyen sinh - Yeu cau hoc tap.dc.html` (menu "…" → Đóng yêu cầu → chọn lý do), `Tuyen sinh - Chi tiet yeu cau.dc.html`.

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Yeu cau hoc tap
    participant V as /yeu-cau/{pk}/dong/
    participant S as yeu_cau.dong_yeu_cau
    participant DB as DB YeuCauHocTap, LoiMoi, NhatKy
    TS->>UI: Đóng YC-0029, chọn lý do
    alt Chưa chọn lý do
        UI-->>TS: "Vui lòng chọn lý do đóng yêu cầu."
    else
        UI->>UI: Dòng đổi sang "Đã đóng" tạm thời + toast "Hoàn tác" 6 giây
        alt Bấm Hoàn tác trong 6 giây
            UI->>UI: Khôi phục dòng, KHÔNG gửi request
        else Hết 6 giây
            UI->>V: POST ly_do
            V->>S: dong_yeu_cau(ts, yc, ly_do)
            S->>DB: UPDATE yc SET DONG WHERE trang_thai IN (MOI, DANG_TIM)
            alt 0 dòng (đã có gia sư nhận trong lúc chờ)
                S-->>UI: Toast lỗi "Chỉ đóng được yêu cầu chưa có gia sư" + tải lại dòng
            else
                S->>DB: LoiMoi CHO → VOIDED, ghi_nhat_ky
            end
        end
    end
```

> Hoàn tác **phía client** (trì hoãn gửi) đơn giản và an toàn hơn "đảo ngược" ở server, vì đóng yêu cầu đã vô hiệu lời mời và không khôi phục được. Áp dụng cùng cách cho khóa tài khoản (SD-03).
