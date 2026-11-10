# 10 · Tài khoản, đăng nhập, mời gia sư

## SD-01 · Đăng nhập theo vai trò  [SỬA]

- **Màn hình:** `Dang nhap.dc.html` → trang chủ theo vai trò.
- **Code cũ:** `chung.DangNhapView` (LoginView), `DangNhapForm.clean()`, `ChanTaiKhoanBiKhoaMiddleware`.
- **Thêm:** cờ `phai_doi_mat_khau`, ghi nhật ký đăng nhập thất bại nhiều lần (tùy chọn), thông báo rõ khi tài khoản bị khóa.

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant UI as Dang nhap
    participant V as /dang-nhap/ DangNhapView
    participant DB as DB User, NhatKy
    U->>UI: Nhập email/tên đăng nhập + mật khẩu
    UI->>UI: Kiểm tra rỗng phía client
    UI->>V: POST username, password, csrf
    V->>DB: authenticate()
    alt Sai mật khẩu / không tồn tại
        V-->>UI: Lỗi chung "Sai tên đăng nhập hoặc mật khẩu" (không nói rõ cái nào sai)
    else Tài khoản bị khóa (is_active=False)
        V-->>UI: "Tài khoản đã bị khóa: {ly_do_khoa}. Liên hệ Quản trị viên"
    else Hợp lệ
        V->>DB: login() cập nhật last_login
        alt phai_doi_mat_khau = True
            V-->>U: 302 /doi-mat-khau/?bat_buoc=1
        else Gia sư
            V-->>U: 302 / (Trang chu Gia su v2)
        else Tuyển sinh
            V-->>U: 302 / (Trang chu Tuyen sinh)
        else Quản trị viên
            V-->>U: 302 / (Trang chu Quan tri vien)
        end
    end
```

| Tình huống | Kết quả |
|---|---|
| Đang đăng nhập thì bị Admin khóa | Request kế tiếp: middleware xóa phiên, về trang đăng nhập với thông báo (đã có) |
| Đã đăng nhập mà mở `/dang-nhap/` | `redirect_authenticated_user` → về trang chủ (đã có) |
| Truy cập trang không đúng vai trò | 403 `templates/403.html` (đã có `vai_tro_required`) |

## SD-02 · Đổi mật khẩu bắt buộc lần đầu  [MỚI]

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng mới
    participant MW as Middleware BatDoiMatKhau [MỚI]
    participant V as /doi-mat-khau/
    participant DB as DB User, NhatKy
    U->>MW: GET bất kỳ trang nào
    alt user.phai_doi_mat_khau
        MW-->>U: 302 /doi-mat-khau/ (trừ chính trang này và /dang-xuat/)
    end
    U->>V: POST mật khẩu cũ (tạm), mật khẩu mới x2
    alt Không đạt AUTH_PASSWORD_VALIDATORS hoặc trùng mật khẩu tạm
        V-->>U: Lỗi cạnh ô nhập
    else Hợp lệ
        V->>DB: set_password, phai_doi_mat_khau=False, update_session_auth_hash
        V->>DB: ghi_nhat_ky(user, "Đổi mật khẩu")
        V-->>U: 302 trang chủ + "Đã đổi mật khẩu"
    end
```

## SD-03 · Quản trị viên tạo, khóa, đặt lại mật khẩu tài khoản  [SỬA]

- **Màn hình:** `Quan tri - Tai khoan.dc.html` (drawer "Tạo tài khoản", menu "…" mỗi dòng).
- **Code cũ:** `views/tai_khoan.py` (`tao`, `sua`, `doi_trang_thai`), `TaoTaiKhoanForm`. Chưa có service riêng → tạo `services/tai_khoan.py`.

```mermaid
sequenceDiagram
    autonumber
    actor QTV
    participant UI as Quan tri - Tai khoan
    participant V as /tai-khoan/...
    participant S as services.tai_khoan [MỚI]
    participant DB as DB User, HoSoGiaSu, NhatKy
    participant EM as Email
    rect rgb(240,244,255)
    Note over QTV,EM: Tạo tài khoản
    QTV->>UI: Drawer: họ tên, email, SĐT, vai trò, tick "Gửi email mật khẩu"
    UI->>V: POST /tai-khoan/tao/
    V->>S: tao(admin, du_lieu)
    alt Email đã tồn tại
        S-->>UI: errors.email = "Email này đã có tài khoản."
    else Hợp lệ
        S->>S: Sinh mật khẩu tạm 10 ký tự (bỏ ký tự dễ nhầm 0/O/1/l)
        S->>DB: User(phai_doi_mat_khau=True)
        opt vai trò = GIA_SU
            S->>DB: HoSoGiaSu(trang_thai=CHO_DUYET, nguoi_moi=null)
        end
        S->>DB: ghi_nhat_ky(admin, "Tạo tài khoản", email)
        opt tick gửi email
            S->>EM: gui_email(mật khẩu tạm + link đăng nhập)
        end
        S-->>UI: Bước "Tạo tài khoản thành công" + nút sao chép mật khẩu tạm
    end
    end
    rect rgb(255,244,240)
    Note over QTV,EM: Khóa tài khoản (có Hoàn tác 6 giây)
    QTV->>UI: Menu … → Khóa → nhập lý do
    UI->>UI: Toast "Đã khóa … · Hoàn tác" (chưa gửi request trong 6 giây)
    alt Bấm Hoàn tác
        UI->>UI: Hủy, không gọi server
    else Hết 6 giây
        UI->>V: POST /tai-khoan/{pk}/doi-trang-thai/ khoa=1, ly_do
        V->>S: khoa(admin, user, ly_do)
        alt Tự khóa chính mình hoặc thiếu lý do
            S-->>UI: Lỗi
        else
            S->>DB: is_active=False, ly_do_khoa, khoa_luc
            opt user là gia sư
                S->>S: yeu_cau.huy_loi_moi_cua_gia_su(user, "Tài khoản bị khóa")
                Note right of S: Vô hiệu lời mời đang chờ, gỡ phân công lớp chưa mở khóa (code cũ)
            end
            S->>DB: ghi_nhat_ky(admin, "Khóa tài khoản", ly_do)
        end
    end
    end
    rect rgb(240,255,248)
    Note over QTV,EM: Đặt lại mật khẩu
    QTV->>V: POST /tai-khoan/{pk}/dat-lai-mat-khau/
    V->>S: dat_lai_mat_khau(admin, user)
    S->>DB: set_password(tam), phai_doi_mat_khau=True
    S->>EM: Email mật khẩu tạm
    S->>DB: ghi_nhat_ky
    S-->>UI: Hộp thoại hiện mật khẩu tạm + nút sao chép
    end
```

## SD-04 · Tuyển sinh mời gia sư đăng ký qua link  [MỚI]

- **Màn hình:** `Tuyen sinh - Gia su.dc.html` nút "Mời gia sư đăng ký"; trang đăng ký công khai `/dang-ky-gia-su/<ma>/` (cần thêm template, dùng lại khung `Dang nhap`).
- **Ý nghĩa:** gắn `HoSoGiaSu.nguoi_moi` → người này hậu kiểm các buổi của gia sư (SD-21).

```mermaid
sequenceDiagram
    autonumber
    actor TS as Tuyển sinh
    actor GS as Gia sư (chưa có TK)
    participant UI as Tuyen sinh - Gia su
    participant API as /api/ma-moi/
    participant P as /dang-ky-gia-su/{ma}/
    participant S as services.gia_su
    participant DB as DB MaMoiGiaSu, User, HoSoGiaSu, ThongBao
    participant EM as Email
    TS->>UI: Bấm "Mời gia sư đăng ký"
    UI->>API: POST
    API->>S: tao_ma_moi(ts)
    S->>DB: MaMoiGiaSu(ma ngẫu nhiên, tuyen_sinh=ts) hoặc dùng lại mã đang mở
    API-->>UI: data.url → copy clipboard, toast "Đã sao chép đường dẫn đăng ký"
    TS-->>GS: Gửi link qua Zalo (ngoài hệ thống)
    GS->>P: Mở link
    alt Mã không tồn tại / đã tắt / hết hạn
        P-->>GS: Trang báo "Link mời không còn hiệu lực"
    else Hợp lệ
        GS->>P: POST họ tên, email, SĐT, mật khẩu, trường/học vấn
        P->>S: dang_ky_tai_khoan(ma, du_lieu)
        alt Email đã có tài khoản
            S-->>GS: Lỗi email
        else
            S->>DB: User(vai_tro=GIA_SU), HoSoGiaSu(CHO_DUYET, nguoi_moi=ts, ma_moi)
            S->>DB: ghi_nhat_ky(None, "Gia sư đăng ký qua link mời", ma)
            S->>DB: ThongBao cho ts + mọi QTV "Có hồ sơ gia sư mới chờ duyệt"
            S->>EM: Email chào mừng gia sư
            S-->>GS: Đăng nhập luôn → /ho-so/ (bước tiếp: đăng ký môn, SD-27)
        end
    end
```

| Tình huống | Kết quả |
|---|---|
| Gia sư do Admin tạo tay (SD-03) | `nguoi_moi = null` → Admin gán người phụ trách ở trang Hồ sơ gia sư; trong lúc chưa gán, **mọi Tuyển sinh** thấy buổi của gia sư này ở Hậu kiểm |
| Tuyển sinh nghỉ việc (bị khóa) | Admin chuyển `nguoi_moi` của các gia sư sang người khác (thao tác hàng loạt ở trang Tài khoản, ghi nhật ký) |
