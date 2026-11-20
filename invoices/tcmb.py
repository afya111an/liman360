"""TCMB (Central Bank of Turkey) indicative exchange rates.

TCMB publishes one XML file per business day around 15:30 Istanbul time:
today's at /kurlar/today.xml, past days at /kurlar/YYYYMM/DDMMYYYY.xml.
Weekends and holidays have no file (404).
"""
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = 'https://www.tcmb.gov.tr/kurlar/'


def url_for(day=None):
    return BASE + ('today.xml' if day is None else f'{day:%Y%m}/{day:%d%m%Y}.xml')


def download(day=None, timeout=20):
    """Raw XML for day (None = latest), or None when TCMB published nothing that day."""
    req = Request(url_for(day), headers={'User-Agent': 'liman360-rates/1.0'})
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read()
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse(xml_bytes, codes):
    """-> (bulletin date, {code: TRY per 1 unit}) using ForexSelling (döviz satış)."""
    root = ET.fromstring(xml_bytes)
    if root.tag != 'Tarih_Date' or not root.get('Date'):
        raise ValueError('Not a TCMB rates file')
    day = datetime.strptime(root.get('Date'), '%m/%d/%Y').date()
    rates = {}
    for cur in root.iter('Currency'):
        code = cur.get('CurrencyCode') or cur.get('Kod')
        if code not in codes:
            continue
        try:
            unit = Decimal(cur.findtext('Unit') or '1')
            selling = Decimal(cur.findtext('ForexSelling') or '')
        except InvalidOperation:
            continue  # TCMB leaves ForexSelling empty for some currencies
        if selling > 0 and unit > 0:
            rates[code] = (selling / unit).quantize(Decimal('0.0001'))
    return day, rates


def is_business_day(day: date):
    return day.weekday() < 5
