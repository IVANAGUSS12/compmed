import re

from models import Equivalencia


def cargar_equivs():
    return [(e.patron.upper(), e.generico) for e in Equivalencia.query.filter_by(activa=True).all()]


def resolver_generico(nombre_comercial, equivs=None):
    if equivs is None:
        equivs = cargar_equivs()

    s = nombre_comercial.upper().strip()
    for patron, generico in equivs:
        if patron in s:
            return generico

    # Fallback: primeras palabras antes de la dosis.
    s2 = re.sub(r'\s+\d+.*$', '', nombre_comercial.strip())
    words = s2.split()
    return ' '.join(words[:3]).strip() or nombre_comercial
