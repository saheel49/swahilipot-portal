from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change.html",
        success_url="/password-change/done/",
    ), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html",
    ), name="password_change_done"),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("attendance/", include("attendance.urls")),
    path("communication/", include("communication.urls")),
    path("tasks/", include("tasks.urls")),
    path("events/", include("events.urls")),
    path("suggestions/", include("suggestions.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

