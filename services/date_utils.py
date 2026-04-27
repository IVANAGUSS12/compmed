import re
from datetime import datetime


def parse_fecha(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def date_to_input(s):
    d = parse_fecha(s)
    return d.strftime('%Y-%m-%d') if d else ''


def normalize_date_input(s):
    if not s:
        return ''
    s = s.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        try:
            return datetime.strptime(s, '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            pass
    return s
