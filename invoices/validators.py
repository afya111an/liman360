import re

from django.core.exceptions import ValidationError

# Country code -> IBAN length, for the countries Liman360 users pay into most; others only get the checksum.
_LENGTHS = {'TR': 26, 'DE': 22, 'GB': 22, 'NL': 18, 'FR': 27, 'IT': 27, 'ES': 24, 'GR': 27, 'CH': 21, 'RU': 33}


def iban_ok(value):
    iban = re.sub(r'\s+', '', value or '').upper()
    if not re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{10,30}', iban):
        return False
    if _LENGTHS.get(iban[:2], len(iban)) != len(iban):
        return False
    digits = ''.join(str(int(c, 36)) for c in iban[4:] + iban[:4])  # ISO 13616 mod-97 check
    return int(digits) % 97 == 1


def imo_ok(value):
    """IMO ship number: 7 digits, last = sum(digit_i * (7 - i)) for the first six, mod 10."""
    v = (value or '').upper().removeprefix('IMO').strip()
    if len(v) != 7 or not v.isdigit():
        return False
    return sum(int(d) * (7 - i) for i, d in enumerate(v[:6])) % 10 == int(v[6])


def validate_imo(value):
    if not imo_ok(value):
        raise ValidationError('Geçerli bir IMO numarası girin (7 rakam, ör. 9074729).')


def validate_iban(value):
    if not iban_ok(value):
        raise ValidationError('Geçerli bir IBAN girin (ör. TR33 0006 1005 1978 6457 8413 26).')
