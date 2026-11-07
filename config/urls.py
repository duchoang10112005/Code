from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Trung tâm Gia sư – Quản trị dữ liệu (dev)"

urlpatterns = [
    path("django-admin/", admin.site.urls),  # chỉ dùng để tra dữ liệu khi phát triển
    path("", include("core.urls")),
]
