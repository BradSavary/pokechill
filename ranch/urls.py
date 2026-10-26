from django.urls import path

from . import views

app_name = "ranch"

urlpatterns = [
    path("", views.index, name="index"),
]
