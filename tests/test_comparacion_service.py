from types import SimpleNamespace

from services.comparacion import comparar_indicaciones_administraciones


def _ind(
    fecha='01/04/2026',
    medicamento='MEROPENEM',
    dosis_mg=500,
    frecuencia_horas=24,
    notas='',
):
    return SimpleNamespace(
        fecha=fecha,
        medicamento=medicamento,
        dosis_mg=dosis_mg,
        frecuencia_horas=frecuencia_horas,
        notas=notas,
        via='IV',
        medico='TEST',
    )


def _adm(
    adm_id,
    fecha='01/04/2026',
    medicamento='MEROEFECTIL 500 MG',
    medicamento_generico='MEROPENEM',
    dosis_mg=500,
):
    return SimpleNamespace(
        id=adm_id,
        fecha=fecha,
        medicamento=medicamento,
        medicamento_generico=medicamento_generico,
        dosis_mg=dosis_mg,
        hora='08:00',
        enfermero='N1',
    )


def _single_result(indicaciones, administraciones):
    resultados, adms_sin_ind = comparar_indicaciones_administraciones(indicaciones, administraciones)
    assert len(resultados) == 1
    return resultados[0], adms_sin_ind


def test_cada_48_horas_con_una_toma_es_ok():
    ind = _ind(frecuencia_horas=48, dosis_mg=500)
    adm = _adm(1, dosis_mg=500)

    r, adms_sin_ind = _single_result([ind], [adm])

    assert r['dosis_esperadas'] == 1
    assert r['estado'] == 'ok'
    assert r['dosis_dadas'] == 1
    assert adms_sin_ind == []


def test_lmv_sin_administracion_es_sin_datos_y_semanal():
    ind = _ind(frecuencia_horas=None, dosis_mg=4000, notas='LMV (lunes-miercoles-viernes)')

    r, _ = _single_result([ind], [])

    assert r['frecuencia_semanal'] is True
    assert r['frecuencia_continua'] is False
    assert r['estado'] == 'sin_datos'


def test_continua_sin_administracion_es_sin_datos_y_continua():
    ind = _ind(frecuencia_horas=None, dosis_mg=50, notas='INFUSION CONTINUA')

    r, _ = _single_result([ind], [])

    assert r['frecuencia_semanal'] is False
    assert r['frecuencia_continua'] is True
    assert r['estado'] == 'sin_datos'


def test_equivalencia_por_mg_dos_por_veinticinco_es_ok_para_cincuenta():
    ind = _ind(dosis_mg=50, frecuencia_horas=24)
    adm_1 = _adm(1, dosis_mg=25)
    adm_2 = _adm(2, dosis_mg=25)

    r, _ = _single_result([ind], [adm_1, adm_2])

    assert r['estado'] == 'ok'
    assert r['mg_esperado'] == 50
    assert r['mg_administrado'] == 50
    assert r['dosis_dadas'] == 2


def test_dosis_incompleta_por_conteo():
    ind = _ind(dosis_mg=None, frecuencia_horas=8)
    adm_1 = _adm(1, dosis_mg=None)
    adm_2 = _adm(2, dosis_mg=None)

    r, _ = _single_result([ind], [adm_1, adm_2])

    assert r['dosis_esperadas'] == 3
    assert r['dosis_dadas'] == 2
    assert r['estado'] == 'incompleto'
