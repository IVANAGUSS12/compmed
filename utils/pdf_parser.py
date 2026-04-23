# -*- coding: utf-8 -*-
"""
Módulo de lectura de PDFs con OCR (easyocr + PyMuPDF).
Parsea dos tipos de PDF:
  - 'indicaciones': planilla de administrados + indicaciones médicas (del sistema del hospital)
  - 'facturados':   liquidación CEMIC (medicamentos y material facturado)
"""

import re
import sys
import io
import warnings
import fitz  # PyMuPDF

warnings.filterwarnings('ignore')

_reader = None


def get_reader():
    """Carga el modelo de OCR (solo la primera vez; se reutiliza)."""
    global _reader
    if _reader is None:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            import easyocr
            _reader = easyocr.Reader(['es'], gpu=False, verbose=False)
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
    return _reader


def _ocr_page(page, zoom=1.8):
    """Renderiza una página del PDF y corre OCR. Devuelve list de (x, y, texto)."""
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    reader = get_reader()
    results = reader.readtext(pix.tobytes('png'))
    items = []
    for bbox, text, conf in results:
        if conf < 0.2 or not text.strip():
            continue
        x = bbox[0][0]
        y = (bbox[0][1] + bbox[2][1]) / 2
        items.append((x, y, text.strip()))
    return items


def _page_lines(page, zoom=1.8, use_ocr_fallback=True):
    """Usa texto nativo primero. Si no alcanza, opcionalmente cae a OCR."""
    native = page.get_text('text') or ''
    native_lines = [re.sub(r'\s+', ' ', ln).strip() for ln in native.splitlines()]
    native_lines = [ln for ln in native_lines if ln]
    if len(native_lines) >= 2:
        return native_lines
    if not use_ocr_fallback:
        return native_lines
    return _group_rows(_ocr_page(page, zoom=zoom))


def _group_rows(items, y_tol=14):
    """Agrupa los tokens OCR por fila (mismo Y aproximado) y los ordena por X."""
    buckets = {}
    for x, y, text in items:
        assigned = False
        for yk in buckets:
            if abs(yk - y) < y_tol:
                buckets[yk].append((x, text))
                assigned = True
                break
        if not assigned:
            buckets[y] = [(x, text)]

    rows = []
    for yk in sorted(buckets.keys()):
        line = ' '.join(t for x, t in sorted(buckets[yk]))
        line = re.sub(r'\s+', ' ', line).strip()
        if line:
            rows.append(line)
    return rows


# ── Patrones ────────────────────────────────────────────────────────────────

RE_DATE_LONG  = re.compile(r'\b(\d{1,2})[/\-](\d{2})[/\-](\d{4})\b')
RE_DATE_SHORT = re.compile(r'\b(\d{1,2})[/\-](\d{2})[/\-](\d{2})\b')
RE_TIME       = re.compile(r'^(\d{1,2})[:.\-,](\d{2})')
RE_REMITO     = re.compile(r'\b(\d{5,7})\b')
RE_FOOTER     = re.compile(r'(usuario|impresion|impresión|pagina|página|pág)', re.I)
RE_PRECIO     = re.compile(r'\d[\d\.\s,]+\d\s*$')


def _normalize_date(s):
    """Extrae y normaliza fecha como dd/mm/aaaa. Asume 2026 para años de 2 dígitos."""
    m = RE_DATE_LONG.search(s)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}/{m.group(3)}"
    m = RE_DATE_SHORT.search(s)
    if m:
        year = m.group(3)
        year4 = f"20{year}" if len(year) == 2 else year
        return f"{int(m.group(1)):02d}/{m.group(2)}/{year4}"
    return None


def _is_standalone_date(line):
    """True si la línea es solo una fecha (posiblemente con poco ruido)."""
    clean = re.sub(r'[^0-9/\-]', '', line)
    return bool(RE_DATE_SHORT.fullmatch(clean) or RE_DATE_LONG.fullmatch(clean))


def _limpiar_nombre(nombre):
    """Elimina artefactos comunes del OCR en nombres de medicamentos."""
    # Quitar números sueltos al inicio (cantidades: "32 SONDA" → "SONDA")
    nombre = re.sub(r'^\d{1,3}\s+', '', nombre)
    # Quitar caracteres raros frecuentes en OCR
    nombre = re.sub(r'[|_\[\]{}]', ' ', nombre)
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    return nombre


# ── Parser de INDICACIONES (planilla de enfermería + indicaciones médicas) ──

def parse_indicaciones(pdf_path, callback=None, zoom=1.8, use_ocr_fallback=True):
    """
    Lee el PDF de indicaciones y devuelve dos listas:
      - administrados: [{fecha, hora_enfermero, nombre_original}]
      - indicados:     [{fecha, medico, droga, dosis_via}]
    callback(n_page, total): función opcional para reportar progreso.
    """
    doc = fitz.open(pdf_path)
    total = len(doc)

    administrados = []
    indicados = []

    for pi in range(total):
        if callback:
            callback(pi + 1, total)

        page = doc[pi]
        lines = _page_lines(page, zoom=zoom, use_ocr_fallback=use_ocr_fallback)

        current_date = None
        section = None   # 'administrados' | 'farmacologicas' | 'enfermeria' | None
        pending_enfermero = None

        i = 0
        while i < len(lines):
            line = lines[i]
            line_up = line.upper()

            # Ignorar pies de página
            if RE_FOOTER.search(line) and len(line) > 40:
                i += 1
                continue

            # ── Detectar fecha de sección ──
            if _is_standalone_date(line) or (
                RE_DATE_SHORT.search(line) and len(line.replace(' ', '')) <= 10
            ):
                d = _normalize_date(line)
                if d:
                    current_date = d
                    section = None
                    pending_enfermero = None
                    i += 1
                    continue

            # ── Detectar encabezados de sección ──
            if 'MEDICAMENTOS ADMINISTRADOS' in line_up:
                section = 'administrados'
                pending_enfermero = None
                i += 1
                continue
            if 'INDICACIONES FARMACOLOGICAS' in line_up or \
               'INDICACION FARMACOLOGICA' in line_up or \
               'FARMACOLOGICA' in line_up:
                section = 'farmacologicas'
                pending_enfermero = None
                i += 1
                continue
            if 'INDICACIONES ENFERMERIA' in line_up or \
               'INDICACION ENFERMERIA' in line_up:
                section = 'enfermeria'
                pending_enfermero = None
                i += 1
                continue
            if line_up.strip() in ('INDICACIONES', 'INDICACION'):
                section = None
                pending_enfermero = None
                i += 1
                continue

            # ── Parsear MEDICAMENTOS ADMINISTRADOS ──
            if section == 'administrados' and current_date:
                if RE_TIME.match(line):
                    # Es línea de hora + enfermero
                    pending_enfermero = line
                    i += 1
                    continue
                elif pending_enfermero:
                    # Esta línea es el nombre del medicamento
                    nombre = _limpiar_nombre(line)
                    if len(nombre) >= 4 and not RE_TIME.match(line):
                        administrados.append({
                            'fecha': current_date,
                            'hora_enfermero': pending_enfermero,
                            'nombre_original': nombre,
                        })
                    pending_enfermero = None
                    i += 1
                    continue

            # ── Parsear INDICACIONES FARMACOLOGICAS ──
            if section == 'farmacologicas' and current_date:
                if RE_TIME.match(line) or 'M.N' in line_up:
                    # Línea del médico
                    # Extraer nombre del médico (antes del "[M.N")
                    medico = re.sub(r'\[.*', '', line).strip()
                    medico = re.sub(r'^\d{1,2}[:.\-,]\d{2}\s*[-–]?\s*', '', medico).strip()
                    medico = re.sub(r'\s+', ' ', medico).strip()
                    pending_enfermero = medico
                    i += 1
                    continue
                elif pending_enfermero:
                    droga_raw = line
                    # Separar dosis/vía si hay patrón "CADA:" o "A LAS"
                    dosis = ''
                    m_cada = re.search(r'(CADA\s*:\s*.+|A\s+LAS\s+.+|SUBCUTANEA.+|INTRAVENOSA.+|ORAL.+|VIA\s+.+)', droga_raw, re.I)
                    if m_cada:
                        dosis = droga_raw[m_cada.start():].strip()
                        droga_raw = droga_raw[:m_cada.start()].strip()
                    droga = _limpiar_nombre(droga_raw)
                    if len(droga) >= 3:
                        indicados.append({
                            'fecha': current_date,
                            'medico': pending_enfermero,
                            'droga': droga,
                            'dosis_via': dosis,
                        })
                    pending_enfermero = None
                    i += 1
                    continue

            i += 1

    doc.close()
    return administrados, indicados


# ── Parser de FACTURADOS (liquidación CEMIC) ────────────────────────────────

def parse_facturados(pdf_path, callback=None, zoom=1.8, use_ocr_fallback=True):
    """
    Lee el PDF de liquidación CEMIC y devuelve:
      [{fecha, nombre, cantidad, codigo, valor}]
    Solo extrae la sección "MEDICAMENTOS SALA" (no descartables).
    callback(n_page, total): función opcional para reportar progreso.
    """
    doc = fitz.open(pdf_path)
    total = len(doc)
    results = []
    in_med_section = False
    pending_nombre = None   # nombre que quedó en la línea anterior sin fecha

    for pi in range(total):
        if callback:
            callback(pi + 1, total)

        page = doc[pi]
        lines = _page_lines(page, zoom=zoom, use_ocr_fallback=use_ocr_fallback)

        for line in lines:
            line_up = line.upper()

            # Detectar inicio de sección de medicamentos
            if ('MEDICAMENTOS' in line_up and 'SALA' in line_up and 'DESCART' not in line_up):
                in_med_section = True
                pending_nombre = None
                continue

            # Ignorar explícitamente la sección de descartables
            if 'DESCARTABLES' in line_up and 'SALA' in line_up:
                in_med_section = False
                pending_nombre = None
                continue

            # Detectar fin de la sección de medicamentos (totales finales)
            if in_med_section and re.match(r'^\s*TOTAL\b', line_up) and len(line) < 30:
                in_med_section = False
                pending_nombre = None
                continue

            # Saltar encabezados de páginas
            if any(h in line_up for h in ['LIQUIDACION DE', 'PACIENTE', 'ACMED', 'C.E.M.I']):
                continue

            if not in_med_section:
                continue

            # Cinturón adicional: si aparece texto de descartables dentro de la sección, descartar
            if 'DESCART' in line_up:
                continue

            # Saltar líneas de transporte/totales parciales
            if 'TRANSP' in line_up and 'MEDICAM' in line_up:
                continue

            # Intentar extraer: NOMBRE + REMITO + FECHA + PRECIO
            remito_m = RE_REMITO.search(line)
            fecha = _normalize_date(line)

            if remito_m and fecha:
                # Línea completa: nombre + remito + fecha [+ precio]
                nombre_raw = line[:remito_m.start()].strip()
                if pending_nombre:
                    # La línea anterior tenía el nombre sin fecha → es parte de este registro
                    nombre_raw = pending_nombre + ' ' + nombre_raw
                    pending_nombre = None
                nombre = _limpiar_nombre(nombre_raw)
                if len(nombre) >= 3:
                    results.append({
                        'fecha': fecha,
                        'nombre': nombre,
                        'cantidad': 1,
                        'codigo': remito_m.group(1),
                        'valor': '',
                    })
            elif remito_m and not fecha:
                # Tiene remito pero no fecha → probablemente nombre y remito, fecha en la próxima línea
                nombre_raw = line[:remito_m.start()].strip()
                if len(nombre_raw) >= 3:
                    pending_nombre = _limpiar_nombre(nombre_raw)
                else:
                    pending_nombre = None
            elif fecha and pending_nombre:
                # Línea solo con fecha (continuación del registro anterior)
                results.append({
                    'fecha': fecha,
                    'nombre': pending_nombre,
                    'cantidad': 1,
                    'codigo': '',
                    'valor': '',
                })
                pending_nombre = None
            else:
                # Línea de solo nombre (sin remito ni fecha aún)
                if len(line) >= 4 and not RE_FOOTER.search(line):
                    pending_nombre = _limpiar_nombre(line)

    doc.close()
    return results
