# 13 · Buổi học: tạo → vào lớp → đánh giá → hoàn tất

Code cũ: `services/buoi_hoc.py` (tiến trình 5.0). Ba màn hình gia sư dùng chung một quy trình và cùng khung thông tin buổi (mã buổi, lớp, học viên, ngày giờ, thời lượng, link lớp cố định, Zoom ID, host key, tin nhắn Zalo):

`Gia su - Tao buoi hoc v2` → `Gia su - Chi tiet buoi hoc v2` (đánh giá + xác nhận) → nhật ký buổi học.

## SD-13 · Tạo một hoặc nhiều buổi học + phòng Zoom + tin nhắn Zalo  [SỬA lớn]

- **Màn hình:** `Gia su - Tao buoi hoc v2.dc.html`: chọn lớp (thẻ khóa học có "Lịch cố định T4 20:00 · T7 08:00", tiến độ đã học/đã xếp/còn), chọn ngày trên lịch + giờ, **lặp hằng tuần N buổi**, hoặc **học bù** cho một buổi đã hủy; kiểm tra từng buổi trước khi tạo; sau khi tạo hiện thẻ kết quả từng buổi (Đã tạo phòng / Lỗi Zoom – Thử lại), nút **"Đánh giá buổi học"**, sao chép link lớp, Zoom ID, tin nhắn Zalo.
- **Code cũ:** chỉ tạo 1 buổi (`tao_buoi_chinh_thuc` / `tao_buoi_hoc_thu`). **Thêm** `kiem_tra_ke_hoach()` và `tao_nhieu_buoi()` gọi lại 2 hàm cũ trong vòng lặp.

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Gia su - Tao buoi hoc v2
    participant API as /api/buoi-hoc/kiem-tra-lich/
    participant V as /buoi-hoc/tao/
    participant S as services.buoi_hoc
    participant DB as DB KhoaHoc, YeuCauHocTap, BuoiHoc, TaiKhoanZoom, NhatKy
    participant ZM as Zoom API
    GS->>UI: Chọn lớp (khoa_co_the_xep + yeu_cau_co_the_hoc_thu)
    UI->>UI: Gợi ý ngày theo lich_co_dinh, hiện "Còn N buổi chưa xếp"
    GS->>UI: Chọn ngày, giờ, lặp 3 tuần (hoặc chọn buổi cần bù)
    UI->>API: POST lop, ke_hoach[{bat_dau}], hoc_bu_cho?
    API->>S: kiem_tra_ke_hoach(gs, lop, ke_hoach)
    loop Mỗi buổi dự kiến
        S->>S: quá khứ? quá 60 ngày?
        S->>DB: Trùng buổi của chính gia sư? (BuoiHoc chiếm chỗ giao nhau)
        S->>DB: Số buổi giao nhau ≥ số host Zoom đang bật?
        S->>DB: Ngoài giờ rảnh đã đăng ký? (chỉ cảnh báo)
        S->>S: Vượt so_buoi_co_the_xep của khóa?
    end
    S-->>UI: Mỗi buổi: OK / chặn (lý do) / cảnh báo + nhãn "Buổi 6/16"
    UI-->>GS: "Sẵn sàng tạo 3 buổi" hoặc "1 buổi bị trùng… Đổi ngày hoặc giờ để tiếp tục"
    GS->>V: POST Tạo buổi
    V->>S: tao_nhieu_buoi(gs, lop, ke_hoach, hoc_bu_cho)
    loop Mỗi buổi (mỗi buổi 1 transaction riêng, buổi lỗi không kéo buổi khác)
        S->>S: kiem_tra_khung_gio() lần cuối (chống người khác vừa chiếm giờ)
        S->>DB: BuoiHoc(LOI_ZOOM, han_xac_nhan = kết thúc + 12h, thu_lao_du_kien, ket_thuc_luc, hoc_bu_cho)
        S->>DB: ghi_nhat_ky(gs, "Tạo buổi học")
        S->>DB: Chọn TaiKhoanZoom đang bật, không có buổi giao nhau
        S->>ZM: POST /users/{host}/meetings (topic, start_time, duration, auto_recording nếu PH đồng ý ghi hình)
        alt Zoom trả 201
            ZM-->>S: id, join_url, start_url, password
            S->>DB: zoom_* , tai_khoan_zoom, trang_thai = DA_LEN_LICH
        else Lỗi mạng / hết quota / sai khóa
            ZM-->>S: ZoomError
            S->>DB: trang_thai = LOI_ZOOM, zoom_loi
            S->>DB: YeuCauXuLy(SU_CO_ZOOM) nếu thử lại thất bại ≥ 2 lần
        end
    end
    S-->>V: danh sách buổi đã tạo
    V-->>UI: Thẻ kết quả từng buổi: mã BH, "Đã tạo phòng" hoặc "Lỗi Zoom · Thử lại"
    GS->>UI: "Sao chép tin nhắn Zalo"
    UI->>API: GET /api/buoi-hoc/{pk}/tin-nhan-lop/
    API->>S: noi_dung_moi_vao_lop(buoi)
    S-->>UI: Topic, giờ, link lớp cố định /lop/KH-0005, Meeting ID, passcode
    UI-->>GS: Toast "Đã sao chép tin nhắn. Dán vào nhóm Zalo của lớp"
```

**Mẫu tin nhắn** (`noi_dung_moi_vao_lop`): `Topic: Buổi dạy KH-0005 - IELTS (Buổi 6/16 · Học bù) của gia sư Phạm Ngọc Lan và học viên Trần Gia Bảo vào 08:00 T7 14/11/2026` · `Vào lớp: https://giasuonline.vn/lop/KH-0005` · `Meeting ID: 845 1209 3377` · `Passcode: ……` · `Phòng mở trước 10 phút.` – **không** chứa host key, học phí, SĐT phụ huynh.

| Tình huống | Kết quả |
|---|---|
| Khóa đã xếp đủ số buổi | Chặn: "Khóa đã xếp đủ số buổi đăng ký" (trừ học bù / dời lịch có `thay_the_cho`) |
| Khóa `TAM_DUNG` / `HUY` | Không hiện trong danh sách lớp; gọi trực tiếp → "Khóa đang ở trạng thái …" |
| Yêu cầu `dang_ky_thang` | Không cho tạo buổi học thử (SD-10) |
| 3 buổi, buổi thứ 2 Zoom lỗi | Buổi 1, 3 `DA_LEN_LICH`; buổi 2 `LOI_ZOOM` có nút Thử lại; nếu tới giờ vẫn lỗi → tự hủy `LOI_ZOOM` (SD-36) |
| Học bù | `hoc_bu_cho` trỏ buổi đã hủy lý do `HOC_VIEN_HUY`/`GIA_SU_HUY`; mỗi buổi hủy chỉ được bù 1 lần (OneToOne) |
| Buổi ngoài giờ rảnh | Cho tạo, cảnh báo vàng "Ngoài giờ rảnh đã đăng ký. Vẫn tạo được, nhớ thống nhất với phụ huynh." |

## SD-14 · Vào lớp: link cố định, mở trước 10′, đóng sau 5′  [MỚI]

- **Màn hình:** khung Zoom trên `Gia su - Chi tiet buoi hoc v2` ("Phòng Zoom đã sẵn sàng", nút "Mở phòng Zoom", host key che `••••••` + nút hiện), trang chủ gia sư "Mở phòng Zoom buổi tiếp theo"; học viên/phụ huynh bấm link cố định `/lop/<ma_lop>/` trong nhóm Zalo.

```mermaid
sequenceDiagram
    autonumber
    actor HV as Học viên / Phụ huynh
    actor GS as Gia sư
    participant L as /lop/{ma_lop}/ [MỚI, công khai]
    participant V as /buoi-hoc/{pk}/mo-phong/
    participant S as services.buoi_hoc
    participant DB as DB KhoaHoc, BuoiHoc
    participant ZM as Zoom API
    participant SCH as quet_dinh_ky
    HV->>L: Mở link cố định của lớp
    L->>S: buoi_dang_mo(ma_lop, now)
    S->>DB: Buổi DA_LEN_LICH của khóa có bat_dau - 10′ ≤ now ≤ ket_thuc + 5′
    alt Có buổi trong cửa sổ
        L-->>HV: 302 zoom_join_url
    else Chưa tới giờ
        L-->>HV: Trang chờ "Buổi tiếp theo: T7 14/11 08:00 · phòng mở lúc 07:50" (tự tải lại mỗi 60 giây)
    else Không còn buổi
        L-->>HV: "Lớp chưa có buổi sắp tới. Liên hệ trung tâm."
    end
    GS->>V: Bấm "Mở phòng Zoom"
    alt Sớm hơn 10′ trước giờ học
        V-->>GS: "Phòng mở lúc 07:50"
    else Trong cửa sổ
        V->>ZM: GET /meetings/{id} lấy start_url mới (link cũ chỉ sống ~2 giờ)
        V-->>GS: 302 start_url (gia sư vào với quyền host)
    end
    SCH->>DB: Buổi kết thúc cách đây ≥ 5′ mà chưa đóng phòng
    SCH->>ZM: PUT /meetings/{id}/status action=end
    SCH->>DB: phong_dong_luc = now
```

| Tình huống | Kết quả |
|---|---|
| Gia sư mở bằng tài khoản Zoom cá nhân thay vì link host | Host key giúp gia sư "Claim host"; hậu kiểm nhận diện host qua email tài khoản host (code cũ `_thong_tin_host`) |
| Zoom lỗi khi lấy start_url | Báo "Không lấy được link mở phòng" + nút "Báo sự cố" → `YeuCauXuLy(SU_CO_ZOOM)` |
| Hai lớp chung 1 host liền giờ | Bị chặn từ lúc tạo buổi (SD-13) nên không xảy ra |

## SD-15 · Phiếu đánh giá tự lưu nháp  [MỚI]

- **Màn hình:** `Gia su - Chi tiet buoi hoc v2` – phiếu mở **sau giờ kết thúc**: Nội dung đã dạy* · Mức tiếp thu* (3 thẻ) · Nhận xét gửi phụ huynh* (≥ 30 ký tự) · Bài tập về nhà · Ghi chú cho Tuyển sinh · công tắc "Gửi nhận xét qua Zalo"; đồng hồ "Xác nhận hoàn tất trước 21:30 hôm nay", "Đủ 3/3 mục bắt buộc", "Đã lưu nháp 21:04".

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Chi tiet buoi hoc v2
    participant API as /api/buoi-hoc/{pk}/nhap/
    participant DB as DB BanNhapDanhGia
    GS->>UI: Gõ vào phiếu
    loop Mỗi 10 giây khi có thay đổi (và khi rời trang)
        UI->>API: POST du_lieu (JSON các ô)
        API->>API: Chỉ gia sư của buổi, buổi DA_LEN_LICH
        API->>DB: update_or_create(buoi, du_lieu)
        API-->>UI: luu_luc → "Đã lưu nháp 21:04"
    end
    Note over UI,DB: Mở lại trang → phiếu nạp lại từ BanNhapDanhGia. QTV dùng bản nháp này khi khôi phục sau lỗi hệ thống (SD-34)
```

## SD-16 · Xác nhận hoàn tất → số buổi, thù lao, Zalo phụ huynh  [SỬA]

- **Code cũ:** `xac_nhan_hoan_tat()` – giữ toàn bộ logic chống chạy đua; **sửa** form (thêm `muc_tiep_thu`, `bai_tap_ve_nha`, `ghi_chu_tuyen_sinh`, `gui_zalo_phu_huynh`), kiểm tra nhận xét ≥ 30 ký tự, xóa bản nháp, tạo `HauKiemBuoi` (chờ chấm).

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant UI as Chi tiet buoi hoc v2
    participant V as /buoi-hoc/{pk}/xac-nhan/
    participant S as buoi_hoc.xac_nhan_hoan_tat
    participant DB as DB BuoiHoc, KhoaHoc, ThuLao, DoiSoatThang, BanNhapDanhGia, HauKiemBuoi, NhatKy
    participant ZL as Zalo ZNS
    participant LOG as DB NhatKyGuiTin
    GS->>UI: "Xác nhận hoàn tất"
    UI->>UI: Kiểm tra 3 mục bắt buộc, nhận xét ≥ 30 ký tự
    UI->>V: POST phiếu đánh giá
    V->>S: xac_nhan_hoan_tat(gs, buoi, du_lieu)
    alt Không phải buổi của mình
        S-->>UI: 403 / "Đây không phải buổi học của bạn."
    else Trước giờ kết thúc
        S-->>UI: "Chỉ xác nhận được sau giờ kết thúc (09:30 11/11)."
    else Quá hạn xác nhận
        S-->>UI: "Đã quá hạn xác nhận…" + nút "Xin mở lại" (SD-19)
    else Hợp lệ
        critical transaction.atomic
            S->>DB: UPDATE BuoiHoc SET HOAN_TAT, xac_nhan_luc, phiếu WHERE pk AND DA_LEN_LICH
            alt 0 dòng (bấm 2 lần / tab khác đã xác nhận)
                S-->>UI: "Buổi học vừa được xác nhận hoặc thay đổi, vui lòng tải lại trang."
            end
            opt Buổi chính thức
                S->>DB: UPDATE KhoaHoc so_buoi_da_dung + 1 WHERE so_buoi_da_dung < so_buoi_dang_ky
                S->>DB: BuoiHoc.so_thu_tu = so_buoi_da_dung
                S->>DB: Đủ buổi → KhoaHoc HOAN_THANH, hoan_thanh_luc
                S->>DB: ThuLao(TAM_TINH, so_tien = thu_lao_du_kien, thang = thang_ghi_nhan())
                Note right of DB: thang_ghi_nhan: tháng đã chốt thì dồn sang tháng mở kế tiếp. OneToOne buoi_hoc chống tính trùng
            end
            S->>DB: Xóa BanNhapDanhGia, tạo HauKiemBuoi(CHUA_KIEM_TRA, nguoi_phu_trach)
            S->>DB: ghi_nhat_ky(gs, "Xác nhận hoàn tất buổi học", mức tiếp thu)
        end
        alt gui_zalo_phu_huynh = True
            S->>ZL: gui_zns(sdt_phu_huynh, template: tên HV, môn, giờ, gia sư, nội dung, đánh giá, nhận xét)
            alt OK
                S->>DB: zalo_trang_thai = DA_GUI
            else Lỗi (chưa có OA, sai template, mạng)
                S->>DB: zalo_trang_thai = LOI
            end
            S->>LOG: NhatKyGuiTin(ZALO, thanh_cong, phan_hoi)
        else Gia sư tắt gửi tự động
            S->>DB: zalo_trang_thai = CHUA_GUI (UI hiện nút "Sao chép nhận xét" để gửi tay)
        end
        V-->>UI: Hộp xanh "Đã xác nhận hoàn tất lúc 21:12. Thù lao buổi này đã vào bảng tạm tính tháng 11…"
    end
```

| Tình huống | Kết quả |
|---|---|
| Zalo lỗi | **Không** hoàn tác xác nhận; chip "Gửi lỗi" + nút "Gửi lại" (`POST /api/buoi-hoc/{pk}/gui-lai-zalo/`) |
| Khóa đã dùng hết số buổi (dữ liệu lệch) | Rollback cả transaction: "Khóa học đã dùng hết số buổi đăng ký." |
| Tháng của buổi đã chốt đối soát | Thù lao ghi vào tháng mở kế tiếp (code cũ đã có) |
| Lỗi 500 giữa chừng | Transaction rollback; bản nháp còn nguyên; middleware ghi `SuCoHeThong` + tạo `YeuCauXuLy(LOI_HE_THONG)` để QTV khôi phục (SD-34) và **không tính là quá hạn của gia sư** |

## SD-17 · Gia sư báo hủy buổi  [GIỮ + đổi cột ghi chú]

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant V as /buoi-hoc/{pk}/huy/
    participant S as buoi_hoc.huy_buoi
    participant DB as DB BuoiHoc, NhatKy, ThongBao
    participant ZM as Zoom
    GS->>V: POST ly_do (Gia sư hủy / Học viên xin nghỉ), ghi chú
    V->>S: huy_buoi(gs, buoi, ly_do, ghi_chu)
    alt Buổi đã bắt đầu
        S-->>V: "Buổi học đã bắt đầu, không hủy được nữa…"
    else
        S->>DB: UPDATE SET DA_HUY, ly_do_huy, ly_do_huy_ghi_chu WHERE trạng thái chiếm chỗ
        S->>DB: ghi_nhat_ky, ThongBao cho Tuyển sinh phụ trách khóa
        S->>ZM: on_commit xoa_phong
        S-->>V: Hộp "Đã báo hủy · Học viên xin nghỉ" + gợi ý "Tạo buổi học bù" (SD-13, hoc_bu_cho)
    end
```

## SD-18 · Dời lịch  [GIỮ]

`doi_lich()` = tạo buổi mới (`thay_the_cho`) **trước**, nếu thành công mới hủy buổi cũ (`DOI_LICH`) trong cùng transaction; phòng Zoom cũ chỉ bị xóa sau commit. Giữ nguyên code; UI gọi từ menu "Dời lịch" trên trang Chi tiết buổi học (chọn ngày giờ mới, dùng lại `kiem-tra-lich` của SD-13).

## SD-19 · Gia sư xin mở lại buổi tự hủy  [MỚI]

- **Màn hình:** `Gia su - Chi tiet buoi hoc v2` trạng thái "Buổi đã tự hủy · Quá hạn xác nhận" → nút "Xin mở lại" (lý do + minh chứng tùy chọn). QTV xử lý ở SD-33.

```mermaid
sequenceDiagram
    autonumber
    actor GS as Gia sư
    participant V as /buoi-hoc/{pk}/xin-mo-lai/ [MỚI]
    participant S as ngoai_le.gui_yeu_cau_xu_ly [MỚI]
    participant DB as DB BuoiHoc, YeuCauXuLy, NhatKy, ThongBao
    GS->>V: POST noi_dung "Tối hôm đó em bị sốt nên quên xác nhận…", minh_chung_url
    V->>S: gui_yeu_cau_xu_ly(gs, buoi, MO_LAI, ...)
    alt Buổi không phải DA_HUY + QUA_HAN
        S-->>V: "Chỉ xin mở lại buổi bị hệ thống tự hủy vì quá hạn xác nhận."
    else Quá 7 ngày từ hạn xác nhận
        S-->>V: "Buổi đã hủy quá 7 ngày, không mở lại được nữa."
    else Đã có yêu cầu đang chờ
        S-->>V: "Bạn đã gửi yêu cầu mở lại buổi này, đang chờ xử lý."
    else
        S->>DB: YeuCauXuLy(MO_LAI, CHO_XU_LY, han_xu_ly = han_xac_nhan + 7 ngày)
        S->>DB: ghi_nhat_ky(gs, "Xin mở lại buổi học")
        S->>DB: ThongBao cho mọi QTV
        S-->>V: "Đã gửi yêu cầu. Quản trị viên sẽ xem xét trước 10/11."
    end
```
