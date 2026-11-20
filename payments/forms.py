from django import forms
from django.utils import timezone

from invoices.models import Company, Currency, Supplier
from invoices.validators import validate_iban


def _style(form):
    for f in form.fields.values():
        f.widget.attrs.setdefault('class', 'form-select' if isinstance(f.widget, forms.Select) else 'form-control')


class PickForm(forms.Form):
    """Step 1: who pays whom, in which currency."""
    sirket = forms.ModelChoiceField(Company.objects.all(), label='Ödeyen şirket', empty_label='Seçiniz')
    cari = forms.ModelChoiceField(Supplier.objects.all(), label='Alıcı (cari)', empty_label='Seçiniz')
    doviz = forms.ChoiceField(choices=Currency.choices, label='Para birimi')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class OrderForm(forms.Form):
    account = forms.ModelChoiceField(None, label='Ödeyen hesap', empty_label='Seçiniz')
    payee_iban = forms.CharField(label='Alıcı IBAN', max_length=34, validators=[validate_iban])
    pay_date = forms.DateField(label='Planlanan ödeme tarihi',
                               widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    note = forms.CharField(label='Açıklama', max_length=200, required=False)

    def __init__(self, *args, accounts, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = accounts
        self.fields['pay_date'].initial = timezone.localdate
        self.fields['payee_iban'].widget.attrs.update(autocomplete='off', spellcheck='false')
        _style(self)
