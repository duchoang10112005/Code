"""Email lời mời nhận lớp (HTML, theo mẫu): nút dẫn thẳng tới lời mời để Nhận / Từ chối."""

from django.conf import settings
from django.core import mail
from django.urls import reverse

from core.tests.test_pb02_pb06_yeu_cau import DuLieu


class EmailLoiMoiTest(DuLieu):
    def test_email_html_co_nut_toi_dung_loi_moi(self):
        mail.outbox.clear()
        (lm,) = self.moi(self.gs_a)
        thu = [m for m in mail.outbox if m.to == [self.gs_a.email]]
        self.assertEqual(len(thu), 1)
        self.assertIn(self.yc.ma, thu[0].subject)
        html = thu[0].alternatives[0][0]
        url = f"{settings.SITE_URL}{reverse('loi_moi_cua_toi')}?chon={lm.pk}"
        self.assertIn(url, html)
        self.assertIn("NHẬN HOẶC TỪ CHỐI", html)
        self.assertIn("Hạn phản hồi", html)
        self.assertNotIn(self.yc.hoc_vien.sdt_phu_huynh, html)  # không lộ SĐT phụ huynh
        self.assertIn(url, thu[0].body)  # bản văn bản thường cũng có link

    def test_chua_dang_nhap_bam_nut_thi_dang_nhap_xong_quay_lai_loi_moi(self):
        (lm,) = self.moi(self.gs_a)
        dich = f"{reverse('loi_moi_cua_toi')}?chon={lm.pk}"
        r = self.client.get(dich)
        self.assertEqual(r.status_code, 302)
        self.assertIn("next=", r.url)
        r = self.client.post(r.url, {"username": "gsa", "password": "MatKhau@Manh123", "next": dich})
        self.assertRedirects(r, dich, fetch_redirect_response=False)
        r = self.client.get(dich)
        self.assertEqual(r.context["chon"]["lm"], lm)
