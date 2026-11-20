from django.urls import path

from . import views

app_name = 'invoices'
urlpatterns = [
    path('onay/', views.invoice_list, {'scope': 'pool'}, name='pool'),
    path('onay/<int:pk>/', views.invoice_list, {'scope': 'pool'}, name='pool_detail'),
    path('tumu/', views.invoice_list, {'scope': 'all'}, name='all'),
    path('tumu/<int:pk>/', views.invoice_list, {'scope': 'all'}, name='all_detail'),
    path('yeni/', views.invoice_create, name='create'),
    path('<int:pk>/karar/', views.invoice_decide, name='decide'),
]
