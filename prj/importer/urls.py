"""
importer/urls.py
────────────────
URL patterns for the CSV student importer app.

Included in prj/urls.py with:
    path('import/', include('importer.urls', namespace='importer')),
"""

from django.urls import path

from . import views

app_name = 'importer'

urlpatterns = [
    path('',               views.upload_view,       name='upload'),
    path('preview/',       views.preview_view,      name='preview'),
    path('confirm/',       views.confirm_view,       name='confirm'),
    path('history/',       views.batch_list_view,    name='batch_list'),
    path('history/<int:batch_id>/', views.batch_detail_view, name='batch_detail'),
]
