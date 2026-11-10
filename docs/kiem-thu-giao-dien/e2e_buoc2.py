"""Kiểm thử giao diện Bước 2 trên server e2e (cổng 8010, bản sao DB)."""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8010"
OUT = os.path.join(os.path.dirname(__file__), "anh_buoc2")
os.makedirs(OUT, exist_ok=True)
loi_console = []


def chup(page, ten):
    page.screenshot(path=os.path.join(OUT, ten + ".png"))
    print("  chụp", ten)


def kiem(dk, mo_ta):
    print(("  OK  " if dk else "  LỖI ") + mo_ta)
    if not dk:
        kiem.loi += 1


kiem.loi = 0

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and loi_console.append(m.text))
    page.on("pageerror", lambda e: loi_console.append(str(e)))

    print("1. Trang đăng nhập")
    page.goto(BASE + "/dang-nhap/")
    page.wait_for_load_state("networkidle")
    chup(page, "01_dang_nhap")
    kiem(page.locator("text=Ghi nhớ đăng nhập").is_visible(), "có ô ghi nhớ")
    page.click("text=Quên mật khẩu?")
    kiem(page.locator("#quen-mk").is_visible(), "bấm Quên mật khẩu hiện hộp liên hệ QTV")

    print("2. Bỏ trống → chặn ở client; sai mật khẩu → banner lỗi")
    page.click("button[type=submit]")
    kiem(page.url.endswith("/dang-nhap/"), "bỏ trống không gửi form")
    page.fill("#id_username", "tuyensinh@giasu.local")
    page.fill("#id_password", "saimatkhau")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    kiem(page.locator("text=Email hoặc mật khẩu chưa đúng").first.is_visible(), "banner sai mật khẩu")
    chup(page, "02_sai_mat_khau")

    print("3. Điền nhanh tài khoản mẫu Tuyển sinh, đăng nhập bằng email")
    page.click("button[data-dien=tuyensinh]")
    page.fill("#id_username", "tuyensinh@giasu.local")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    kiem(page.url.rstrip("/") == BASE, "đăng nhập bằng email vào trang chủ")

    print("4. Khung giao diện mới (trang Đổi mật khẩu)")
    page.goto(BASE + "/doi-mat-khau/")
    page.wait_for_load_state("networkidle")
    chup(page, "03_khung_tuyen_sinh")
    kiem(page.locator(".brand small", has_text="Bảng điều phối").is_visible(), "phụ đề vai trò Tuyển sinh")
    kiem(page.locator(".nav a.sap-co", has_text="Hậu kiểm").count() == 1, "Hậu kiểm hiện 'Sắp có'")
    kiem(page.locator(".dot-badge").inner_text() == "2", "chuông có 2 thông báo chưa đọc")

    print("5. Chuông thông báo")
    page.click("[data-mo-menu=menu-thong-bao]")
    page.wait_for_selector("[data-ds-thong-bao] a")
    chup(page, "04_chuong")
    kiem(page.locator("[data-ds-thong-bao] a").count() == 2, "danh sách 2 thông báo")
    page.click("[data-doc-het]")
    page.wait_for_timeout(500)
    kiem(page.locator(".dot-badge").count() == 0, "đánh dấu đã đọc → mất huy hiệu")
    page.keyboard.press("Escape")

    print("6. Ctrl+K")
    page.keyboard.press("Control+k")
    kiem(page.locator("#bang-lenh").is_visible(), "Ctrl+K mở bảng lệnh")
    kiem(page.locator("#bang-lenh .kq a").count() >= 3, "có lệnh nhanh")
    page.keyboard.type("minh anh")
    page.wait_for_timeout(900)
    chup(page, "05_ctrl_k_tim_ten")
    kiem(page.locator("#bang-lenh .nhom", has_text="Gia sư").count() == 1, "tìm 'minh anh' (không dấu) ra nhóm Gia sư")
    page.fill("#bang-lenh input", "kh1")
    page.wait_for_timeout(900)
    kiem(page.locator("#bang-lenh .kq a", has_text="KH-0001").count() == 1, "tìm mã kh1 ra KH-0001")
    with page.expect_navigation():
        page.keyboard.press("Enter")
    kiem("/khoa-hoc/1/" in page.url, "Enter mở khóa học")

    print("7. Thu gọn menu (nhớ sau khi tải lại)")
    page.goto(BASE + "/doi-mat-khau/")
    page.click("[data-thu-gon]")
    page.reload()
    page.wait_for_load_state("networkidle")
    kiem("side-gon" in (page.locator("body").get_attribute("class") or ""), "menu vẫn thu gọn sau khi tải lại")
    chup(page, "06_menu_thu_gon")
    page.click("[data-thu-gon]")

    print("8. Menu cá nhân → Đăng xuất")
    page.click("[data-mo-menu=menu-ca-nhan]")
    chup(page, "07_menu_ca_nhan")
    page.click("#menu-ca-nhan button")
    page.wait_for_load_state("networkidle")
    kiem("/dang-nhap/" in page.url, "đăng xuất về trang đăng nhập")

    print("9. Tài khoản mới phải đặt mật khẩu")
    page.fill("#id_username", "gsmoi")
    page.fill("#id_password", "TamThoi123")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    kiem("/doi-mat-khau/" in page.url, "chuyển tới đặt mật khẩu mới")
    page.fill("#id_new_password1", "abc")
    page.fill("#id_new_password2", "abd")
    chup(page, "08_dat_mat_khau_moi_dang_go")
    kiem(page.locator("[data-chua-khop]").is_visible(), "báo hai mật khẩu chưa khớp")
    page.fill("#id_new_password1", "MatKhauMoi2026")
    page.fill("#id_new_password2", "MatKhauMoi2026")
    kiem(page.locator(".dieu-kien li.dat").count() == 3, "đủ 3 điều kiện hiện xanh")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    kiem(page.url.rstrip("/") == BASE, "đặt xong vào trang chủ")

    print("10. Gia sư mở trang của Tuyển sinh → 403 khung mới")
    r = page.goto(BASE + "/yeu-cau/")
    kiem(r.status == 403, "403")
    chup(page, "09_403_gia_su")

    b.close()

loi_console = [x for x in loi_console if "403" not in x]  # bước 10 cố ý gọi trang 403
print("Lỗi console:", loi_console or "không có")
print("TỔNG LỖI:", kiem.loi)
sys.exit(1 if kiem.loi or loi_console else 0)
