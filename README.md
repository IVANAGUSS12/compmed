# MedControl

Aplicacion Flask para auditoria de medicamentos.

Incluye:

- Carga y gestion de pacientes.
- Importacion de PDF de internacion (indicaciones + administraciones).
- Comparacion de dosis (ok, incompleto, falta, sin_datos).
- Filtros por estado y frecuencia semanal.
- Tests unitarios de la logica critica de comparacion.

## Arquitectura

La app esta separada por responsabilidades:

- `app.py`: capa web Flask (rutas y orquestacion).
- `extensions.py`: inicializacion de extensiones (`SQLAlchemy`).
- `models.py`: entidades y tabla de equivalencias por defecto.
- `services/date_utils.py`: normalizacion y parseo de fechas.
- `services/equivalencias.py`: resolucion de nombre comercial -> generico.
- `services/comparacion.py`: reglas de negocio de comparacion de dosis.
- `services/importacion.py`: flujo de importacion de PDF a entidades.
- `utils/pdf_parser.py`: parser unificado de PDF (`parsear_pdf_internacion`).
- `tests/test_comparacion_service.py`: tests unitarios de negocio.

## Requisitos

- Windows 10/11 (o Linux/macOS con ajustes de script)
- Python 3.11+
- Git

## Inicio rapido (Windows)

1. Clonar repo.
2. Doble click en `iniciar.bat`.
3. Abrir `http://127.0.0.1:5000`.

El script:

- crea `.venv` si no existe,
- instala dependencias de `requirements.txt`,
- levanta la app.

## Inicio manual

```powershell
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

## Notas importantes

- La primera vez que se usa OCR (`easyocr`) puede tardar mas porque descarga/carga modelos.
- La base SQLite se guarda en `data/medcontrol_v2.db`.
- `uploads/` y la DB estan ignorados por Git para no subir datos sensibles.

## Tests

Ejecutar:

```powershell
pytest
```

Los tests actuales cubren los casos criticos de `comparar_indicaciones_administraciones`:

- frecuencia c/48 hs,
- LMV (semanal),
- infusion continua,
- equivalencia de mg (2x25 = 50),
- dosis incompleta por conteo.

## Preparado para GitHub

Para subir:

```powershell
git init
git add .
git commit -m "MedControl listo para despliegue"
```

Luego crear repo remoto y hacer push.
