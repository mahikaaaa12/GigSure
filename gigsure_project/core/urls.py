from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('index.html', views.dashboard), 
    path('dashboard/', views.dashboard), 

    path('api/signup', views.signup),
    path('api/login', views.login),
]