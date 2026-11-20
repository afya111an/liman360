from django import forms
from django.utils import timezone

from .models import Invoice


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        # Order follows the 4-column form grid: four single cells, then pairs, then full-width rows.
        fields = ['number', 'invoice_date', 'due_date', 'ref_no', 'supplier', 'company', 'category', 'vessel',
                  'voyage', 'amount', 'currency', 'description', 'notes']
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'due_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'inputmode': 'decimal'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            css = 'form-select' if isinstance(f.widget, forms.Select) else 'form-control'
            f.widget.attrs.setdefault('class', css)
            if isinstance(f, forms.ModelChoiceField):
                f.empty_label = 'Seçiniz'
            f.span = {'supplier': 'w2', 'company': 'w2', 'category': 'w2', 'amount': 'w2 f-amt',
                      'currency': 'w2', 'description': 'w4', 'notes': 'w4'}.get(name, '')
        self.fields['number'].widget.attrs['autocomplete'] = 'off'
        self.fields['voyage'].queryset = self.fields['voyage'].queryset.exclude(
            status='CANCELLED').select_related('vessel')
        self.fields['voyage'].label_from_instance = lambda v: f'{v.number} · {v.vessel}'
        self.fields['voyage'].help_text = 'Seçilirse gemi seferden alınır.'
        self.fields['invoice_date'].initial = timezone.localdate
