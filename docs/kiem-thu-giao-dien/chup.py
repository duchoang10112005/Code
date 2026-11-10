"""Chụp nhanh màn hình: python chup.py <tài khoản> <thư mục ảnh> <url1> [url2 ...]
Đăng nhập bằng mật khẩu demo (seed_demo), báo lỗi console/HTTP ≥ 400."""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8010")
tk, out, urls = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
loi = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: m.type == "error" and loi.append(m.text))
    page.on("pageerror", lambda e: loi.append(str(e)))
    page.goto(BASE + "/dang-nhap/")
    page.fill("#id_username", tk)
    page.fill("#id_password", os.environ.get("E2E_MK", "Demo@2026"))
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    for u in urls:
        r = page.goto(BASE + u)
        page.wait_for_load_state("networkidle")
        ten = u.strip("/").replace("/", "_").replace("?", "_").replace("=", "-") or "trang_chu"
        page.screenshot(path=os.path.join(out, f"{tk}_{ten}.png"), full_page=True)
        print(r.status, u)
        if r.status >= 400:
            loi.append(f"HTTP {r.status} {u}")
    b.close()
print("LỖI:", loi or "không có")
