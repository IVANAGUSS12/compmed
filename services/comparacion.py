import re
from difflib import SequenceMatcher


UMBRAL = 0.65


def _norm_nombre(s):
    s = (s or '').upper().strip()
    s = re.sub(r'[^A-Z0-9\s+]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def similitud_nombre(a, b):
    na, nb = _norm_nombre(a), _norm_nombre(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if len(na) >= 5 and (na in nb or nb in na):
        return 0.9

    ta, tb = set(na.split()), set(nb.split())
    if ta and tb:
        inter = len(ta & tb)
        union = len(ta | tb)
        if inter >= 2 or (inter >= 1 and inter / max(len(ta), len(tb)) >= 0.5):
            return max(inter / union, 0.65)

    return SequenceMatcher(None, na, nb).ratio()


def _nota_upper(indicacion):
    return (getattr(indicacion, 'notas', '') or '').upper()


def es_frecuencia_semanal(indicacion):
    notas = _nota_upper(indicacion)
    return any(token in notas for token in ('LMV', 'LUN/MIE/VIE', 'LUNES', 'MIERCOLES', 'VIERNES', 'SEMANAL'))


def es_frecuencia_continua(indicacion):
    return 'CONTINUA' in _nota_upper(indicacion)


def filtrar_comparacion(resultados, estado=None, solo_semanales=False):
    filtrados = resultados
    if estado and estado != 'todos':
        filtrados = [item for item in filtrados if item['estado'] == estado]
    if solo_semanales:
        filtrados = [item for item in filtrados if item['frecuencia_semanal']]
    return filtrados


def comparar_indicaciones_administraciones(indicaciones, administraciones, umbral=UMBRAL):
    resultados = []
    adms_usadas = set()

    adms_por_fecha = {}
    for a in administraciones:
        adms_por_fecha.setdefault(a.fecha, []).append(a)

    vistos_ind = {}
    for ind in indicaciones:
        key = (ind.fecha, _norm_nombre(ind.medicamento))
        if key not in vistos_ind:
            vistos_ind[key] = ind

    for ind in vistos_ind.values():
        adms_dia = [
            a
            for a in adms_por_fecha.get(ind.fecha, [])
            if similitud_nombre(ind.medicamento, getattr(a, 'medicamento_generico', None) or a.medicamento) >= umbral
        ]

        for a in adms_dia:
            if getattr(a, 'id', None) is not None:
                adms_usadas.add(a.id)

        dosis_por_dia = max(1, round(24 / ind.frecuencia_horas)) if ind.frecuencia_horas else 1
        frecuencia_semanal = es_frecuencia_semanal(ind)
        frecuencia_continua = es_frecuencia_continua(ind)
        freq_especial = ind.frecuencia_horas is None and (frecuencia_semanal or frecuencia_continua)

        adms_con_mg = [a for a in adms_dia if getattr(a, 'dosis_mg', None) is not None]
        mg_administrado_total = sum(a.dosis_mg for a in adms_con_mg) if adms_con_mg else None

        if ind.dosis_mg and mg_administrado_total is not None:
            mg_esperado = ind.dosis_mg * dosis_por_dia
            estado = 'ok' if mg_administrado_total >= mg_esperado * 0.85 else 'incompleto'
            mg_administrado = mg_administrado_total
        else:
            mg_esperado = (ind.dosis_mg * dosis_por_dia) if ind.dosis_mg else None
            mg_administrado = mg_administrado_total
            if len(adms_dia) == 0:
                estado = 'falta' if not freq_especial else 'sin_datos'
            elif len(adms_dia) >= dosis_por_dia:
                estado = 'ok'
            else:
                estado = 'incompleto'

        resultados.append(
            {
                'indicacion': ind,
                'adms': adms_dia,
                'estado': estado,
                'mg_esperado': mg_esperado,
                'mg_administrado': mg_administrado,
                'dosis_esperadas': dosis_por_dia,
                'dosis_dadas': len(adms_dia),
                'frecuencia_semanal': frecuencia_semanal,
                'frecuencia_continua': frecuencia_continua,
            }
        )

    adms_sin_ind = [a for a in administraciones if getattr(a, 'id', None) not in adms_usadas]
    return resultados, adms_sin_ind
