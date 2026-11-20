from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='invoices:pool', permanent=False)),
    path('giris/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('cikis/', auth_views.LogoutView.as_view(), name='logout'),
    path('faturalar/', include('invoices.urls')),
    path('odemeler/', include('payments.urls')),
    path('operasyon/', include('operations.urls')),
    path('tanimlar/', admin.site.urls),
]
