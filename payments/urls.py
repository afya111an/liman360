from django.urls import path

from . import views

app_name = 'payments'
urlpatterns = [
    path('onay/', views.order_list, {'scope': 'onay'}, name='pending'),
    path('onay/<int:pk>/', views.order_list, {'scope': 'onay'}, name='pending_detail'),
    path('odenecek/', views.order_list, {'scope': 'odenecek'}, name='topay'),
    path('odenecek/<int:pk>/', views.order_list, {'scope': 'odenecek'}, name='topay_detail'),
    path('tumu/', views.order_list, {'scope': 'tumu'}, name='all'),
    path('tumu/<int:pk>/', views.order_list, {'scope': 'tumu'}, name='all_detail'),
    path('yeni/', views.order_create, name='create'),
    path('<int:pk>/islem/', views.order_action, name='action'),
]
