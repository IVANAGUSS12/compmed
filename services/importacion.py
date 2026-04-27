from models import Administracion, Indicacion, Paciente
from services.equivalencias import cargar_equivs, resolver_generico
from utils.pdf_parser import parsear_pdf_internacion


def importar_pdf_paciente(tmp_path):
    """Parsea PDF de internacion y devuelve estructuras crudas para persistencia."""
    return parsear_pdf_internacion(tmp_path)


def upsert_paciente_por_pdf(pac_info):
    pac = None
    if pac_info.get('dni'):
        pac = Paciente.query.filter_by(dni=pac_info['dni']).first()

    if pac is None:
        pac = Paciente(
            apellido=pac_info.get('apellido', '').upper(),
            nombre=pac_info.get('nombre', '').upper(),
            dni=pac_info.get('dni', ''),
            fecha_ingreso='',
            fecha_egreso='',
        )
        creado = True
        return pac, creado

    pac.apellido = pac_info.get('apellido', pac.apellido).upper()
    pac.nombre = pac_info.get('nombre', pac.nombre).upper()
    creado = False
    return pac, creado


def reemplazar_datos_paciente(pid):
    Indicacion.query.filter_by(paciente_id=pid).delete()
    Administracion.query.filter_by(paciente_id=pid).delete()


def persistir_indicaciones_administraciones(paciente_id, inds_raw, adms_raw):
    indicaciones = []
    n_ind = 0
    for r in inds_raw:
        if not r['medicamento'] or len(r['medicamento']) < 3:
            continue
        indicaciones.append(Indicacion(
            paciente_id=paciente_id,
            fecha=r['fecha'],
            medico=r['medico'],
            medicamento=r['medicamento'],
            dosis_mg=r['dosis_mg'],
            frecuencia_horas=r['frecuencia_horas'],
            via=r['via'],
            notas=r['notas'],
        ))
        n_ind += 1

    equivs = cargar_equivs()

    administraciones = []
    n_adm = 0
    for r in adms_raw:
        if not r['medicamento']:
            continue
        generico = resolver_generico(r['medicamento'], equivs)
        administraciones.append(Administracion(
            paciente_id=paciente_id,
            fecha=r['fecha'],
            hora=r['hora'],
            enfermero=r['enfermero'],
            medicamento=r['medicamento'],
            medicamento_generico=generico,
            dosis_mg=r['dosis_mg'],
            notas='',
        ))
        n_adm += 1

    return indicaciones, administraciones, n_ind, n_adm
