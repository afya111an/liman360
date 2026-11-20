from django.contrib import admin

from .models import Approval, ApprovalLevel, Company, ExchangeRate, ExpenseCategory, Invoice, Supplier, Vessel

admin.site.site_header = 'Liman360 tanımlar'
admin.site.site_title = 'Liman360'

for m in (Company, Vessel, ExpenseCategory, ApprovalLevel):
    admin.site.register(m)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    search_fields = ['name', 'tax_no']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['date', 'currency', 'rate']
    list_filter = ['currency']


class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 0
    readonly_fields = ['level', 'user', 'approved', 'note', 'at']
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'supplier', 'company', 'amount', 'currency', 'status']
    list_filter = ['status', 'company', 'currency']
    search_fields = ['number', 'supplier__name']
    readonly_fields = ['status', 'created_by']
    inlines = [ApprovalInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
