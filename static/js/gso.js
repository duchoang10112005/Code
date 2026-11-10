/* gso.js — hành vi dùng chung của giao diện mới (không phụ thuộc thư viện ngoài).
   Mọi trang vẫn chạy được khi tắt JS (form POST + chuyển trang); JS chỉ làm nhanh và gọn hơn. */
(function () {
  "use strict";
  var $ = function (s, g) { return (g || document).querySelector(s); };
  var $$ = function (s, g) { return Array.prototype.slice.call((g || document).querySelectorAll(s)); };

  function layCookie(ten) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + ten + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  /* GSO.post(url, duLieu) → Promise<{ok, message, data, errors}> (quy ước API ở 01 · mục 3). */
  function post(url, duLieu) {
    var body = duLieu instanceof FormData ? duLieu : JSON.stringify(duLieu || {});
    var headers = { "X-CSRFToken": layCookie("csrftoken"), "X-Requested-With": "fetch" };
    if (!(duLieu instanceof FormData)) { headers["Content-Type"] = "application/json"; }
    return fetch(url, { method: "POST", headers: headers, body: body, credentials: "same-origin" })
      .then(docJson);
  }
  function get(url) {
    return fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" }).then(docJson);
  }
  function docJson(r) {
    return r.json().catch(function () { return { ok: false, message: "Lỗi máy chủ (" + r.status + ")." }; })
      .then(function (j) { if (r.status >= 400 && j.ok === undefined) { j.ok = false; } return j; });
  }

  /* Toast: GSO.toast("Đã lưu", "ok"|"loi"|"canh"|"tin", {hoanTac: fn, giay: 6}) */
  function toast(noiDung, loai, tuyChon) {
    tuyChon = tuyChon || {};
    var vung = $(".toasts");
    var el = document.createElement("div");
    var icon = { ok: "bi-check-lg", loi: "bi-exclamation-circle", canh: "bi-exclamation-triangle" }[loai || "ok"] || "bi-info-circle";
    el.className = "toast fade-in";
    el.setAttribute("role", "status");
    el.innerHTML = '<span class="ok ' + (loai || "ok") + '"><i class="bi ' + icon + '" aria-hidden="true"></i></span><span></span>' +
      (tuyChon.hoanTac ? '<button type="button" class="btn sm" data-hoan-tac>Hoàn tác</button>' : "") +
      '<button type="button" class="dong" data-dong-toast aria-label="Đóng"><i class="bi bi-x-lg"></i></button>';
    el.children[1].textContent = noiDung;
    vung.appendChild(el);
    var giay = tuyChon.giay || (tuyChon.hoanTac ? Number(document.body.dataset.giayHoanTac || 6) : 4);
    var het = setTimeout(function () { el.remove(); if (tuyChon.khiHet) { tuyChon.khiHet(); } }, giay * 1000);
    if (tuyChon.hoanTac) {
      el.querySelector("[data-hoan-tac]").addEventListener("click", function () {
        clearTimeout(het); el.remove(); tuyChon.hoanTac();
      });
    }
    return el;
  }

  /* Hộp xác nhận: GSO.xacNhan("Nội dung", {nut: "Khóa"}) → Promise<boolean> */
  function xacNhan(noiDung, tuyChon) {
    tuyChon = tuyChon || {};
    var hop = $("#hop-xac-nhan");
    return new Promise(function (xong) {
      $("#hxn-t", hop).textContent = tuyChon.tieuDe || "Xác nhận thao tác";
      $("#hxn-n", hop).textContent = noiDung;
      var dongY = $("[data-dong-y]", hop), huy = $("[data-huy]", hop);
      dongY.textContent = tuyChon.nut || "Đồng ý";
      hop.hidden = false; huy.focus();
      function ket(kq) { hop.hidden = true; dongY.onclick = huy.onclick = null; document.removeEventListener("keydown", esc); xong(kq); }
      function esc(e) { if (e.key === "Escape") { ket(false); } }
      dongY.onclick = function () { ket(true); };
      huy.onclick = function () { ket(false); };
      document.addEventListener("keydown", esc);
    });
  }

  /* data-xac-nhan trên <form> hoặc nút submit → hỏi trước khi gửi */
  document.addEventListener("submit", function (e) {
    var form = e.target, nut = e.submitter;
    var nguon = (nut && nut.dataset.xacNhan) ? nut : (form.dataset.xacNhan ? form : null);
    if (!nguon || form.dataset.daXacNhan === "1") { return; }
    e.preventDefault();
    xacNhan(nguon.dataset.xacNhan, { nut: nguon.dataset.nut }).then(function (ok) {
      if (!ok) { return; }
      form.dataset.daXacNhan = "1";
      if (form.requestSubmit) { form.requestSubmit(nut || undefined); } else { form.submit(); }
    });
  }, true);

  /* data-dang-gui: khóa nút khi đang gửi (tránh bấm 2 lần khi chờ Zoom) */
  document.addEventListener("submit", function (e) {
    var nut = e.submitter;
    if (e.defaultPrevented || !nut || !nut.dataset.dangGui) { return; }
    setTimeout(function () { nut.disabled = true; nut.textContent = nut.dataset.dangGui; }, 0);
  });

  /* Sao chép: data-sao-chep="văn bản" hoặc data-sao-chep-tu="#id" */
  function saoChep(vanBan, thongBao) {
    var xong = function () { toast(thongBao || "Đã sao chép", "ok"); };
    if (navigator.clipboard && window.isSecureContext) { return navigator.clipboard.writeText(vanBan).then(xong); }
    var t = document.createElement("textarea"); t.value = vanBan; document.body.appendChild(t);
    t.select(); document.execCommand("copy"); t.remove(); xong();
    return Promise.resolve();
  }
  document.addEventListener("click", function (e) {
    var nut = e.target.closest("[data-sao-chep],[data-sao-chep-tu]");
    if (!nut) { return; }
    var vb = nut.dataset.saoChep;
    if (nut.dataset.saoChepTu) { var o = $(nut.dataset.saoChepTu); vb = o.value !== undefined ? o.value : o.textContent; }
    saoChep(vb, nut.dataset.thongBao);
  });

  /* Toast của Django messages: tự ẩn; nút đóng */
  $$(".toast[data-tu-dong]").forEach(function (el) { setTimeout(function () { el.remove(); }, 6000); });
  document.addEventListener("click", function (e) {
    var d = e.target.closest("[data-dong-toast]"); if (d) { d.closest(".toast").remove(); }
  });

  /* Thu gọn menu trái (nhớ trên máy) */
  var nutGon = $("[data-thu-gon]");
  if (nutGon) {
    nutGon.addEventListener("click", function () {
      var gon = document.body.classList.toggle("side-gon");
      try { localStorage.setItem("gso-side-gon", gon ? "1" : "0"); } catch (err) { /* chế độ riêng tư */ }
    });
  }

  /* Menu bật/tắt: data-mo-menu="id" */
  function dongMenu(tru) {
    $$("[data-mo-menu]").forEach(function (b) {
      var m = document.getElementById(b.dataset.moMenu);
      if (m && m !== tru) { m.hidden = true; b.setAttribute("aria-expanded", "false"); }
    });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-mo-menu]");
    if (b) {
      var m = document.getElementById(b.dataset.moMenu);
      dongMenu(m);
      m.hidden = !m.hidden;
      b.setAttribute("aria-expanded", String(!m.hidden));
      if (!m.hidden && m.id === "menu-thong-bao") { taiThongBao(); }
      return;
    }
    if (!e.target.closest(".menu")) { dongMenu(null); }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { dongMenu(null); } });

  /* Chuông thông báo */
  function taiThongBao() {
    var ds = $("[data-ds-thong-bao]");
    get("/api/thong-bao/").then(function (j) {
      if (!j.ok) { ds.innerHTML = '<div class="empty">Không tải được thông báo.</div>'; return; }
      var items = j.data.thong_bao;
      if (!items.length) { ds.innerHTML = '<div class="empty"><span class="ring"><i class="bi bi-bell"></i></span>Chưa có thông báo nào.</div>'; return; }
      ds.innerHTML = "";
      items.forEach(function (t) {
        var a = document.createElement("a");
        a.href = t.url || "#"; a.className = t.da_doc ? "" : "chua-doc"; a.dataset.id = t.id;
        a.innerHTML = "<b></b><small></small>";
        a.children[0].textContent = t.tieu_de;
        a.children[1].textContent = (t.noi_dung ? t.noi_dung + " · " : "") + t.luc;
        ds.appendChild(a);
      });
    });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest("[data-ds-thong-bao] a[data-id]");
    if (a && a.classList.contains("chua-doc")) { post("/api/thong-bao/da-doc/", { ids: [Number(a.dataset.id)] }); }
    if (e.target.closest("[data-doc-het]")) {
      post("/api/thong-bao/da-doc/", {}).then(function () {
        $$("[data-ds-thong-bao] a").forEach(function (x) { x.classList.remove("chua-doc"); });
        var so = $("[data-so-thong-bao]"); if (so) { so.remove(); }
      });
    }
  });

  /* Bảng lệnh Ctrl+K */
  var bang = $("#bang-lenh");
  if (bang) {
    var o = $("input", bang), kq = $(".kq", bang), chon = 0, hen = null;
    var lenh = JSON.parse(($("#du-lieu-lenh") || { textContent: "[]" }).textContent || "[]");
    var ve = function (nhom) {
      kq.innerHTML = ""; var stt = 0;
      nhom.forEach(function (n) {
        if (!n.muc.length) { return; }
        var h = document.createElement("div"); h.className = "nhom"; h.textContent = n.ten; kq.appendChild(h);
        n.muc.forEach(function (m) {
          var a = document.createElement("a"); a.href = m.url; a.setAttribute("role", "option");
          a.innerHTML = '<i class="bi ' + (m.icon || "bi-arrow-right") + '" aria-hidden="true"></i><span></span><small></small>';
          a.children[1].textContent = m.nhan; a.children[2].textContent = m.phu || "";
          a.dataset.stt = stt++; kq.appendChild(a);
        });
      });
      if (!stt) { kq.innerHTML = '<div class="empty">Không tìm thấy kết quả phù hợp.</div>'; }
      chon = 0; danhDau();
    };
    var danhDau = function () {
      $$("a", kq).forEach(function (a) { a.setAttribute("aria-selected", String(Number(a.dataset.stt) === chon)); });
      var a = $('a[aria-selected="true"]', kq); if (a) { a.scrollIntoView({ block: "nearest" }); }
    };
    var mo = function () { bang.hidden = false; o.value = ""; ve([{ ten: "Lệnh", muc: lenh }]); o.focus(); };
    var dong = function () { bang.hidden = true; };
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if (bang.hidden) { mo(); } else { dong(); } }
      if (bang.hidden) { return; }
      var tong = $$("a", kq).length;
      if (e.key === "Escape") { dong(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); chon = Math.min(chon + 1, tong - 1); danhDau(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); chon = Math.max(chon - 1, 0); danhDau(); }
      else if (e.key === "Enter") { var a = $('a[aria-selected="true"]', kq); if (a) { e.preventDefault(); location.href = a.href; } }
    });
    $$("[data-mo-lenh]").forEach(function (b) { b.addEventListener("click", mo); });
    bang.addEventListener("click", function (e) { if (e.target === bang) { dong(); } });
    o.addEventListener("input", function () {
      clearTimeout(hen);
      var q = o.value.trim();
      if (!q) { ve([{ ten: "Lệnh", muc: lenh }]); return; }
      hen = setTimeout(function () {
        get("/api/tim-kiem/?q=" + encodeURIComponent(q)).then(function (j) {
          if (o.value.trim() !== q) { return; }
          var nhom = (j.ok ? j.data.nhom : []);
          var l = lenh.filter(function (m) { return m.nhan.toLowerCase().indexOf(q.toLowerCase()) >= 0; });
          if (l.length) { nhom.push({ ten: "Lệnh", muc: l }); }
          ve(nhom);
        });
      }, 250);
    });
  }

  /* Hiện / ẩn mật khẩu: data-hien-mat-khau="#id" */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-hien-mat-khau]"); if (!b) { return; }
    var o = $(b.dataset.hienMatKhau), hien = o.type === "password";
    o.type = hien ? "text" : "password";
    b.setAttribute("aria-pressed", String(hien));
    b.setAttribute("aria-label", hien ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    b.querySelector(".bi").className = "bi " + (hien ? "bi-eye-slash" : "bi-eye");
  });

  /* Hộp thoại: data-mo-hop="id" mở .overlay#id, data-dong-hop đóng, Esc / bấm nền cũng đóng */
  document.addEventListener("click", function (e) {
    var mo = e.target.closest("[data-mo-hop]");
    if (mo) {
      var h = document.getElementById(mo.dataset.moHop);
      if (h) { h.hidden = false; var f = h.querySelector("[autofocus],input,select,textarea,button"); if (f) { f.focus(); } }
      return;
    }
    if (e.target.closest("[data-dong-hop]") || e.target.classList.contains("overlay")) {
      var o = e.target.closest(".overlay"); if (o && o.id !== "hop-xac-nhan") { o.hidden = true; }
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { $$(".overlay:not(#hop-xac-nhan)").forEach(function (o) { o.hidden = true; }); }
  });

  /* Đếm ngược: data-dem-nguoc="ISO" → "05:12:39"; thêm data-kieu="chu" → "còn 5 giờ 12 phút" */
  function demNguoc() {
    $$("[data-dem-nguoc]").forEach(function (el) {
      var s = Math.max(Math.floor((new Date(el.dataset.demNguoc).getTime() - Date.now()) / 1000), 0);
      var g = Math.floor(s / 3600), p = Math.floor(s % 3600 / 60), hai = function (n) { return (n < 10 ? "0" : "") + n; };
      if (el.dataset.kieu === "chu") {
        el.textContent = s <= 0 ? (el.dataset.het || "Hết hạn") : "còn " + (g ? g + " giờ " : "") + p + " phút";
      } else {
        el.textContent = hai(g) + ":" + hai(p) + ":" + hai(s % 60);
      }
      if (s <= 0 && el.dataset.khiHet) { $$(el.dataset.khiHet).forEach(function (n) { n.disabled = true; }); }
    });
  }
  demNguoc(); setInterval(demNguoc, 1000);

  /* Lọc danh sách tại chỗ: <input data-loc="#ds"> lọc các phần tử [data-tim] (chuỗi không dấu) trong #ds */
  function boDau(x) { return x.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d"); }
  $$("[data-loc]").forEach(function (o) {
    o.addEventListener("input", function () {
      var q = boDau(o.value.trim());
      $$(o.dataset.loc + " [data-tim]").forEach(function (x) { x.hidden = !!q && boDau(x.dataset.tim).indexOf(q) < 0; });
    });
  });

  /* Lỗi form: đưa con trỏ tới hộp tóm tắt lỗi */
  var tomTat = $(".tom-tat-loi"); if (tomTat) { tomTat.focus(); }

  /* Tải lại trang (giữ query, đổi tham số nếu có) và hiện toast sau khi tải: GSO.taiLai("Đã lưu", {chon: 5}) */
  function taiLai(noiDung, thamSo) {
    try { sessionStorage.setItem("gso-toast", noiDung || ""); } catch (err) { /* bỏ qua */ }
    var u = new URL(location.href);
    Object.keys(thamSo || {}).forEach(function (k) {
      if (thamSo[k] === null) { u.searchParams.delete(k); } else { u.searchParams.set(k, thamSo[k]); }
    });
    location.href = u.toString();
  }
  try {
    var tc = sessionStorage.getItem("gso-toast");
    if (tc) { sessionStorage.removeItem("gso-toast"); toast(tc, "ok"); }
  } catch (err) { /* bỏ qua */ }

  window.GSO = { post: post, get: get, toast: toast, xacNhan: xacNhan, saoChep: saoChep, taiLai: taiLai, $: $, $$: $$ };
})();
