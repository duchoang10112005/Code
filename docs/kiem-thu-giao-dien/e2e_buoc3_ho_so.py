"""E2E Bước 3f – Hồ sơ của tôi: lưới giờ rảnh + đăng ký môn 4 bước (server e2e cổng 8010)."""
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8010"
OUT = sys.argv[1] if len(sys.argv) > 1 else "anh_ho_so"
os.makedirs(OUT, exist_ok=True)
loi, dem_loi = [], 0
anh = os.path.join(tempfile.gettempdir(), "kq_test.png")
with open(anh, "wb") as f:  # PNG 1x1 hợp lệ
    f.write(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                          "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"))


def kiem(dk, mo_ta):
    global dem_loi
    print(("  OK  " if dk else "  LỖI ") + mo_ta)
    dem_loi += 0 if dk else 1


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: loi.append(str(e)))
    page.goto(BASE + "/dang-nhap/")
    page.fill("#id_username", "giasu1")
    page.fill("#id_password", "Demo@2026")
    with page.expect_navigation():
        page.click("button[type=submit]")
    page.goto(BASE + "/ho-so/")
    page.wait_for_load_state("networkidle")
    page.screenshot(path=os.path.join(OUT, "ho_so.png"), full_page=True)

    # Lưới giờ rảnh
    o = page.locator("button.o[data-khung='6-SANG']")
    truoc = o.get_attribute("aria-pressed")
    o.click()
    page.click("[data-luu-gio]")
    page.wait_for_timeout(800)
    kiem("Đã lưu" in page.locator(".toasts").inner_text(), "lưu lưới giờ rảnh báo 'Đã lưu'")
    page.reload()
    kiem(page.locator("button.o[data-khung='6-SANG']").get_attribute("aria-pressed") != truoc, "ô CN sáng giữ sau tải lại")

    # Wizard 4 bước
    page.click("button[data-mo-hop=hop-dang-ky] >> nth=0")
    kiem(page.locator("#hop-dang-ky").is_visible(), "mở popup đăng ký môn")
    page.click("[data-wz-toi]")
    kiem("Chọn môn" in page.locator("[data-wz-loi-chu]").inner_text(), "bước 1 thiếu môn → báo lỗi, không qua bước")
    page.locator("[data-ds-mon] label").first.click()
    cap = page.locator("[data-cap-do] input[type=checkbox]")
    if cap.count():
        cap.first.check()
    else:
        page.fill("input[name=cap_do]", "Lớp 6–9")
    page.screenshot(path=os.path.join(OUT, "wizard_1.png"))
    page.click("[data-wz-toi]")
    kiem(page.locator("[data-wz='2']").is_visible(), "sang bước 2 Bài test")
    page.click("[data-wz-toi]")
    kiem("điểm" in page.locator("[data-wz-loi-chu]").inner_text().lower(), "bước 2 thiếu điểm → báo lỗi")
    page.fill("#wz-diem", "8,5")
    page.set_input_files("input[name=anh_ket_qua_test]", anh)
    page.screenshot(path=os.path.join(OUT, "wizard_2.png"))
    page.click("[data-wz-toi]")
    kiem(page.locator("[data-wz='3']").is_visible(), "sang bước 3 Minh chứng")
    page.set_input_files("[data-ds-mc] .dong-mc >> nth=0 >> [data-f=tep]", anh)
    page.click("[data-them-mc]")
    dong2 = page.locator("[data-ds-mc] .dong-mc").nth(1)
    dong2.locator("[data-f=kieu]").select_option("link")
    dong2.locator("[data-f=url]").fill("http://drive.google.com/abc")
    page.click("[data-wz-toi]")
    kiem("https://" in page.locator("[data-wz-loi-chu]").inner_text(), "link http → báo phải https")
    dong2.locator("[data-f=url]").fill("https://drive.google.com/abc")
    page.screenshot(path=os.path.join(OUT, "wizard_3.png"))
    page.click("[data-wz-toi]")
    kiem(page.locator("[data-wz='4']").is_visible(), "sang bước 4 Xem lại")
    kiem("8,5/10" in page.locator("[data-xem-lai]").inner_text(), "xem lại có điểm 8,5/10")
    page.fill("#wz-kn", "Hai năm dạy kèm học sinh THCS")
    page.check("input[name=cam_ket]")
    page.screenshot(path=os.path.join(OUT, "wizard_4.png"))
    with page.expect_navigation():
        page.click("[data-wz-toi]")
    page.wait_for_load_state("networkidle")
    kiem(page.locator(".gt-r .chip.cam", has_text="Chờ duyệt").count() >= 1, "môn mới hiện 'Chờ duyệt'")
    kiem(page.locator(".gt-r a", has_text="ảnh kết quả").count() >= 1, "có link xem ảnh kết quả (có phân quyền)")
    page.screenshot(path=os.path.join(OUT, "ho_so_sau_dang_ky.png"), full_page=True)
    b.close()

print("Lỗi JS:", loi or "không có")
print("TỔNG LỖI:", dem_loi)
sys.exit(1 if dem_loi or loi else 0)
