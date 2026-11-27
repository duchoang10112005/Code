CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

CREATE TABLE "core_bannhapdanhgia" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "du_lieu" text NOT NULL CHECK ((JSON_VALID("du_lieu") OR "du_lieu" IS NULL)), "luu_luc" datetime NOT NULL, "buoi_hoc_id" bigint NOT NULL UNIQUE REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_buoihoc" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(20) NOT NULL, "bat_dau" datetime NOT NULL, "thoi_luong_phut" integer unsigned NOT NULL CHECK ("thoi_luong_phut" >= 0), "trang_thai" varchar(20) NOT NULL, "ly_do_huy" varchar(20) NOT NULL, "zoom_meeting_id" varchar(50) NOT NULL, "zoom_join_url" varchar(500) NOT NULL, "zoom_start_url" varchar(1000) NOT NULL, "zoom_passcode" varchar(20) NOT NULL, "zoom_loi" text NOT NULL, "noi_dung" text NOT NULL, "danh_gia" text NOT NULL, "xac_nhan_luc" datetime NULL, "kiem_tra" varchar(20) NOT NULL, "kiem_tra_ghi_chu" text NOT NULL, "phut_tham_gia_chung" integer unsigned NULL CHECK ("phut_tham_gia_chung" >= 0), "ban_ghi_trang_thai" varchar(20) NOT NULL, "ban_ghi_url" varchar(1000) NOT NULL, "ban_ghi_passcode" varchar(50) NOT NULL, "ban_ghi_het_han" datetime NULL, "zalo_trang_thai" varchar(20) NOT NULL, "tao_luc" datetime NOT NULL, "cap_nhat_luc" datetime NOT NULL, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "hoc_vien_id" bigint NOT NULL REFERENCES "core_hocvien" ("id") DEFERRABLE INITIALLY DEFERRED, "khoa_hoc_id" bigint NULL REFERENCES "core_khoahoc" ("id") DEFERRABLE INITIALLY DEFERRED, "yeu_cau_id" bigint NOT NULL REFERENCES "core_yeucauhoctap" ("id") DEFERRABLE INITIALLY DEFERRED, "da_nhac_han" bool NOT NULL, "dan_do_buoi_sau" text NOT NULL, "han_xac_nhan" datetime NULL, "mo_lai_luc" datetime NULL, "so_thu_tu" integer unsigned NULL CHECK ("so_thu_tu" >= 0), "thoi_luong_thuc_te" integer unsigned NULL CHECK ("thoi_luong_thuc_te" >= 0), "thu_lao_du_kien" integer unsigned NOT NULL CHECK ("thu_lao_du_kien" >= 0), "xep_loai" varchar(20) NOT NULL, "ghi_chu_tuyen_sinh" text NOT NULL, "gui_zalo_phu_huynh" bool NOT NULL, "ket_thuc_luc" datetime NULL, "ly_do_huy_ghi_chu" varchar(300) NOT NULL, "phong_dong_luc" datetime NULL, "phong_mo_luc" datetime NULL, "tai_khoan_zoom_id" bigint NULL REFERENCES "core_taikhoanzoom" ("id") DEFERRABLE INITIALLY DEFERRED, "email_trang_thai" varchar(20) NOT NULL, "ban_ghi_cac_doan" text NOT NULL CHECK ((JSON_VALID("ban_ghi_cac_doan") OR "ban_ghi_cac_doan" IS NULL)), "thay_the_cho_id" bigint NULL UNIQUE REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, "hoc_bu_cho_id" bigint NULL UNIQUE REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "buoi_chinh_thuc_phai_co_khoa_hoc" CHECK (("loai" = 'HOC_THU' OR "khoa_hoc_id" IS NOT NULL)));

CREATE TABLE "core_capdo" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ten" varchar(80) NOT NULL, "thu_tu" integer unsigned NOT NULL CHECK ("thu_tu" >= 0), "dang_mo" bool NOT NULL, "mon_hoc_id" bigint NULL REFERENCES "core_monhoc" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_dieuchinhthulao" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "thang" date NOT NULL, "so_tien" integer NOT NULL, "ly_do" text NOT NULL, "tao_luc" datetime NOT NULL, "buoi_hoc_id" bigint NULL REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_doigiasu" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ly_do" varchar(30) NOT NULL, "ghi_chu" varchar(300) NOT NULL, "trang_thai" varchar(20) NOT NULL, "tao_luc" datetime NOT NULL, "duyet_luc" datetime NULL, "duyet_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_cu_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_moi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "khoa_hoc_id" bigint NOT NULL REFERENCES "core_khoahoc" ("id") DEFERRABLE INITIALLY DEFERRED, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_moi_dong_y" bool NOT NULL, "so_buoi_chuyen" integer unsigned NOT NULL CHECK ("so_buoi_chuyen" >= 0), "thu_lao_moi" integer unsigned NULL CHECK ("thu_lao_moi" >= 0));

CREATE TABLE "core_doisoatthang" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "thang" date NOT NULL, "tong_tien" integer NOT NULL, "chot_luc" datetime NULL, "ghi_chu" text NOT NULL, "chot_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "kiem_tra_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "kiem_tra_luc" datetime NULL, "trang_thai" varchar(20) NOT NULL, "chi_tra_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "chi_tra_luc" datetime NULL, "chung_tu" varchar(200) NOT NULL, CONSTRAINT "doi_soat_mot_lan_moi_thang" UNIQUE ("gia_su_id", "thang"));

CREATE TABLE "core_giahankhoa" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(20) NOT NULL, "so_buoi_cu" integer unsigned NOT NULL CHECK ("so_buoi_cu" >= 0), "so_buoi_moi" integer unsigned NOT NULL CHECK ("so_buoi_moi" >= 0), "hoc_phi_moi_buoi" integer unsigned NULL CHECK ("hoc_phi_moi_buoi" >= 0), "ly_do" varchar(300) NOT NULL, "tao_luc" datetime NOT NULL, "khoa_hoc_id" bigint NOT NULL REFERENCES "core_khoahoc" ("id") DEFERRABLE INITIALLY DEFERRED, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_haukiembuoi" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "da_cham" bool NOT NULL, "tre_phut" smallint NULL, "ty_le_gia_su" smallint unsigned NULL CHECK ("ty_le_gia_su" >= 0), "ty_le_hoc_vien" smallint unsigned NULL CHECK ("ty_le_hoc_vien" >= 0), "do_dai_nhan_xet" smallint unsigned NOT NULL CHECK ("do_dai_nhan_xet" >= 0), "da_gui_zalo" bool NOT NULL, "so_canh_bao" smallint unsigned NOT NULL CHECK ("so_canh_bao" >= 0), "ket_luan" varchar(30) NOT NULL, "ly_do" varchar(30) NOT NULL, "ghi_chu" text NOT NULL, "hang_loat" bool NOT NULL, "kiem_luc" datetime NULL, "buoi_hoc_id" bigint NOT NULL UNIQUE REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, "kiem_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "nguoi_phu_trach_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_hocvien" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ho_ten" varchar(150) NOT NULL, "lop" varchar(50) NOT NULL, "ten_phu_huynh" varchar(150) NOT NULL, "sdt_phu_huynh" varchar(15) NOT NULL, "dong_y_ghi_hinh" bool NOT NULL, "ghi_chu" text NOT NULL, "tao_luc" datetime NOT NULL, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gioi_tinh" varchar(5) NOT NULL, "truong" varchar(200) NOT NULL, "tuyen_sinh_phu_trach_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "email_phu_huynh" varchar(254) NOT NULL);

CREATE TABLE "core_hosogiasu" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kinh_nghiem" text NOT NULL, "trinh_do" varchar(200) NOT NULL, "email_zoom" varchar(254) NOT NULL, "trang_thai" varchar(20) NOT NULL, "cap_nhat_luc" datetime NOT NULL, "user_id" bigint NOT NULL UNIQUE REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "muc_tieu_buoi_thang" integer unsigned NOT NULL CHECK ("muc_tieu_buoi_thang" >= 0), "nguoi_moi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "so_lop_toi_da" integer unsigned NOT NULL CHECK ("so_lop_toi_da" >= 0), "tam_nghi_den" date NULL, "truong_hoc" varchar(200) NOT NULL, "ma_moi_id" bigint NULL REFERENCES "core_mamoigiasu" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_khoahoc" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "so_buoi_dang_ky" integer unsigned NOT NULL CHECK ("so_buoi_dang_ky" >= 0), "so_buoi_da_dung" integer unsigned NOT NULL CHECK ("so_buoi_da_dung" >= 0), "thoi_luong_phut" integer unsigned NOT NULL CHECK ("thoi_luong_phut" >= 0), "hoc_phi_moi_buoi" integer unsigned NOT NULL CHECK ("hoc_phi_moi_buoi" >= 0), "thu_lao_moi_buoi" integer unsigned NOT NULL CHECK ("thu_lao_moi_buoi" >= 0), "trang_thai" varchar(20) NOT NULL, "tao_luc" datetime NOT NULL, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "hoc_vien_id" bigint NOT NULL REFERENCES "core_hocvien" ("id") DEFERRABLE INITIALLY DEFERRED, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "yeu_cau_id" bigint NOT NULL UNIQUE REFERENCES "core_yeucauhoctap" ("id") DEFERRABLE INITIALLY DEFERRED, "ghi_chu" varchar(300) NOT NULL, "ghi_chu_phu_huynh" text NOT NULL, "hoan_thanh_luc" datetime NULL, "lich_co_dinh" text NOT NULL CHECK ((JSON_VALID("lich_co_dinh") OR "lich_co_dinh" IS NULL)), "ma_lop" varchar(20) NULL UNIQUE, "tuyen_sinh_phu_trach_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "zalo_nhom" varchar(150) NOT NULL, CONSTRAINT "khoa_hoc_khong_vuot_so_buoi" CHECK ("so_buoi_da_dung" <= ("so_buoi_dang_ky")), CONSTRAINT "khoa_hoc_so_buoi_duong" CHECK ("so_buoi_dang_ky" > 0), CONSTRAINT "khoa_hoc_thu_lao_khong_vuot_hoc_phi" CHECK ("thu_lao_moi_buoi" <= ("hoc_phi_moi_buoi")));

CREATE TABLE "core_lichranh" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "thu" integer NOT NULL, "tu_gio" time NOT NULL, "den_gio" time NOT NULL, "ho_so_id" bigint NOT NULL REFERENCES "core_hosogiasu" ("id") DEFERRABLE INITIALLY DEFERRED, "khung" varchar(10) NOT NULL, CONSTRAINT "lich_ranh_gio_hop_le" CHECK ("den_gio" > ("tu_gio")));

CREATE TABLE "core_loimoi" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "trang_thai" varchar(20) NOT NULL, "gui_luc" datetime NOT NULL, "het_han_luc" datetime NOT NULL, "phan_hoi_luc" datetime NULL, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gui_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "yeu_cau_id" bigint NOT NULL REFERENCES "core_yeucauhoctap" ("id") DEFERRABLE INITIALLY DEFERRED, "ly_do_tu_choi" varchar(300) NOT NULL, "cam_ket" bool NOT NULL, "chi_tiet_khop" text NOT NULL CHECK ((JSON_VALID("chi_tiet_khop") OR "chi_tiet_khop" IS NULL)), "diem_khop" smallint unsigned NULL CHECK ("diem_khop" >= 0), "ghi_chu_gia_su" varchar(300) NOT NULL);

CREATE TABLE "core_mamoigiasu" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ma" varchar(12) NOT NULL UNIQUE, "het_han_luc" datetime NULL, "dang_mo" bool NOT NULL, "tao_luc" datetime NOT NULL, "tuyen_sinh_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_minhchung" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(20) NOT NULL, "kieu" varchar(10) NOT NULL, "tep" varchar(100) NOT NULL, "url" varchar(500) NOT NULL, "mo_ta" varchar(200) NOT NULL, "tao_luc" datetime NOT NULL, "ho_so_id" bigint NOT NULL REFERENCES "core_hosogiasu" ("id") DEFERRABLE INITIALLY DEFERRED, "mon_gia_su_id" bigint NULL REFERENCES "core_mongiasu" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "minh_chung_co_tep_hoac_link" CHECK ((("kieu" = 'TEP' AND NOT ("tep" = '')) OR ("kieu" = 'LINK' AND NOT ("url" = '')))));

CREATE TABLE "core_mongiasu" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "cap_do" varchar(100) NOT NULL, "trang_thai" varchar(20) NOT NULL, "duyet_luc" datetime NULL, "duyet_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "ho_so_id" bigint NOT NULL REFERENCES "core_hosogiasu" ("id") DEFERRABLE INITIALLY DEFERRED, "mon_hoc_id" bigint NOT NULL REFERENCES "core_monhoc" ("id") DEFERRABLE INITIALLY DEFERRED, "ghi_chu_duyet" varchar(300) NOT NULL, "anh_ket_qua_test" varchar(100) NOT NULL, "diem_test" decimal NULL, "gui_luc" datetime NULL, "link_ket_qua_test" varchar(500) NOT NULL, "ly_do_dang_ky" text NOT NULL, CONSTRAINT "mon_gia_su_khong_trung" UNIQUE ("ho_so_id", "mon_hoc_id"));

CREATE TABLE "core_mongiasu_cap_do_duyet" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "mongiasu_id" bigint NOT NULL REFERENCES "core_mongiasu" ("id") DEFERRABLE INITIALLY DEFERRED, "capdo_id" bigint NOT NULL REFERENCES "core_capdo" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_monhoc" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ma" varchar(20) NOT NULL UNIQUE, "ten" varchar(100) NOT NULL, "bai_test_phut" integer unsigned NULL CHECK ("bai_test_phut" >= 0), "bai_test_so_cau" integer unsigned NULL CHECK ("bai_test_so_cau" >= 0), "bai_test_url" varchar(500) NOT NULL, "dang_mo" bool NOT NULL, "diem_dat" decimal NULL);

CREATE TABLE "core_nhacviec" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(30) NOT NULL, "noi_dung" varchar(300) NOT NULL, "han_luc" datetime NOT NULL, "da_bao_luc" datetime NULL, "xong_luc" datetime NULL, "tao_luc" datetime NOT NULL, "khoa_hoc_id" bigint NULL REFERENCES "core_khoahoc" ("id") DEFERRABLE INITIALLY DEFERRED, "nguoi_phu_trach_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "yeu_cau_id" bigint NULL REFERENCES "core_yeucauhoctap" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_nhatky" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "hanh_dong" varchar(100) NOT NULL, "doi_tuong" varchar(200) NOT NULL, "chi_tiet" text NOT NULL, "thoi_diem" datetime NOT NULL, "nguoi_thuc_hien_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_tri_cu" text NULL CHECK ((JSON_VALID("gia_tri_cu") OR "gia_tri_cu" IS NULL)), "gia_tri_moi" text NULL CHECK ((JSON_VALID("gia_tri_moi") OR "gia_tri_moi" IS NULL)), "ip" char(39) NULL, "loai_doi_tuong" varchar(20) NOT NULL, "ma_doi_tuong" varchar(30) NOT NULL);

CREATE TABLE "core_nhatkyguitin" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kenh" varchar(10) NOT NULL, "nguoi_nhan" varchar(200) NOT NULL, "tieu_de" varchar(200) NOT NULL, "noi_dung" text NOT NULL, "thanh_cong" bool NOT NULL, "phan_hoi" text NOT NULL, "thoi_diem" datetime NOT NULL, "buoi_hoc_id" bigint NULL REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_sucohethong" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "duong_dan" varchar(500) NOT NULL, "phuong_thuc" varchar(10) NOT NULL, "ma_loi" smallint unsigned NOT NULL CHECK ("ma_loi" >= 0), "chi_tiet" text NOT NULL, "du_lieu_form" text NOT NULL CHECK ((JSON_VALID("du_lieu_form") OR "du_lieu_form" IS NULL)), "tao_luc" datetime NOT NULL, "nguoi_dung_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_taikhoanzoom" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "email_host" varchar(254) NOT NULL UNIQUE, "host_key" varchar(10) NOT NULL, "dang_bat" bool NOT NULL, "ghi_chu" varchar(200) NOT NULL);

CREATE TABLE "core_thongbao" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(20) NOT NULL, "tieu_de" varchar(200) NOT NULL, "noi_dung" text NOT NULL, "url" varchar(300) NOT NULL, "da_doc" bool NOT NULL, "tao_luc" datetime NOT NULL, "nguoi_nhan_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_thulao" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "thang" date NOT NULL, "so_tien" integer unsigned NOT NULL CHECK ("so_tien" >= 0), "trang_thai" varchar(20) NOT NULL, "tao_luc" datetime NOT NULL, "buoi_hoc_id" bigint NOT NULL UNIQUE REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, "gia_su_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_tokenzalo" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "access_token" text NOT NULL, "refresh_token" text NOT NULL, "het_han_luc" datetime NULL, "cap_nhat_luc" datetime NOT NULL);

CREATE TABLE "core_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "first_name" varchar(150) NOT NULL, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "vai_tro" varchar(20) NOT NULL, "ho_ten" varchar(150) NOT NULL, "so_dien_thoai" varchar(20) NOT NULL, "khoa_luc" datetime NULL, "ly_do_khoa" varchar(300) NOT NULL, "phai_doi_mat_khau" bool NOT NULL);

CREATE TABLE "core_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_yeucauhoctap" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "trinh_do" varchar(100) NOT NULL, "muc_tieu" text NOT NULL, "lich_mong_muon" varchar(200) NOT NULL, "trang_thai" varchar(20) NOT NULL, "phan_cong_luc" datetime NULL, "ket_qua_hoc_thu" varchar(20) NOT NULL, "ghi_chu_hoc_thu" text NOT NULL, "tao_luc" datetime NOT NULL, "cap_nhat_luc" datetime NOT NULL, "gia_su_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "hoc_vien_id" bigint NOT NULL REFERENCES "core_hocvien" ("id") DEFERRABLE INITIALLY DEFERRED, "mon_hoc_id" bigint NOT NULL REFERENCES "core_monhoc" ("id") DEFERRABLE INITIALLY DEFERRED, "tao_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "ly_do_dong" varchar(300) NOT NULL, "thu_mong_muon" text NOT NULL CHECK ((JSON_VALID("thu_mong_muon") OR "thu_mong_muon" IS NULL)), "dang_ky_thang" bool NOT NULL, "ghi_chu" text NOT NULL, "khung_mong_muon" text NOT NULL CHECK ((JSON_VALID("khung_mong_muon") OR "khung_mong_muon" IS NULL)), "nhac_goi_lai_luc" datetime NULL, "thu_lao_du_kien" integer unsigned NULL CHECK ("thu_lao_du_kien" >= 0), "cap_do_id" bigint NULL REFERENCES "core_capdo" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "core_yeucauxuly" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "loai" varchar(20) NOT NULL, "noi_dung" text NOT NULL, "minh_chung_url" varchar(500) NOT NULL, "trang_thai" varchar(20) NOT NULL, "han_xu_ly" datetime NULL, "xu_ly_luc" datetime NULL, "ket_qua" varchar(300) NOT NULL, "tao_luc" datetime NOT NULL, "buoi_hoc_id" bigint NULL REFERENCES "core_buoihoc" ("id") DEFERRABLE INITIALLY DEFERRED, "nguoi_gui_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "su_co_id" bigint NULL REFERENCES "core_sucohethong" ("id") DEFERRABLE INITIALLY DEFERRED, "xu_ly_boi_id" bigint NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");

CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");

CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");

CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");

CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");

CREATE INDEX "buoi_gs_tt_bd" ON "core_buoihoc" ("gia_su_id", "trang_thai", "bat_dau");

CREATE INDEX "buoi_tt_han" ON "core_buoihoc" ("trang_thai", "han_xac_nhan");

CREATE INDEX "core_buoihoc_gia_su_id_8126733e" ON "core_buoihoc" ("gia_su_id");

CREATE INDEX "core_buoihoc_hoc_vien_id_c827feb5" ON "core_buoihoc" ("hoc_vien_id");

CREATE INDEX "core_buoihoc_ket_thuc_luc_3afa39ec" ON "core_buoihoc" ("ket_thuc_luc");

CREATE INDEX "core_buoihoc_khoa_hoc_id_2aa56960" ON "core_buoihoc" ("khoa_hoc_id");

CREATE INDEX "core_buoihoc_tai_khoan_zoom_id_09b45d93" ON "core_buoihoc" ("tai_khoan_zoom_id");

CREATE INDEX "core_buoihoc_yeu_cau_id_714c4e17" ON "core_buoihoc" ("yeu_cau_id");

CREATE INDEX "core_capdo_mon_hoc_id_058c9230" ON "core_capdo" ("mon_hoc_id");

CREATE INDEX "core_dieuchinhthulao_buoi_hoc_id_7dfee73c" ON "core_dieuchinhthulao" ("buoi_hoc_id");

CREATE INDEX "core_dieuchinhthulao_gia_su_id_a203e3af" ON "core_dieuchinhthulao" ("gia_su_id");

CREATE INDEX "core_dieuchinhthulao_tao_boi_id_9a662d5d" ON "core_dieuchinhthulao" ("tao_boi_id");

CREATE INDEX "core_doigiasu_duyet_boi_id_ac8e5977" ON "core_doigiasu" ("duyet_boi_id");

CREATE INDEX "core_doigiasu_gia_su_cu_id_edfe6636" ON "core_doigiasu" ("gia_su_cu_id");

CREATE INDEX "core_doigiasu_gia_su_moi_id_9f77b7b6" ON "core_doigiasu" ("gia_su_moi_id");

CREATE INDEX "core_doigiasu_khoa_hoc_id_ec192a5c" ON "core_doigiasu" ("khoa_hoc_id");

CREATE INDEX "core_doigiasu_tao_boi_id_2877ff4a" ON "core_doigiasu" ("tao_boi_id");

CREATE INDEX "core_doisoatthang_chi_tra_boi_id_662e33c6" ON "core_doisoatthang" ("chi_tra_boi_id");

CREATE INDEX "core_doisoatthang_chot_boi_id_94b8c9fa" ON "core_doisoatthang" ("chot_boi_id");

CREATE INDEX "core_doisoatthang_gia_su_id_d5235ee0" ON "core_doisoatthang" ("gia_su_id");

CREATE INDEX "core_doisoatthang_kiem_tra_boi_id_5ba02911" ON "core_doisoatthang" ("kiem_tra_boi_id");

CREATE INDEX "core_giahankhoa_khoa_hoc_id_5425da29" ON "core_giahankhoa" ("khoa_hoc_id");

CREATE INDEX "core_giahankhoa_tao_boi_id_8ff0ab23" ON "core_giahankhoa" ("tao_boi_id");

CREATE INDEX "core_haukiembuoi_kiem_boi_id_38231c7f" ON "core_haukiembuoi" ("kiem_boi_id");

CREATE INDEX "core_haukiembuoi_nguoi_phu_trach_id_f38feec2" ON "core_haukiembuoi" ("nguoi_phu_trach_id");

CREATE INDEX "core_hocvien_tao_boi_id_f5c29f4a" ON "core_hocvien" ("tao_boi_id");

CREATE INDEX "core_hocvien_tuyen_sinh_phu_trach_id_1094f09e" ON "core_hocvien" ("tuyen_sinh_phu_trach_id");

CREATE INDEX "core_hosogiasu_ma_moi_id_1de91934" ON "core_hosogiasu" ("ma_moi_id");

CREATE INDEX "core_hosogiasu_nguoi_moi_id_41023c81" ON "core_hosogiasu" ("nguoi_moi_id");

CREATE INDEX "core_khoahoc_gia_su_id_44af0ac3" ON "core_khoahoc" ("gia_su_id");

CREATE INDEX "core_khoahoc_hoc_vien_id_2c392d8a" ON "core_khoahoc" ("hoc_vien_id");

CREATE INDEX "core_khoahoc_tao_boi_id_5a49906f" ON "core_khoahoc" ("tao_boi_id");

CREATE INDEX "core_khoahoc_tuyen_sinh_phu_trach_id_9c2da28d" ON "core_khoahoc" ("tuyen_sinh_phu_trach_id");

CREATE INDEX "core_lichranh_ho_so_id_6108c907" ON "core_lichranh" ("ho_so_id");

CREATE INDEX "core_loimoi_gia_su_id_89529156" ON "core_loimoi" ("gia_su_id");

CREATE INDEX "core_loimoi_gui_boi_id_912448ff" ON "core_loimoi" ("gui_boi_id");

CREATE INDEX "core_loimoi_yeu_cau_id_1c2aee12" ON "core_loimoi" ("yeu_cau_id");

CREATE INDEX "core_mamoigiasu_tuyen_sinh_id_b67ed511" ON "core_mamoigiasu" ("tuyen_sinh_id");

CREATE INDEX "core_minhchung_ho_so_id_67e52d56" ON "core_minhchung" ("ho_so_id");

CREATE INDEX "core_minhchung_mon_gia_su_id_72b6eedf" ON "core_minhchung" ("mon_gia_su_id");

CREATE INDEX "core_mongiasu_cap_do_duyet_capdo_id_2f322f2f" ON "core_mongiasu_cap_do_duyet" ("capdo_id");

CREATE UNIQUE INDEX "core_mongiasu_cap_do_duyet_mongiasu_id_capdo_id_4712778f_uniq" ON "core_mongiasu_cap_do_duyet" ("mongiasu_id", "capdo_id");

CREATE INDEX "core_mongiasu_cap_do_duyet_mongiasu_id_e44dfa05" ON "core_mongiasu_cap_do_duyet" ("mongiasu_id");

CREATE INDEX "core_mongiasu_duyet_boi_id_46cea22e" ON "core_mongiasu" ("duyet_boi_id");

CREATE INDEX "core_mongiasu_ho_so_id_a226197e" ON "core_mongiasu" ("ho_so_id");

CREATE INDEX "core_mongiasu_mon_hoc_id_829ae563" ON "core_mongiasu" ("mon_hoc_id");

CREATE INDEX "core_nhacviec_khoa_hoc_id_f593bced" ON "core_nhacviec" ("khoa_hoc_id");

CREATE INDEX "core_nhacviec_nguoi_phu_trach_id_aa6e66e2" ON "core_nhacviec" ("nguoi_phu_trach_id");

CREATE INDEX "core_nhacviec_yeu_cau_id_08745a8d" ON "core_nhacviec" ("yeu_cau_id");

CREATE INDEX "core_nhatky_ma_doi_tuong_121f5b72" ON "core_nhatky" ("ma_doi_tuong");

CREATE INDEX "core_nhatky_nguoi_thuc_hien_id_a65b29d5" ON "core_nhatky" ("nguoi_thuc_hien_id");

CREATE INDEX "core_nhatkyguitin_buoi_hoc_id_01d73668" ON "core_nhatkyguitin" ("buoi_hoc_id");

CREATE INDEX "core_sucohethong_nguoi_dung_id_2570dad2" ON "core_sucohethong" ("nguoi_dung_id");

CREATE INDEX "core_thongbao_nguoi_nhan_id_03471751" ON "core_thongbao" ("nguoi_nhan_id");

CREATE INDEX "core_thulao_gia_su_id_adfdfa3b" ON "core_thulao" ("gia_su_id");

CREATE INDEX "core_user_groups_group_id_fe8c697f" ON "core_user_groups" ("group_id");

CREATE INDEX "core_user_groups_user_id_70b4d9b8" ON "core_user_groups" ("user_id");

CREATE UNIQUE INDEX "core_user_groups_user_id_group_id_c82fcad1_uniq" ON "core_user_groups" ("user_id", "group_id");

CREATE INDEX "core_user_user_permissions_permission_id_35ccf601" ON "core_user_user_permissions" ("permission_id");

CREATE INDEX "core_user_user_permissions_user_id_085123d3" ON "core_user_user_permissions" ("user_id");

CREATE UNIQUE INDEX "core_user_user_permissions_user_id_permission_id_73ea0daa_uniq" ON "core_user_user_permissions" ("user_id", "permission_id");

CREATE INDEX "core_yeucauhoctap_cap_do_id_be656110" ON "core_yeucauhoctap" ("cap_do_id");

CREATE INDEX "core_yeucauhoctap_gia_su_id_fa28811e" ON "core_yeucauhoctap" ("gia_su_id");

CREATE INDEX "core_yeucauhoctap_hoc_vien_id_29ad794f" ON "core_yeucauhoctap" ("hoc_vien_id");

CREATE INDEX "core_yeucauhoctap_mon_hoc_id_dceac514" ON "core_yeucauhoctap" ("mon_hoc_id");

CREATE INDEX "core_yeucauhoctap_tao_boi_id_a64240e2" ON "core_yeucauhoctap" ("tao_boi_id");

CREATE INDEX "core_yeucauxuly_buoi_hoc_id_a74dc077" ON "core_yeucauxuly" ("buoi_hoc_id");

CREATE INDEX "core_yeucauxuly_nguoi_gui_id_c74aff2f" ON "core_yeucauxuly" ("nguoi_gui_id");

CREATE INDEX "core_yeucauxuly_su_co_id_9a4151b0" ON "core_yeucauxuly" ("su_co_id");

CREATE INDEX "core_yeucauxuly_xu_ly_boi_id_032409a5" ON "core_yeucauxuly" ("xu_ly_boi_id");

CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" ("content_type_id");

CREATE INDEX "django_admin_log_user_id_c564eba6" ON "django_admin_log" ("user_id");

CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");

CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");

CREATE INDEX "hau_kiem_ts_kl" ON "core_haukiembuoi" ("nguoi_phu_trach_id", "ket_luan");

CREATE UNIQUE INDEX "lich_ranh_mot_khung_moi_thu" ON "core_lichranh" ("ho_so_id", "thu", "khung") WHERE NOT ("khung" = '');

CREATE INDEX "loi_moi_tt_han" ON "core_loimoi" ("trang_thai", "het_han_luc");

CREATE UNIQUE INDEX "mot_loi_moi_dang_cho_moi_gia_su" ON "core_loimoi" ("yeu_cau_id", "gia_su_id") WHERE "trang_thai" = 'CHO';

CREATE INDEX "thong_bao_nn_doc" ON "core_thongbao" ("nguoi_nhan_id", "da_doc");

CREATE INDEX "ycxl_tt_loai" ON "core_yeucauxuly" ("trang_thai", "loai");
