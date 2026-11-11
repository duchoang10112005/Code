"""E2E: Tuyển sinh thêm email phụ huynh → gia sư xác nhận buổi → hệ thống tự gửi email đánh giá.

Chạy khi server e2e (8010) đang chạy. Tham số: thư mục ảnh, mã học viên (pk), mã buổi (pk), email nhận thử.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8010"
OUT, HV, BH, EMAIL = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
os.makedirs(OUT, exist_ok=True)
loi = []


def dang_nhap(pg, ten):
    pg.context.clear_cookies()
    pg.goto(BASE + "/dang-nhap/")
    pg.fill("#id_username", ten)
    pg.fill("#id_password", "Demo@2026")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: loi.append(str(e)))

    # 1) Tuyển sinh thêm email phụ huynh trong hộp Sửa học viên
    dang_nhap(pg, "tuyensinh")
    pg.goto(f"{BASE}/hoc-vien/?chon={HV}")
    pg.click("[data-mo-hop='hop-sua-hv']")
    pg.fill("#id_hv-email_phu_huynh", EMAIL)
    pg.click("#hop-sua-hv button.pri")
    pg.wait_for_load_state("networkidle")
    assert EMAIL in pg.content(), "Chưa lưu được email phụ huynh"
    pg.screenshot(path=f"{OUT}/1_hoc_vien_co_email.png")

    # 2) Gia sư xác nhận buổi
    dang_nhap(pg, "giasu1")
    pg.goto(f"{BASE}/buoi-hoc/{BH}/")
    assert "và email" in pg.content(), "Ô tick chưa nhắc gửi email"
    pg.fill("[name=noi_dung]", "Ôn tập dao động điều hòa, chữa bài tập chương 1")
    pg.locator("label:has([name=xep_loai][value=TOT])").click()
    pg.fill("[name=danh_gia]", "Em nắm chắc công thức, làm đúng 9/10 bài, cần luyện thêm bài đồ thị.")
    pg.fill("[name=dan_do_buoi_sau]", "Làm bài 1–5 trang 20")
    pg.locator("[data-phieu] button.pri").last.click()
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(800)
    trang = pg.content()
    pg.screenshot(path=f"{OUT}/2_sau_xac_nhan.png", full_page=True)
    print("thong bao email:", "qua Zalo và email" in trang, "| chip email đã gửi:", "Email · đã gửi" in trang)
    b.close()
print("LỖI JS:", loi or "không có")
