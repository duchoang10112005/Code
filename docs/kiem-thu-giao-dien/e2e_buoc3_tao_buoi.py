"""E2E Bước 3c – Gia sư tạo 3 buổi lặp tuần (SD-13) trên server e2e (cổng 8010)."""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8010")
OUT = sys.argv[1] if len(sys.argv) > 1 else "anh_buoc3"
os.makedirs(OUT, exist_ok=True)
loi, dem_loi = [], 0


def kiem(dk, mo_ta):
    global dem_loi
    print(("  OK  " if dk else "  LỖI ") + mo_ta)
    dem_loi += 0 if dk else 1


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: loi.append(str(e)))
    page.on("console", lambda m: m.type == "error" and loi.append(m.text))
    page.goto(BASE + "/dang-nhap/")
    page.fill("#id_username", "giasu1")
    page.fill("#id_password", "Demo@2026")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.goto(BASE + "/buoi-hoc/tao/")
    page.wait_for_load_state("networkidle")
    page.locator("label.the-lop", has_text="Trần Gia Bảo").click()
    kiem(page.locator("[data-nut-tao]").is_disabled(), "chưa chọn ngày giờ → nút Tạo bị khóa")
    page.locator("[data-lich-toi]").click()  # sang 3 tuần sau để chắc là ngày tương lai
    page.locator("[data-luoi-ngay] button:not([disabled])").nth(1).click()
    page.select_option("#gio", "19:30")
    page.locator("[data-them]").click()
    page.locator("[data-them]").click()
    page.wait_for_timeout(1200)
    page.screenshot(path=os.path.join(OUT, "tao_buoi_xem_truoc.png"), full_page=True)
    dong = page.locator("[data-xem-truoc] .dong-xt")
    kiem(dong.count() == 3, f"xem trước có 3 buổi (thấy {dong.count()})")
    kiem(page.locator(".lich-chon button.lap").count() >= 1, "lịch đánh dấu buổi lặp")
    kiem(not page.locator("[data-nut-tao]").is_disabled(), "nút Tạo bật khi lịch hợp lệ")
    kiem("Tạo 3 buổi" in page.locator("[data-nut-tao]").inner_text(), "nút ghi 'Tạo 3 buổi học'")
    with page.expect_navigation():
        page.locator("[data-nut-tao]").click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path=os.path.join(OUT, "tao_buoi_ket_qua.png"), full_page=True)
    kiem("da_tao=" in page.url, "chuyển tới trang kết quả")
    kiem(page.locator("article.kq-buoi").count() == 3, "có 3 thẻ kết quả")
    tn = page.locator("pre.tin-nhan").first.inner_text()
    kiem("/lop/" in tn and "Meeting ID" in tn, "tin nhắn Zalo có link lớp cố định và Meeting ID")
    kiem("host key" not in tn.lower(), "tin nhắn không chứa host key")

    # Tạo trùng giờ → bị chặn ở xem trước
    page.goto(BASE + "/buoi-hoc/tao/")
    page.locator("label.the-lop", has_text="Trần Gia Bảo").click()
    page.locator("[data-lich-toi]").click()
    page.locator("[data-luoi-ngay] button:not([disabled])").nth(1).click()
    page.select_option("#gio", "19:30")
    page.wait_for_timeout(1200)
    kiem(page.locator("[data-xem-truoc] .chip.do").count() == 1, "trùng giờ buổi vừa tạo → Bị chặn")
    kiem(page.locator("[data-nut-tao]").is_disabled(), "trùng giờ → nút Tạo khóa")
    page.select_option("#gio", "21:00")
    page.wait_for_timeout(1200)
    kiem(page.locator("[data-xem-truoc] .chip.do").count() == 0, "giờ 21:00 không bị chặn vì quá muộn")
    page.screenshot(path=os.path.join(OUT, "tao_buoi_bi_chan.png"), full_page=True)
    b.close()

print("Lỗi console:", loi or "không có")
print("TỔNG LỖI:", dem_loi)
sys.exit(1 if dem_loi or loi else 0)
