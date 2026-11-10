"""Nghiệp vụ hồ sơ gia sư – tiến trình 2.0 trên DFD (PB-04; BRULE-09, BRULE-10).

Quy tắc:
- Gia sư tự cập nhật kinh nghiệm, lịch rảnh và ĐĂNG KÝ môn (trạng thái Chờ duyệt).
- Gia sư KHÔNG sửa/xóa được môn đã duyệt; chỉ rút được môn đang chờ hoặc bị từ chối.
- Chỉ Admin duyệt / từ chối / thu hồi môn và đổi trạng thái hồ sơ.
- Hồ sơ chỉ được chuyển sang "Đang hoạt động" khi có ít nhất 1 môn đã duyệt.
Mọi thao tác của Admin đều ghi nhật ký (D9) và gửi email báo cho gia sư.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import HoSoGiaSu, LichRanh, MonGiaSu
from core.services.nhat_ky import ghi_nhat_ky
from core.services.thong_bao import gui_email
from core.services.yeu_cau import huy_loi_moi_cua_gia_su


# ---------- Phía gia sư ----------------------------------------------------
DUOI_TEP = (".pdf", ".jpg", ".jpeg", ".png")


def kiem_tra_tep(tep, ten_o="tep"):
    """Tệp minh chứng: pdf/jpg/png, tối đa GIOI_HAN_TEP_MB."""
    if tep is None:
        return
    gioi_han = getattr(settings, "GIOI_HAN_TEP_MB", 5)
    if not tep.name.lower().endswith(DUOI_TEP):
        raise ValidationError({ten_o: "Chỉ nhận tệp PDF, JPG hoặc PNG."})
    if tep.size > gioi_han * 1024 * 1024:
        raise ValidationError({ten_o: f"Tệp tối đa {gioi_han} MB."})


def kiem_tra_link(url, ten_o="url"):
    if url and not url.startswith("https://"):
        raise ValidationError({ten_o: "Link phải bắt đầu bằng https://"})


def dang_ky_mon(ho_so, mon_hoc, cap_do="", cap_do_ids=None, diem_test=None, anh_ket_qua=None,
                link_ket_qua="", minh_chung=None, ly_do_dang_ky="", bat_buoc_day_du=False):
    """Đăng ký môn (SD-27). minh_chung: list dict {loai, tep | url, mo_ta}.

    bat_buoc_day_du=True (popup 4 bước): bắt buộc cấp độ, kết quả test (điểm + ảnh/link), ≥ 1 minh chứng,
    kinh nghiệm ≥ 15 ký tự. Môn từng Bị từ chối / Đã rút → cập nhật bản ghi cũ về Chờ duyệt ("Gửi lại").
    """
    from core.models import CapDo, MinhChung
    minh_chung = minh_chung or []
    cap_do_ds = list(CapDo.objects.filter(pk__in=cap_do_ids or [], dang_mo=True))
    if bat_buoc_day_du:
        if not cap_do_ds and not (cap_do or "").strip():
            raise ValidationError({"cap_do": "Chọn ít nhất 1 cấp độ."})
        if diem_test is None:
            raise ValidationError({"diem_test": "Nhập điểm bài test từ 0 đến 10."})
        if not anh_ket_qua and not link_ket_qua:
            raise ValidationError({"anh_ket_qua_test": "Nộp ảnh chụp kết quả bài test (tệp hoặc link https)."})
        if not minh_chung:
            raise ValidationError({"minh_chung": "Thêm ít nhất 1 bằng cấp hoặc chứng chỉ."})
        if len((ly_do_dang_ky or "").strip()) < 15:
            raise ValidationError({"ly_do_dang_ky": "Mô tả ngắn kinh nghiệm dạy môn này, tối thiểu 15 ký tự."})
    if diem_test is not None and not (0 <= diem_test <= 10):
        raise ValidationError({"diem_test": "Nhập điểm từ 0 đến 10."})
    kiem_tra_tep(anh_ket_qua, "anh_ket_qua_test")
    kiem_tra_link(link_ket_qua, "link_ket_qua_test")
    for i, m in enumerate(minh_chung):
        if m.get("loai") not in MinhChung.Loai.values:
            raise ValidationError({"minh_chung": f"Minh chứng {i + 1}: chọn loại."})
        if m.get("tep"):
            kiem_tra_tep(m["tep"], "minh_chung")
        elif m.get("url"):
            kiem_tra_link(m["url"], "minh_chung")
        else:
            raise ValidationError({"minh_chung": f"Minh chứng {i + 1}: chọn tệp hoặc dán link https."})
    chuoi_cap_do = (cap_do or "").strip() or ", ".join(c.ten for c in cap_do_ds)
    with transaction.atomic():
        mg = MonGiaSu.objects.filter(ho_so=ho_so, mon_hoc=mon_hoc).first()
        if mg and mg.trang_thai in (MonGiaSu.TrangThai.DA_DUYET, MonGiaSu.TrangThai.CHO_DUYET):
            raise ValidationError(f"Bạn đã đăng ký môn {mon_hoc} ({mg.get_trang_thai_display().lower()}).")
        gui_lai = mg is not None
        mg = mg or MonGiaSu(ho_so=ho_so, mon_hoc=mon_hoc)
        mg.cap_do, mg.trang_thai, mg.ghi_chu_duyet = chuoi_cap_do[:100], MonGiaSu.TrangThai.CHO_DUYET, ""
        mg.duyet_boi, mg.duyet_luc, mg.gui_luc = None, None, timezone.now()
        mg.diem_test, mg.link_ket_qua_test, mg.ly_do_dang_ky = diem_test, link_ket_qua, (ly_do_dang_ky or "").strip()
        if anh_ket_qua:
            mg.anh_ket_qua_test = anh_ket_qua
        mg.save()
        mg.cap_do_duyet.set(cap_do_ds)
        for m in minh_chung:
            MinhChung.objects.create(ho_so=ho_so, mon_gia_su=mg, loai=m["loai"],
                                     kieu=MinhChung.Kieu.TEP if m.get("tep") else MinhChung.Kieu.LINK,
                                     tep=m.get("tep") or "", url=m.get("url") or "", mo_ta=(m.get("mo_ta") or "")[:200])
        ghi_nhat_ky(ho_so.user, "Gửi lại đăng ký môn" if gui_lai else "Đăng ký môn dạy", f"{ho_so} – {mon_hoc}",
                    f"Cấp độ: {chuoi_cap_do}" + (f"; điểm test {diem_test}" if diem_test is not None else ""),
                    loai="MON")
    from django.urls import reverse
    from core.services.thong_bao import thong_bao_quan_tri
    thong_bao_quan_tri(f"{ho_so.user.ho_ten} đăng ký {'lại ' if gui_lai else 'thêm '}môn {mon_hoc}",
                       chuoi_cap_do, reverse("gia_su_chi_tiet", args=[ho_so.pk]), "HO_SO")
    return mg


def rut_mon(ho_so, mon_gia_su):
    """Rút môn đang chờ / bị từ chối → Đã rút (giữ bản ghi + minh chứng để tra cứu)."""
    if mon_gia_su.ho_so_id != ho_so.pk:
        raise ValidationError("Môn này không thuộc hồ sơ của bạn.")
    if mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_DUYET:
        raise ValidationError("Môn đã được duyệt không thể tự rút. Vui lòng liên hệ Quản trị viên.")
    if mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_RUT:
        raise ValidationError("Môn này đã được rút.")
    mon_gia_su.trang_thai = MonGiaSu.TrangThai.DA_RUT
    mon_gia_su.save(update_fields=["trang_thai"])
    ghi_nhat_ky(ho_so.user, "Rút đăng ký môn", f"{ho_so} – {mon_gia_su.mon_hoc}", loai="MON")


def them_lich_ranh(ho_so, thu, tu_gio, den_gio):
    if den_gio <= tu_gio:
        raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")
    trung = ho_so.lich_ranh.filter(thu=thu, tu_gio__lt=den_gio, den_gio__gt=tu_gio).first()
    if trung:
        raise ValidationError(f"Khung giờ bị trùng với khung đã có: {trung}.")
    return LichRanh.objects.create(ho_so=ho_so, thu=thu, tu_gio=tu_gio, den_gio=den_gio,
                                   khung=LichRanh.khung_cua_gio(tu_gio, den_gio)
                                   if not ho_so.lich_ranh.filter(thu=thu, khung=LichRanh.khung_cua_gio(tu_gio, den_gio)).exists() else "")


def khung_dang_day(ho_so):
    """{"<thu>-<khung>": "KH-0005"} theo lịch cố định của các khóa đang học."""
    from datetime import time
    from core.models import KhoaHoc
    kq = {}
    for k in KhoaHoc.objects.filter(gia_su=ho_so.user, trang_thai=KhoaHoc.TrangThai.DANG_HOC):
        for x in k.lich_co_dinh or []:
            try:
                h, m = map(int, str(x["gio"]).split(":"))
                kh = LichRanh.khung_cua_gio(time(h, m), time(min(h + 1, 23), m))
                if kh:
                    kq[f"{int(x['thu'])}-{kh}"] = k.ma
            except (KeyError, ValueError):
                continue
    return kq


def dat_luoi_gio_ranh(ho_so, ds_khung):
    """Lưu cả lưới giờ rảnh (SD-26). Trả về danh sách cảnh báo (bỏ chọn khung đang dạy – vẫn lưu)."""
    from datetime import time
    hop_le = set()
    for x in ds_khung or []:
        thu, _, kh = str(x).partition("-")
        if thu.isdigit() and 0 <= int(thu) <= 6 and kh in LichRanh.GIO_KHUNG:
            hop_le.add((int(thu), kh))
    dang_day = khung_dang_day(ho_so)
    thu_ngan = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    nhan = dict(LichRanh.Khung.choices)
    canh_bao = [f"{thu_ngan[int(k.split('-')[0])]} {nhan[k.split('-')[1]].split()[0].lower()} đang dạy {ma}"
                for k, ma in dang_day.items() if (int(k.split("-")[0]), k.split("-")[1]) not in hop_le]
    with transaction.atomic():
        ho_so.lich_ranh.all().delete()
        for thu, kh in sorted(hop_le):
            a, b = LichRanh.GIO_KHUNG[kh]
            LichRanh.objects.create(ho_so=ho_so, thu=thu, khung=kh, tu_gio=time(*map(int, a.split(":"))),
                                    den_gio=time(*map(int, b.split(":"))))
        ghi_nhat_ky(ho_so.user, "Cập nhật giờ rảnh", str(ho_so), f"{len(hop_le)} khung", loai="HO_SO")
    return canh_bao


def cap_nhat_ho_so(ho_so, du_lieu_cu_tam_nghi=None):
    """Sau khi lưu hồ sơ: đặt tạm nghỉ → vô hiệu lời mời đang chờ (SD-26)."""
    if ho_so.dang_tam_nghi and du_lieu_cu_tam_nghi != ho_so.tam_nghi_den:
        # Chỉ vô hiệu lời mời đang chờ; lớp đã nhận và buổi đã xếp giữ nguyên (gia sư tự báo hủy nếu cần).
        from core.models import LoiMoi
        ly_do = f"Gia sư tạm nghỉ đến {ho_so.tam_nghi_den:%d/%m/%Y}"
        n = LoiMoi.objects.filter(gia_su=ho_so.user, trang_thai=LoiMoi.TrangThai.CHO).update(
            trang_thai=LoiMoi.TrangThai.VOIDED, phan_hoi_luc=timezone.now(), ly_do_tu_choi=ly_do)
        ghi_nhat_ky(ho_so.user, "Đặt tạm nghỉ", str(ho_so), f"{ly_do}; vô hiệu {n} lời mời đang chờ", loai="HO_SO")
        return n
    return 0


# ---------- Phía Admin -----------------------------------------------------
def _bao_gia_su(ho_so, tieu_de, noi_dung):
    gui_email(ho_so.user, tieu_de, f"Chào {ho_so.user.ho_ten},\n\n{noi_dung}\n\nTrung tâm Gia sư Trực tuyến")


@transaction.atomic
def duyet_mon(admin, mon_gia_su, ghi_chu=""):
    if mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_DUYET:
        raise ValidationError(f"Môn {mon_gia_su.mon_hoc} đã được duyệt rồi.")  # chống bấm 2 lần / F5
    mon_gia_su.trang_thai = MonGiaSu.TrangThai.DA_DUYET
    mon_gia_su.duyet_boi, mon_gia_su.duyet_luc = admin, timezone.now()
    mon_gia_su.ghi_chu_duyet = ghi_chu
    mon_gia_su.save()
    ghi_nhat_ky(admin, "Duyệt môn dạy", mon_gia_su.ho_so.user.username, f"{mon_gia_su.mon_hoc} – {mon_gia_su.cap_do}")
    _bao_gia_su(mon_gia_su.ho_so, f"Môn {mon_gia_su.mon_hoc} đã được duyệt",
                f"Môn {mon_gia_su.mon_hoc} ({mon_gia_su.cap_do or 'không ghi cấp độ'}) của bạn đã được duyệt. "
                "Từ nay bạn có thể nhận lời mời dạy môn này.")


@transaction.atomic
def tu_choi_mon(admin, mon_gia_su, ly_do):
    if not ly_do.strip():
        raise ValidationError("Cần ghi lý do từ chối để gia sư biết cách bổ sung.")
    if mon_gia_su.trang_thai == MonGiaSu.TrangThai.TU_CHOI:
        raise ValidationError(f"Môn {mon_gia_su.mon_hoc} đã ở trạng thái từ chối.")
    da_duyet_truoc = mon_gia_su.trang_thai == MonGiaSu.TrangThai.DA_DUYET
    mon_gia_su.trang_thai = MonGiaSu.TrangThai.TU_CHOI
    mon_gia_su.duyet_boi, mon_gia_su.duyet_luc = admin, timezone.now()
    mon_gia_su.ghi_chu_duyet = ly_do
    mon_gia_su.save()
    hanh_dong = "Thu hồi môn đã duyệt" if da_duyet_truoc else "Từ chối môn dạy"
    ghi_nhat_ky(admin, hanh_dong, mon_gia_su.ho_so.user.username, f"{mon_gia_su.mon_hoc}: {ly_do}")
    _bao_gia_su(mon_gia_su.ho_so, f"Môn {mon_gia_su.mon_hoc} chưa được duyệt",
                f"Môn {mon_gia_su.mon_hoc} của bạn {'đã bị thu hồi' if da_duyet_truoc else 'chưa được duyệt'}.\n"
                f"Lý do: {ly_do}\nBạn có thể bổ sung thông tin và đăng ký lại trong mục Hồ sơ của tôi.")
    if da_duyet_truoc:
        huy_loi_moi_cua_gia_su(mon_gia_su.ho_so.user, "Bị thu hồi môn", mon_hoc=mon_gia_su.mon_hoc)
    # Hồ sơ đang hoạt động mà không còn môn nào được duyệt → tạm ngừng.
    ho_so = mon_gia_su.ho_so
    if ho_so.trang_thai == HoSoGiaSu.TrangThai.HOAT_DONG and not ho_so.mon_day.filter(
        trang_thai=MonGiaSu.TrangThai.DA_DUYET
    ).exists():
        ho_so.trang_thai = HoSoGiaSu.TrangThai.TAM_NGUNG
        ho_so.save(update_fields=["trang_thai"])
        ghi_nhat_ky(admin, "Tự tạm ngừng hồ sơ", ho_so.user.username, "Không còn môn nào được duyệt")


@transaction.atomic
def doi_trang_thai_ho_so(admin, ho_so, trang_thai_moi):
    if trang_thai_moi == HoSoGiaSu.TrangThai.HOAT_DONG and not ho_so.mon_day.filter(
        trang_thai=MonGiaSu.TrangThai.DA_DUYET
    ).exists():
        raise ValidationError("Cần duyệt ít nhất 1 môn trước khi cho gia sư hoạt động.")
    cu = ho_so.get_trang_thai_display()
    ho_so.trang_thai = trang_thai_moi
    ho_so.save(update_fields=["trang_thai"])
    if trang_thai_moi != HoSoGiaSu.TrangThai.HOAT_DONG:
        huy_loi_moi_cua_gia_su(ho_so.user, f"Hồ sơ chuyển sang {ho_so.get_trang_thai_display()}")
    ghi_nhat_ky(admin, "Đổi trạng thái hồ sơ gia sư", ho_so.user.username, f"{cu} → {ho_so.get_trang_thai_display()}")
    _bao_gia_su(ho_so, "Cập nhật trạng thái hồ sơ",
                f"Hồ sơ gia sư của bạn chuyển sang trạng thái: {ho_so.get_trang_thai_display()}.")
