from django.urls import path
from . import views

app_name = "communication"

urlpatterns = [
    path("", views.home, name="home"),
    path("announcements/new/", views.announcement_create, name="announcement_create"),
    path("channels/<int:pk>/", views.channel, name="channel"),
    path("direct/send/", views.send_direct, name="send_direct"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/go/", views.notification_redirect, name="notification_redirect"),
]
