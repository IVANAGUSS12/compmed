# MedControl

Aplicacion Flask para auditoria de medicamentos:

- Carga de paciente.
- Importacion de PDFs (indicaciones + facturados).
- Equivalencias de nombres comerciales a facturados.
- Control cruzado y exportaciones (Excel/PDF).

## Requisitos

- Windows 10/11 (o Linux/macOS con ajustes de script)
- Python 3.11+ (probado con 3.14)
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
- La base SQLite se guarda en `data/medcontrol.db`.
- `uploads/` y la DB estan ignorados por Git para no subir datos sensibles.

## Estructura principal

- `app.py`: backend Flask y rutas.
- `utils/pdf_parser.py`: parsing OCR de PDFs.
- `utils/excel_gen.py`: exportacion Excel.
- `templates/`: vistas HTML.
- `iniciar.bat`: bootstrap para Windows.

## Preparado para GitHub

Para subir:

```powershell
git init
git add .
git commit -m "MedControl listo para despliegue"
```

Luego crear repo remoto y hacer push.
