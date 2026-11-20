from django.contrib import admin

from .models import BankAccount, PaymentLine, PaymentOrder


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['company', 'bank', 'currency', 'iban', 'active']
    list_filter = ['company', 'currency', 'active']


class LineInline(admin.TabularInline):
    model = PaymentLine
    extra = 0
    readonly_fields = ['invoice', 'amount']
    can_delete = False


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    # Orders change state only through the app's approve / pay / cancel actions, so admin is read-only.
    list_display = ['number', 'supplier', 'currency', 'status', 'pay_date']
    list_filter = ['status', 'company', 'currency']
    inlines = [LineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
