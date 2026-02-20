"""
URL configuration for prj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.render_home, name='homepage'),
    path('about/', views.render_about, name='about'),
    # Student dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('payments/pending/', views.pending_payments_view, name='pending_payments'),
    path('payments/info/', views.payment_info_view, name='payment_info'),
    # Treasurer dashboard
    path('treasurer/', views.treasurer_dashboard_view, name='treasurer_dashboard'),
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Password management
    path('password-change/', views.password_change_view, name='password_change'),
    path('password-change/done/', views.password_change_done_view, name='password_change_done'),
]
