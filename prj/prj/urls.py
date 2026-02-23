"""
URL configuration for prj project.

Routing is split across four dedicated apps:
  core          – public landing page and about page
  accounts      – login / logout / password change
  finances      – student dashboards, payments, treasurer tools
  communications – notification log
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── core: public pages ────────────────────────────────────────────────────
    path('', include('core.urls')),

    # ── accounts: auth ────────────────────────────────────────────────────────
    path('', include('accounts.urls')),

    # ── finances: student + treasurer views ───────────────────────────────────
    path('', include('finances.urls')),

    # ── communications: notification log ─────────────────────────────────────
    path('communications/', include('communications.urls')),
]
