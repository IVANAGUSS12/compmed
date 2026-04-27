import os

from flask import Flask, flash, redirect, render_template, request, url_for

from extensions import db
from models import Administracion, EQUIV_DEFAULT, Equivalencia, Indicacion, Paciente
from services.comparacion import comparar_indicaciones_administraciones, filtrar_comparacion
from services.date_utils import date_to_input, normalize_date_input
from services.equivalencias import cargar_equivs, resolver_generico
from services.importacion import (
    importar_pdf_paciente,
    persistir_indicaciones_administraciones,
    reemplazar_datos_paciente,
    upsert_paciente_por_pdf,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'medcontrol-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DATA_DIR, 'medcontrol_v2.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa extension y modelos.
db.init_app(app)


@app.route('/')
def index():
    pacientes = Paciente.query.order_by(Paciente.apellido, Paciente.nombre).all()
    return render_template('index.html', pacientes=pacientes)


@app.route('/paciente/nuevo', methods=['GET', 'POST'])
def nuevo_paciente():
    if request.method == 'POST':
        pac = Paciente(
            nombre=request.form['nombre'].strip().upper(),
            apellido=request.form['apellido'].strip().upper(),
            dni=request.form.get('dni', '').strip(),
            fecha_ingreso=normalize_date_input(request.form.get('fecha_ingreso', '')),
            fecha_egreso=normalize_date_input(request.form.get('fecha_egreso', '')),
        )
        db.session.add(pac)
        db.session.commit()
        flash('Paciente creado correctamente.', 'success')
        return redirect(url_for('paciente', pid=pac.id))
    return render_template('nuevo_paciente.html')


@app.route('/paciente/<int:pid>')
def paciente(pid):
    pac = Paciente.query.get_or_404(pid)
    inds = (
        Indicacion.query.filter_by(paciente_id=pid)
        .order_by(Indicacion.fecha, Indicacion.medicamento)
        .all()
    )
    adms = (
        Administracion.query.filter_by(paciente_id=pid)
        .order_by(Administracion.fecha, Administracion.hora)
        .all()
    )

    comparacion_total, adms_sin_ind = comparar_indicaciones_administraciones(inds, adms)

    tab = request.args.get('tab', 'comparacion')
    filtro_estado = request.args.get('estado', 'todos')
    solo_semanales = request.args.get('solo_semanales', '').lower() in ('1', 'true', 'on', 'si')
    comparacion = filtrar_comparacion(
        comparacion_total,
        estado=filtro_estado,
        solo_semanales=solo_semanales,
    )

    return render_template(
        'paciente.html',
        pac=pac,
        inds=inds,
        adms=adms,
        comparacion=comparacion,
        adms_sin_ind=adms_sin_ind,
        comparacion_total=comparacion_total,
        filtro_estado=filtro_estado,
        solo_semanales=solo_semanales,
        tab=tab,
        date_to_input=date_to_input,
    )


@app.route('/paciente/<int:pid>/editar', methods=['POST'])
def editar_paciente(pid):
    pac = Paciente.query.get_or_404(pid)
    pac.nombre = request.form['nombre'].strip().upper()
    pac.apellido = request.form['apellido'].strip().upper()
    pac.dni = request.form.get('dni', '').strip()
    pac.fecha_ingreso = normalize_date_input(request.form.get('fecha_ingreso', ''))
    pac.fecha_egreso = normalize_date_input(request.form.get('fecha_egreso', ''))
    db.session.commit()
    flash('Datos actualizados.', 'success')
    return redirect(url_for('paciente', pid=pid))


@app.route('/paciente/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    pac = Paciente.query.get_or_404(pid)
    nombre = f'{pac.apellido} {pac.nombre}'
    db.session.delete(pac)
    db.session.commit()
    flash(f'Paciente {nombre} eliminado.', 'success')
    return redirect(url_for('index'))


@app.route('/cargar_pdf', methods=['GET', 'POST'])
def cargar_pdf():
    if request.method == 'GET':
        return render_template('cargar_pdf.html')

    archivo = request.files.get('pdf_file')
    if not archivo or not archivo.filename.lower().endswith('.pdf'):
        flash('Selecciona un archivo PDF valido.', 'danger')
        return render_template('cargar_pdf.html')

    tmp_path = os.path.join(UPLOAD_DIR, 'tmp_upload.pdf')
    archivo.save(tmp_path)

    try:
        pac_info, inds_raw, adms_raw = importar_pdf_paciente(tmp_path)
    except Exception as e:
        flash(f'Error al leer el PDF: {e}', 'danger')
        return render_template('cargar_pdf.html')
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not pac_info.get('apellido') and not pac_info.get('dni'):
        flash('No se pudo identificar al paciente en el PDF.', 'danger')
        return render_template('cargar_pdf.html')

    pac, creado = upsert_paciente_por_pdf(pac_info)
    if creado:
        db.session.add(pac)
        db.session.flush()
    else:
        reemplazar_datos_paciente(pac.id)
        db.session.flush()

    indicaciones, administraciones, n_ind, n_adm = persistir_indicaciones_administraciones(
        pac.id,
        inds_raw,
        adms_raw,
    )
    db.session.add_all(indicaciones)
    db.session.add_all(administraciones)
    db.session.commit()

    accion = 'creado' if creado else 'actualizado'
    flash(
        f'Paciente {pac.apellido}, {pac.nombre} {accion}. '
        f'Importadas {n_ind} indicaciones y {n_adm} administraciones.',
        'success',
    )
    return redirect(url_for('paciente', pid=pac.id))


@app.route('/paciente/<int:pid>/borrar_datos', methods=['POST'])
def borrar_datos(pid):
    Paciente.query.get_or_404(pid)
    Indicacion.query.filter_by(paciente_id=pid).delete()
    Administracion.query.filter_by(paciente_id=pid).delete()
    db.session.commit()
    flash('Datos del paciente borrados.', 'success')
    return redirect(url_for('paciente', pid=pid))


@app.route('/paciente/<int:pid>/indicacion/nueva', methods=['POST'])
def nueva_indicacion(pid):
    Paciente.query.get_or_404(pid)
    dosis = request.form.get('dosis_mg', '').strip()
    freq = request.form.get('frecuencia_horas', '').strip()
    ind = Indicacion(
        paciente_id=pid,
        fecha=normalize_date_input(request.form.get('fecha', '')),
        medico=request.form.get('medico', '').strip(),
        medicamento=request.form['medicamento'].strip(),
        dosis_mg=float(dosis) if dosis else None,
        frecuencia_horas=float(freq) if freq else None,
        via=request.form.get('via', '').strip(),
        notas=request.form.get('notas', '').strip(),
    )
    db.session.add(ind)
    db.session.commit()
    flash('Indicacion agregada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='indicaciones'))


@app.route('/paciente/<int:pid>/indicacion/<int:iid>/editar', methods=['POST'])
def editar_indicacion(pid, iid):
    ind = Indicacion.query.get_or_404(iid)
    dosis = request.form.get('dosis_mg', '').strip()
    freq = request.form.get('frecuencia_horas', '').strip()
    ind.fecha = normalize_date_input(request.form.get('fecha', ''))
    ind.medico = request.form.get('medico', '').strip()
    ind.medicamento = request.form['medicamento'].strip()
    ind.dosis_mg = float(dosis) if dosis else None
    ind.frecuencia_horas = float(freq) if freq else None
    ind.via = request.form.get('via', '').strip()
    ind.notas = request.form.get('notas', '').strip()
    db.session.commit()
    flash('Indicacion actualizada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='indicaciones'))


@app.route('/paciente/<int:pid>/indicacion/<int:iid>/eliminar', methods=['POST'])
def eliminar_indicacion(pid, iid):
    ind = Indicacion.query.get_or_404(iid)
    db.session.delete(ind)
    db.session.commit()
    flash('Indicacion eliminada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='indicaciones'))


@app.route('/paciente/<int:pid>/administracion/nueva', methods=['POST'])
def nueva_administracion(pid):
    Paciente.query.get_or_404(pid)
    dosis = request.form.get('dosis_mg', '').strip()
    med = request.form['medicamento'].strip()
    equivs = cargar_equivs()
    adm = Administracion(
        paciente_id=pid,
        fecha=normalize_date_input(request.form['fecha']),
        hora=request.form.get('hora', '').strip(),
        enfermero=request.form.get('enfermero', '').strip(),
        medicamento=med,
        medicamento_generico=resolver_generico(med, equivs),
        dosis_mg=float(dosis) if dosis else None,
        notas=request.form.get('notas', '').strip(),
    )
    db.session.add(adm)
    db.session.commit()
    flash('Administracion registrada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='administraciones'))


@app.route('/paciente/<int:pid>/administracion/<int:aid>/editar', methods=['POST'])
def editar_administracion(pid, aid):
    adm = Administracion.query.get_or_404(aid)
    dosis = request.form.get('dosis_mg', '').strip()
    med = request.form['medicamento'].strip()
    equivs = cargar_equivs()
    adm.medicamento = med
    adm.medicamento_generico = resolver_generico(med, equivs)
    adm.dosis_mg = float(dosis) if dosis else None
    adm.fecha = normalize_date_input(request.form['fecha'])
    adm.hora = request.form.get('hora', '').strip()
    adm.enfermero = request.form.get('enfermero', '').strip()
    adm.notas = request.form.get('notas', '').strip()
    db.session.commit()
    flash('Administracion actualizada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='administraciones'))


@app.route('/paciente/<int:pid>/administracion/<int:aid>/eliminar', methods=['POST'])
def eliminar_administracion(pid, aid):
    adm = Administracion.query.get_or_404(aid)
    db.session.delete(adm)
    db.session.commit()
    flash('Administracion eliminada.', 'success')
    return redirect(url_for('paciente', pid=pid, tab='administraciones'))


def init_db():
    db.create_all()
    if Equivalencia.query.count() == 0:
        for patron, generico in EQUIV_DEFAULT:
            db.session.add(Equivalencia(patron=patron, generico=generico))
        db.session.commit()
        print(f'[init] {len(EQUIV_DEFAULT)} equivalencias cargadas.')


if __name__ == '__main__':
    with app.app_context():
        init_db()
    print('\n' + '=' * 50)
    print('  MedControl arrancando...')
    print('  Abrir: http://localhost:5000')
    print('=' * 50 + '\n')
    app.run(debug=True, port=5000)
