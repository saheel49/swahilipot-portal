from django.urls import path
from . import views

app_name = "suggestions"

urlpatterns = [
    path("", views.suggestion_list, name="list"),
    path("new/", views.suggestion_create, name="create"),
    path("<int:pk>/review/", views.review, name="review"),
]
