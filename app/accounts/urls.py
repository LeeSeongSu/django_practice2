from django.contrib.auth.views import LogoutView
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'accounts'

urlpatterns = [
    # CBV 로 LoginView 를 구성, Authentication 폼에서 username/password 의 인증을 수행
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    # path('login/', views.login_view, name='login'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),
]
