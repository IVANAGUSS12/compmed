from datetime import datetime

from extensions import db


class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20))
    fecha_ingreso = db.Column(db.String(20))
    fecha_egreso = db.Column(db.String(20))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    indicaciones = db.relationship('Indicacion', backref='paciente', lazy=True, cascade='all,delete')
    administraciones = db.relationship('Administracion', backref='paciente', lazy=True, cascade='all,delete')


class Indicacion(db.Model):
    """Lo que indica el medico cada dia."""

    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    medico = db.Column(db.String(200))
    medicamento = db.Column(db.String(200), nullable=False)
    dosis_mg = db.Column(db.Float)
    frecuencia_horas = db.Column(db.Float)
    via = db.Column(db.String(50))
    notas = db.Column(db.Text)


class Administracion(db.Model):
    """Lo que realmente se le dio al paciente."""

    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    hora = db.Column(db.String(10))
    enfermero = db.Column(db.String(200))
    medicamento = db.Column(db.String(300), nullable=False)
    medicamento_generico = db.Column(db.String(200))
    dosis_mg = db.Column(db.Float)
    notas = db.Column(db.Text)


class Equivalencia(db.Model):
    """Mapeo de nombre comercial a nombre generico para comparacion."""

    id = db.Column(db.Integer, primary_key=True)
    patron = db.Column(db.String(200), nullable=False, unique=True)
    generico = db.Column(db.String(200), nullable=False)
    activa = db.Column(db.Boolean, default=True)


EQUIV_DEFAULT = [
    ('HOLOMAGNESIO', 'MAGNESIO'),
    ('FRIDALIT', 'HIDROCORTISONA'),
    ('CUBICIN', 'DAPTOMICINA'),
    ('CANCIDAS', 'CASPOFUNGIN'),
    ('SOBRIUS', 'HEPARINA SODICA'),
    ('FLOXLEVO', 'LEVOFLOXACINA'),
    ('UNIFLOX', 'LEVOFLOXACINA'),
    ('AMINOXIDIN', 'AMPICILINA SULBACTAM'),
    ('DRENIX', 'MINOCICLINA'),
    ('BACTRIM', 'SULFAMETOXAZOL TRIMETOPRIMA'),
    ('CLEXANE', 'ENOXAPARINA SODICA'),
    ('HEMAX', 'ERITROPOYETINA'),
    ('ATLANSIL', 'AMIODARONA'),
    ('PROGRAF', 'TACROLIMUS'),
    ('LA MEPREDNISONA', 'MEPREDNISONA'),
    ('DELTISONA', 'MEPREDNISONA'),
    ('ACIFOL', 'ACIDO FOLICO'),
    ('ACIDO FOLICO VANNIER', 'ACIDO FOLICO'),
    ('PROCELAC', 'OMEPRAZOL'),
    ('MEROEFECTIL', 'MEROPENEM'),
    ('SULFATO DE MAGNESIO', 'MAGNESIO SULFATO'),
]
