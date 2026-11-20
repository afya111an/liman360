from decimal import Decimal

from django import forms
from django.utils import timezone

from invoices.models import Vessel

from .models import BunkerDelivery, FuelGrade, NoonReport, Voyage

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def plain(d):
    """Decimal('747.700') -> Decimal('747.7'), Decimal('80.000') -> Decimal('80') (no exponent form)."""
    return Decimal(format(d.normalize(), 'f'))


def styled(form, spans):
    """Bootstrap classes plus the 4-column bill-of-lading span for each field. Decimal fields accept and show
    Turkish numbers (28,1 / 28.500) and drop trailing zeros from stored values."""
    for name, value in list(form.initial.items()):
        if isinstance(value, Decimal):
            form.initial[name] = plain(value)
    for name, f in form.fields.items():
        f.widget.attrs.setdefault('class', 'form-select' if isinstance(f.widget, forms.Select) else 'form-control')
        if isinstance(f, forms.ModelChoiceField):
            f.empty_label = 'Seçiniz'
        if isinstance(f, forms.DecimalField):
            f.localize = f.widget.is_localized = True
            if isinstance(f.widget, forms.NumberInput):  # type=number rejects a decimal comma
                f.widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
                f.widget.is_localized = True
            f.widget.attrs.setdefault('inputmode', 'decimal')
        f.span = spans.get(name, '')


class VoyageForm(forms.ModelForm):
    class Meta:
        model = Voyage
        # Order and spans fill the 4-column grid row by row (see styled()).
        fields = ['number', 'vessel', 'load_port', 'discharge_port', 'planned_departure', 'planned_arrival',
                  'cargo', 'cargo_mt', 'charterer', 'freight_rate', 'freight_currency']
        widgets = {'planned_departure': DATE, 'planned_arrival': DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vessel'].queryset = Vessel.objects.filter(active=True)
        styled(self, {'number': 'ph-full', 'vessel': 'w3', 'load_port': 'w2', 'discharge_port': 'w2',
                      'planned_departure': 'w2', 'planned_arrival': 'w2', 'cargo': 'w2', 'cargo_mt': 'w2',
                      'charterer': 'w2', 'freight_rate': 'ph-full', 'freight_currency': 'ph-full'})
        self.fields['number'].widget.attrs['autocomplete'] = 'off'


class VesselForm(forms.ModelForm):
    class Meta:
        model = Vessel
        fields = ['name', 'imo', 'vessel_type', 'flag', 'dwt', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styled(self, {'name': 'w2', 'flag': 'w2'})
        self.fields['active'].widget.attrs['class'] = 'form-check-input'

    def clean_imo(self):
        return self.cleaned_data['imo'] or None  # blank IMO stays NULL so the unique index allows many


class BunkerForm(forms.ModelForm):
    class Meta:
        model = BunkerDelivery
        fields = ['vessel', 'voyage', 'date', 'port', 'grade', 'supplier', 'bdn_no', 'quantity_mt', 'price_per_mt',
                  'currency']
        widgets = {'date': DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vessel'].queryset = Vessel.objects.filter(active=True)
        self.fields['voyage'].queryset = Voyage.objects.exclude(status=Voyage.Status.CANCELLED).select_related('vessel')
        self.fields['voyage'].label_from_instance = lambda v: f'{v.number} · {v.vessel}'
        self.fields['date'].initial = timezone.localdate
        styled(self, {'vessel': 'w2', 'voyage': 'w2', 'port': 'w2', 'supplier': 'w2', 'bdn_no': 'w2',
                      'currency': 'w2'})


class NoonForm(forms.ModelForm):
    """The report plus one consumed / ROB pair per fuel grade; a grade left blank is not carried."""
    class Meta:
        model = NoonReport
        fields = ['vessel', 'date', 'remarks']
        widgets = {'date': DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vessel'].queryset = Vessel.objects.filter(active=True)
        self.fields['date'].initial = timezone.localdate
        self.grades = []
        for g, label in FuelGrade.choices:
            for kind in ('cons', 'rob'):
                self.fields[f'{kind}_{g}'] = forms.DecimalField(required=False, min_value=Decimal('0'), max_digits=10,
                                                                decimal_places=3, widget=forms.TextInput())
        styled(self, {'vessel': 'w2', 'date': 'w2', 'remarks': 'w4'})
        for g, label in FuelGrade.choices:
            self.grades.append((g, label, self[f'cons_{g}'], self[f'rob_{g}']))

    def fuel_fields(self):
        return [f for f in self if not f.name.startswith(('cons_', 'rob_'))]

    def clean(self):
        data = super().clean()
        rows = {}
        for g, _ in FuelGrade.choices:
            cons, rob = data.get(f'cons_{g}'), data.get(f'rob_{g}')
            if cons is None and rob is None:
                continue
            if cons is None or rob is None:
                self.add_error(f'rob_{g}' if rob is None else f'cons_{g}', f'{g} için tüketim ve ROB birlikte girilmeli.')
                continue
            rows[g] = (cons, rob)
        if not rows and not self.errors:
            raise forms.ValidationError('En az bir yakıt cinsi için tüketim ve ROB girin.')
        date = data.get('date')
        if date and date > timezone.localdate():
            self.add_error('date', 'Rapor tarihi bugünden ileri olamaz.')
        self.fuel_rows = rows
        return data
