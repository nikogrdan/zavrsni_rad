from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.email_list, name="email_list"),
    path("email/<int:pk>/", views.email_detail, name="email_detail"),
    path("task/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("task/<int:pk>/action/", views.task_action, name="task_action"),
    path("evaluation/", views.evaluation, name="evaluation"),
    path("refresh/", views.refresh, name="refresh"),
]