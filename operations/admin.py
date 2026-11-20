from django.contrib import admin

from .models import BunkerDelivery, NoonReport, Port, Voyage

admin.site.register(Port, list_display=['name', 'country', 'unlocode'], search_fields=['name', 'unlocode'])
admin.site.register(Voyage, list_display=['number', 'vessel', 'status', 'planned_departure'], list_filter=['status'])
admin.site.register(BunkerDelivery, list_display=['vessel', 'date', 'grade', 'quantity_mt', 'bdn_no'])
admin.site.register(NoonReport, list_display=['vessel', 'date'])
