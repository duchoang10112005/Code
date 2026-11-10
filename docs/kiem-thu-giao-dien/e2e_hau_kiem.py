"""E2E màn Hậu kiểm (SD-21/22): Hợp lệ 1 buổi, Có vấn đề 1 buổi, xử lý Vẫn tính, duyệt nhanh 2 buổi.

Chạy khi server e2e (cổng 8010) đang chạy và đã nạp du_lieu_hau_kiem.py. Tham số 1 = thư mục ảnh.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8010"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
loi = []


def dem(page, tab):
    return int(page.locator(f".tabs a[href^='?tab={tab}'] .cnt").inner_text())


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: loi.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    page.goto(BASE + "/dang-nhap/")
    page.fill("#id_username", "tuyensinh")
    page.fill("#id_password", "Demo@2026")
    page.click("button[type=submit]")
    page.goto(BASE + "/hau-kiem/")
    can0 = dem(page, "can_kiem")

    # 1) Hợp lệ buổi đang chọn
    page.click("[data-ket-luan=HOP_LE]")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    toast1 = page.locator(".toast").first.inner_text()
    assert dem(page, "can_kiem") == can0 - 1, "Hợp lệ chưa giảm tab Cần kiểm tra"

    # 2) Có vấn đề: thiếu ghi chú → báo lỗi tại chỗ; đủ → chuyển tab Có vấn đề
    page.click("[data-ket-luan=CO_VAN_DE]")
    page.wait_for_timeout(300)
    assert "Chọn lý do" in page.locator(".toast").last.inner_text()
    page.click("label.chip-chon:has-text('Vào trễ')")
    page.fill("#hk-gc", "Gia sư vào trễ 12 phút, đã nhắc qua Zalo")
    page.click("[data-ket-luan=CO_VAN_DE]")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    assert dem(page, "co_van_de") == 1
    page.screenshot(path=os.path.join(OUT, "1_sau_ket_luan.png"), full_page=False)

    # 3) Xử lý: Vẫn tính thù lao
    page.goto(BASE + "/hau-kiem/?tab=co_van_de")
    page.fill("#xl-ld", "Phụ huynh xác nhận buổi học đủ giờ")
    page.screenshot(path=os.path.join(OUT, "2_tab_co_van_de.png"), full_page=False)
    page.click("[data-tinh='1']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    assert dem(page, "co_van_de") == 0

    # 4) Duyệt nhanh 2 buổi
    page.goto(BASE + "/hau-kiem/")
    can1 = dem(page, "can_kiem")
    o = page.locator("[data-chon-buoi]")
    o.nth(0).check()
    o.nth(1).check()
    assert page.locator("[data-so-chon]").inner_text() == "2"
    assert page.evaluate("document.querySelector('[data-chon-tat]').indeterminate")
    page.click("[data-duyet-chon]")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, "3_xac_nhan_hang_loat.png"), full_page=False)
    page.click("#hop-xac-nhan [data-dong-y]")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    toast4 = page.locator(".toast").first.inner_text()
    assert dem(page, "can_kiem") == can1 - 2, "Duyệt nhanh chưa giảm đúng 2"
    page.goto(BASE + "/hau-kiem/?tab=da_kiem")
    page.screenshot(path=os.path.join(OUT, "4_tab_da_kiem.png"), full_page=False)
    print("OK", can0, "→", dem(page, "can_kiem"), "|", toast1.strip(), "|", toast4.strip())
    b.close()
print("LỖI JS:", loi or "không có")
