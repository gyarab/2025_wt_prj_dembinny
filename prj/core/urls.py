"""
core/urls.py
────────────
URL patterns for public / sitewide pages.
Include in the root urls.py with:
    path('', include('core.urls')),
"""

from django.urls import path

from . import views

urlpatterns = [
    path('',       views.home_view,  name='homepage'),
    path('about/', views.about_view, name='about'),
]
