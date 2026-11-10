# 15 · Khóa học: trạng thái, gia hạn, đổi gia sư

- **Màn hình:** `Tuyen sinh - Khoa hoc.dc.html` (danh sách + menu "…": Gia hạn thêm buổi, Đề xuất đổi gia sư, Sao chép SĐT phụ huynh) và `Tuyen sinh - Chi tiet khoa hoc.dc.html` (nút Đổi gia sư, Sửa số buổi, Đổi trạng thái ▾; tiến độ đã học / đã xếp / còn lại; danh sách buổi; dòng thời gian).
- **Code cũ:** `khoa_hoc.doi_trang_thai_khoa`, `ngoai_le.sua_so_buoi` (chỉ Admin), `ngoai_le.de_nghi_doi_gia_su / duyet_doi_gia_su / _thuc_hien_doi / nhan_lai_khoa`.

## SD-23 · Đổi trạng thái khóa (tạm dừng, tiếp tục, hoàn thành sớm, hủy)  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    participant UI as Chi tiet khoa hoc
    participant V as /khoa-hoc/{pk}/trang-thai/
    participant S as khoa_hoc.doi_trang_thai_khoa
    participant DB as DB KhoaHoc, BuoiHoc, YeuCauHocTap, LoiMoi, NhatKy
    participant ZM as Zoom
    participant EM as Email gia sư
    TS->>UI: Đổi trạng thái ▾ → chọn, nhập lý do
    UI->>V: POST moi, ly_do
    V->>S: doi_trang_thai_khoa(ts, khoa, moi, ly_do)
    alt Chuyển không hợp lệ (bảng CHUYEN_HOP_LE)
        S-->>UI: "Không chuyển được từ Đã hủy sang Đang học"
    else TAM_DUNG hoặc HUY
        S->>DB: UPDATE KhoaHoc WHERE trang_thai trong tập hợp lệ
        S->>DB: Buổi tương lai chiếm chỗ → DA_HUY (ADMIN_HUY, ghi chú "Khóa tạm dừng: …")
        S->>ZM: on_commit xoa_phong từng buổi
        opt HUY khi yêu cầu đang tìm gia sư mới
            S->>DB: YeuCau → DONG, LoiMoi CHO → VOIDED
        end
    else DANG_HOC (tiếp tục)
        S->>DB: Chỉ khi YeuCau = CHINH_THUC (không đang chờ gia sư mới)
    else HOAN_THANH (đánh dấu hoàn thành sớm) [MỚI]
        S->>DB: Chỉ từ DANG_HOC, hủy buổi tương lai, hoan_thanh_luc = now
    end
    S->>DB: ghi_nhat_ky(ts, "Đổi trạng thái khóa học", "cũ → mới. lý do, hủy N buổi sắp tới")
    S->>EM: Email gia sư
    V-->>UI: Banner theo trạng thái ("Khóa đang tạm dừng · Gia sư không tạo được buổi mới…")
```

| Tình huống | Kết quả |
|---|---|
| Buổi đã dạy nhưng chưa xác nhận khi tạm dừng/hủy | **Không** bị hủy (chỉ hủy `bat_dau > now`), gia sư vẫn xác nhận được |
| Hủy khóa | Không hoàn tác được (UI ghi rõ) |

## SD-24 · Gia hạn thêm buổi (Tuyển sinh) / sửa số buổi nhập nhầm (QTV)  [SỬA]

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    actor QTV as Quản trị viên
    participant V as /khoa-hoc/{pk}/sua-so-buoi/
    participant S as khoa_hoc.gia_han [MỚI] / ngoai_le.sua_so_buoi
    participant DB as DB KhoaHoc, GiaHanKhoa, NhatKy
    participant EM as Email gia sư
    alt Tuyển sinh gia hạn (phụ huynh đăng ký thêm)
        TS->>V: POST loai=GIA_HAN, so_buoi_them, hoc_phi_moi_buoi?, ly_do
        V->>S: gia_han(ts, khoa, so_buoi_them, ...)
        S->>S: so_buoi_them > 0, khóa DANG_HOC hoặc HOAN_THANH
        S->>DB: KhoaHoc.so_buoi_dang_ky += them, HOAN_THANH → DANG_HOC
        S->>DB: GiaHanKhoa(GIA_HAN, cu, moi, ly_do), xong NhacViec HOI_GIA_HAN
        S->>EM: "KH-0011 được gia hạn thêm 12 buổi"
    else QTV sửa nhập nhầm (giảm hoặc tăng)
        QTV->>V: POST loai=SUA_NHAP_NHAM, so_moi, ly_do (bắt buộc)
        V->>S: sua_so_buoi(admin, khoa, so_moi, ly_do)
        S->>S: so_moi ≥ đã học + đang lên lịch
        S->>DB: Cập nhật + tự đổi HOAN_THANH/DANG_HOC (code cũ)
        S->>DB: GiaHanKhoa(SUA_NHAP_NHAM)
    end
    S->>DB: ghi_nhat_ky
```

> Quyền: Tuyển sinh chỉ được **tăng** (gia hạn). Giảm số buổi = sửa dữ liệu đã khóa → chỉ QTV (giữ quy tắc phân vai).

## SD-25 · Đổi gia sư (chọn sẵn gia sư mới, Admin duyệt từ lần 2)  [SỬA lớn – Q2]

- **UI mới** (`Chi tiet khoa hoc` + `Quan tri - Can xem xet` mục "Duyệt đổi gia sư"): Tuyển sinh chọn **lý do**, chọn **gia sư mới** (gợi ý theo khớp khung giờ cố định, đã duyệt môn), **thù lao mới**, tick "Gia sư mới đã đồng ý (qua Zalo)". Khi thực hiện: **các buổi đã xếp lịch chuyển sang gia sư mới**; "Trong lúc chờ duyệt, các buổi vẫn do gia sư cũ dạy".
- **Khác code cũ:** cũ hủy buổi tương lai, tạm dừng khóa, đưa yêu cầu về Đang tìm, chờ ai đó Accept (`nhan_lai_khoa`). Luồng cũ vẫn giữ làm **phương án dự phòng** khi Tuyển sinh chưa tìm được người: chọn "Chưa có gia sư mới – mở lại tìm gia sư".

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    actor QTV as Quản trị viên
    participant UI as Chi tiet khoa hoc / Can xem xet
    participant S as ngoai_le.de_nghi_doi_gia_su [SỬA]
    participant DB as DB DoiGiaSu, KhoaHoc, BuoiHoc, YeuCauHocTap, NhatKy, ThongBao
    participant ZM as Zoom
    participant EM as Email
    TS->>UI: Đổi gia sư: lý do, gia sư mới, thù lao mới, tick đã đồng ý
    UI->>S: POST /khoa-hoc/{pk}/doi-gia-su/
    S->>S: Khóa DANG_HOC/TAM_DUNG, YeuCau CHINH_THUC, không có đề nghị CHO_DUYET khác
    S->>S: la_du_dieu_kien(gia_su_moi, mon), không tạm nghỉ, khác gia sư cũ
    S->>DB: da_doi = số DoiGiaSu DA_THUC_HIEN của khóa
    alt da_doi ≥ 1 và người làm không phải QTV
        S->>DB: DoiGiaSu(CHO_DUYET, gia_su_moi, thu_lao_moi)
        S->>DB: ThongBao QTV, ghi_nhat_ky "Đề nghị đổi gia sư (chờ duyệt)"
        S-->>UI: Banner "Đổi gia sư sang Nguyễn Hoài An · Chờ Admin duyệt. Trong lúc chờ, các buổi vẫn do cô Lan dạy"
        QTV->>UI: Cần xem xét → Duyệt (hoặc Từ chối + lý do bắt buộc)
        UI->>S: duyet_doi_gia_su(admin, dn, dong_y)
        alt Từ chối
            S->>DB: DoiGiaSu TU_CHOI, Email cho TS tạo đề nghị
        else Duyệt
            S->>S: _thuc_hien_doi(admin, dn)
        end
    else Lần đầu (hoặc QTV tự làm)
        S->>S: _thuc_hien_doi(ts, dn)
    end
    critical _thuc_hien_doi [SỬA] – transaction.atomic
        S->>DB: Buổi tương lai chiếm chỗ của gia sư cũ: kiểm tra trùng lịch với gia sư mới
        alt Có buổi trùng lịch gia sư mới
            S->>DB: Buổi đó → DA_HUY (ADMIN_HUY "Đổi gia sư – trùng lịch gia sư mới"), on_commit xóa Zoom
        end
        S->>DB: Buổi còn lại: gia_su = mới, thu_lao_du_kien = thu_lao_moi
        S->>DB: KhoaHoc.gia_su = mới, thu_lao_moi_buoi = thu_lao_moi (giữ DANG_HOC)
        S->>DB: YeuCauHocTap.gia_su = mới
        S->>DB: DoiGiaSu DA_THUC_HIEN, so_buoi_chuyen
        S->>DB: ghi_nhat_ky
    end
    S->>ZM: PATCH topic các phòng đã chuyển (tên gia sư mới) – lỗi chỉ ghi log
    S->>EM: Gia sư cũ: "Các buổi đã dạy vẫn tính thù lao…" · Gia sư mới: "Bạn nhận khóa KH-0005, N buổi đã xếp"
    S->>DB: ThongBao Tuyển sinh: "Báo phụ huynh và đổi nhóm Zalo"
```

| Tình huống | Kết quả |
|---|---|
| Buổi đã dạy, chưa xác nhận của gia sư cũ | Không chuyển (chỉ buổi `bat_dau > now`); gia sư cũ vẫn xác nhận và nhận thù lao |
| Thù lao các buổi cũ | Không đổi (đã chụp `thu_lao_du_kien` lúc tạo/hoàn tất) |
| Gia sư mới bị khóa trong lúc chờ duyệt | Duyệt bị chặn: "Gia sư mới không còn đủ điều kiện" → TS tạo đề nghị khác |
| Chọn "Chưa có gia sư mới" | Chạy luồng cũ: hủy buổi tương lai, khóa TAM_DUNG, yêu cầu → DANG_TIM, mời gia sư (SD-07); người Accept nhận lại khóa (`nhan_lai_khoa`) |
