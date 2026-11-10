"""E2E: 4 chỉ số trang chủ gia sư tự cập nhật không cần tải lại trang.

Chạy khi server e2e (cổng 8010) đang chạy; tham số 1 = thư mục ảnh, tham số 2 = đường dẫn python của dự án,
tham số 3 = DB e2e (để giả lập gia sư xác nhận một buổi ở máy khác).
"""
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8010"
OUT, PY, DB = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
loi = []

XAC_NHAN = """
from core.models import BuoiHoc, User
from core.services import buoi_hoc as dv
from django.utils import timezone
gs = User.objects.get(username='giasu1')
b = BuoiHoc.objects.filter(gia_su=gs, trang_thai='DA_LEN_LICH', ket_thuc_luc__lte=timezone.now(),
                           han_xac_nhan__gte=timezone.now(), loai='CHINH_THUC').first()
dv.xac_nhan_hoan_tat(gs, b, {'noi_dung': 'On tap', 'xep_loai': 'TOT',
                             'danh_gia': 'Em lam bai tot, nam chac kien thuc buoi nay', 'gui_zalo_phu_huynh': False})
print('DA_XAC_NHAN', b.ma)
"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: loi.append(str(e)))
    page.goto(BASE + "/dang-nhap/")
    page.fill("#id_username", "giasu1")
    page.fill("#id_password", "Demo@2026")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    so_truoc = page.locator("[data-cs=so_buoi_thang]").inner_text()
    vong_truoc = page.evaluate("getComputedStyle(document.querySelector('[data-cs=vong]')).strokeDashoffset")
    tien_truoc = page.locator("[data-cs=tam_tinh_chu]").inner_text()
    print("Trước:", so_truoc, "buổi · vòng", vong_truoc, "·", tien_truoc)
    page.locator(".chi-so").screenshot(path=os.path.join(OUT, "chi_so_truoc.png"))
    ok_vong = float(vong_truoc.replace("px", "")) > 1
    print(("  OK  " if ok_vong else "  LỖI ") + "vòng không tô kín khi chưa đạt mục tiêu")

    env = {**os.environ, "DB_PATH": DB, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run([PY, "manage.py", "shell", "-c", XAC_NHAN], capture_output=True, text=True, env=env)
    print(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-300:])

    # Giả lập quay lại tab (không tải lại trang) → trang tự hỏi API
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(1800)
    so_sau = page.locator("[data-cs=so_buoi_thang]").inner_text()
    vong_sau = page.evaluate("getComputedStyle(document.querySelector('[data-cs=vong]')).strokeDashoffset")
    tien_sau = page.locator("[data-cs=tam_tinh_chu]").inner_text()
    print("Sau:  ", so_sau, "buổi · vòng", vong_sau, "·", tien_sau)
    page.locator(".chi-so").screenshot(path=os.path.join(OUT, "chi_so_sau.png"))
    ok = int(so_sau) == int(so_truoc) + 1 and vong_sau != vong_truoc and tien_sau != tien_truoc
    print(("  OK  " if ok else "  LỖI ") + "số buổi, vòng tiến độ và tạm tính tự đổi không cần tải lại")
    b.close()
print("Lỗi JS:", loi or "không có")
sys.exit(0 if ok and ok_vong and not loi else 1)
