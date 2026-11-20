from django.urls import path

from . import views

app_name = 'operations'
urlpatterns = [
    path('seferler/', views.voyage_list, name='voyages'),
    path('seferler/yeni/', views.voyage_form, name='voyage_create'),
    path('seferler/<int:pk>/', views.voyage_list, name='voyage_detail'),
    path('seferler/<int:pk>/duzenle/', views.voyage_form, name='voyage_edit'),
    path('seferler/<int:pk>/islem/', views.voyage_action, name='voyage_action'),
    path('gemiler/', views.vessel_list, name='vessels'),
    path('gemiler/yeni/', views.vessel_form, name='vessel_create'),
    path('gemiler/<int:pk>/', views.vessel_list, name='vessel_detail'),
    path('gemiler/<int:pk>/duzenle/', views.vessel_form, name='vessel_edit'),
    path('bunker/', views.bunker_list, name='bunkers'),
    path('bunker/yeni/', views.bunker_form, name='bunker_create'),
    path('bunker/<int:pk>/', views.bunker_list, name='bunker_detail'),
    path('bunker/<int:pk>/duzenle/', views.bunker_form, name='bunker_edit'),
    path('raporlar/', views.noon_list, name='noon'),
    path('raporlar/yeni/', views.noon_form, name='noon_create'),
    path('raporlar/<int:pk>/', views.noon_list, name='noon_detail'),
    path('raporlar/<int:pk>/duzenle/', views.noon_form, name='noon_edit'),
]
