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


# ── Parser unificado de internacion (indicaciones + administraciones) ───────

def _extraer_droga_indicacion_internacion(linea):
    """
    Parsea una linea de indicacion farmacologica y devuelve:
    (medicamento, dosis_mg, frecuencia_horas, via, nota_original)
    """
    orig = linea.strip()
    linea = re.sub(r'^EN AYUNAS:\s*', '', orig, flags=re.I).strip()
    linea = re.sub(r'\.\s*$', '', linea).strip()

    freq = None
    m_cada = re.search(r'CADA:\s*(\d+(?:[.,]\d+)?)\s*H', linea, re.I)
    if m_cada:
        freq = float(m_cada.group(1).replace(',', '.'))
    elif re.search(r'A LAS\s+\d{1,2}:\d{2}', linea, re.I):
        freq = 24.0

    dosis_mg = None
    m_mg = re.search(r'(\d+(?:[.,]\d+)?)\s*MG\b', linea, re.I)
    if m_mg:
        dosis_mg = float(m_mg.group(1).replace(',', '.'))
    else:
        m_ui = re.search(r'(\d+(?:[.,]\d+)?)\s*UI\b', linea, re.I)
        if m_ui:
            dosis_mg = float(m_ui.group(1).replace(',', '.'))

    via = None
    for v in ('INTRAVENOSA', 'ORAL', 'SUBCUTANEA', 'INTRAMUSCULAR', 'TOPICA', 'NASAL'):
        if v.lower() in linea.lower():
            via = v
            break

    m_pos = re.search(r'\b\d+(?:[.,/]\d+)?\s*(?:MG|UI|MEQ|GR|ML)\b', linea, re.I)
    if m_pos:
        droga = linea[:m_pos.start()].strip().rstrip(',').strip()
    else:
        droga = re.split(
            r'\s+(?:CADA|ORAL|INTRAVENOSA|SUBCUTANEA|AMPOLLA|COMPRIMIDO|CAPSULA|FRASCO|INFUSION)\b',
            linea,
            1,
            flags=re.I,
        )[0].strip()

    droga = re.sub(r'\s+', ' ', droga).strip()

    if re.search(r'LUNES|MIERCOLES|VIERNES|LMV', linea, re.I):
        freq = None
    elif re.search(r'CONTINUA', linea, re.I):
        freq = None

    return droga, dosis_mg, freq, via, orig


def _extraer_dosis_comercial_internacion(nombre):
    """Extrae mg/UI y cantidad final de un nombre comercial."""
    s = nombre.strip().upper()
    m_qty = re.search(r'X\s+(\d+)\s*$', s)
    qty = int(m_qty.group(1)) if m_qty else 1

    m_mg = re.search(r'(\d+(?:[.,]\d+)?)\s*MG\b', s)
    if m_mg:
        mg = float(m_mg.group(1).replace(',', '.'))
        return mg, qty, mg * qty

    m_ui = re.search(r'(\d+(?:[.,]\d+)?)\s*UI\b', s)
    if m_ui:
        ui = float(m_ui.group(1).replace(',', '.'))
        return ui, qty, ui * qty

    return None, qty, None


def parsear_pdf_internacion(pdf_path, callback=None, zoom=1.8, use_ocr_fallback=True):
    """
    Parsea un PDF de internacion y devuelve:
    (paciente_info, indicaciones, administraciones)
    """
    doc = fitz.open(pdf_path)
    total = len(doc)

    all_lines = []
    for pi in range(total):
        if callback:
            callback(pi + 1, total)
        page = doc[pi]
        all_lines.extend(_page_lines(page, zoom=zoom, use_ocr_fallback=use_ocr_fallback))
    doc.close()

    paciente_info = {'nombre': '', 'apellido': '', 'dni': ''}
    for i, line in enumerate(all_lines[:60]):
        line = line.strip()
        if line == 'Paciente:' and i + 1 < len(all_lines):
            nombre_completo = all_lines[i + 1].strip()
            partes = nombre_completo.split(',', 1)
            paciente_info['apellido'] = partes[0].strip()
            paciente_info['nombre'] = partes[1].strip() if len(partes) > 1 else ''
        elif line == 'DNI:' and i + 1 < len(all_lines):
            paciente_info['dni'] = all_lines[i + 1].strip()

    indicaciones = []
    administraciones = []

    fecha_actual = None
    seccion = None
    medico_actual = None

    skip = {
        'INTERNACION', 'Paciente:', 'DNI:', 'Fecha Nac.:', 'Edad:', 'Sexo:',
        'Nro. HC Anterior:', 'INDICACIONES', 'INDICACIONES ENFERMERIA',
        'INDICACIONES NUTRICION', 'INDICACIONES FARMACOLOGICAS',
        'MEDICAMENTOS ADMINISTRADOS', 'NEFROPROTECTOR',
    }

    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()

        if not line or 'Usuario Impresi' in line or 'Fecha Impresi' in line or 'Pagina' in line or 'Página' in line:
            i += 1
            continue

        if line == 'INTERNACION':
            seccion = None
            i += 1
            continue

        if line in skip or line in ('CABECERA A 30°', 'CABECERA A 30\u00b0'):
            if line == 'INDICACIONES FARMACOLOGICAS':
                seccion = 'ind'
            elif line == 'MEDICAMENTOS ADMINISTRADOS':
                seccion = 'adm'
            elif line in ('INDICACIONES ENFERMERIA', 'INDICACIONES NUTRICION'):
                seccion = None
            i += 1
            continue

        if re.match(r'^\d{7,9}$', line):
            i += 1
            continue
        if re.match(r'^\d{2}/\d{2}/\d{4}$', line) and not fecha_actual:
            i += 1
            continue
        if line in ('MASCULINO', 'FEMENINO'):
            i += 1
            continue

        m_fecha = re.match(r'^(\d{2})/(\d{2})/(\d{2,4})$', line)
        if m_fecha:
            d, mo, y = m_fecha.groups()
            if len(y) == 2:
                y = '20' + y
            fecha_actual = f'{d}/{mo}/{y}'
            seccion = None
            medico_actual = None
            i += 1
            continue

        if 'INDICACIONES FARMACOLOGICAS' in line:
            seccion = 'ind'
            i += 1
            continue
        if 'MEDICAMENTOS ADMINISTRADOS' in line:
            seccion = 'adm'
            i += 1
            continue
        if re.match(r'^INDICACIONES\b', line):
            if 'FARMACOLOGICAS' not in line:
                seccion = None
            i += 1
            continue

        if not fecha_actual:
            i += 1
            continue

        if seccion == 'ind':
            m_doc = re.match(r'^\d{1,2}:\d{2}\s+(.+?)\s*\[M\.N\.:', line)
            if m_doc:
                medico_actual = m_doc.group(1).strip()
                i += 1
                continue

            if re.match(r'^CONTROL\b', line, re.I):
                i += 1
                continue
            if re.match(r'^\d+$', line) or re.match(r'^\d{2}/\d{2}', line):
                i += 1
                continue

            drug_markers = re.compile(
                r'\b(?:MG|UI|MEQ|GR|ML|ORAL|INTRAVENOSA|SUBCUTANEA|INTRAMUSCULAR|'
                r'AMPOLLA|COMPRIMIDO|CAPSULA|FRASCO|INFUSION|CADA|JERINGA)\b',
                re.I,
            )
            if len(line) >= 5 and drug_markers.search(line):
                droga, dosis_mg, freq, via, notas = _extraer_droga_indicacion_internacion(line)
                if droga and len(droga) >= 3:
                    indicaciones.append(
                        {
                            'fecha': fecha_actual,
                            'medico': medico_actual or '',
                            'medicamento': droga,
                            'dosis_mg': dosis_mg,
                            'frecuencia_horas': freq,
                            'via': via or '',
                            'notas': notas,
                        }
                    )

        elif seccion == 'adm':
            m_adm = re.match(r'^(\d{1,2}:\d{2})\s*-\s*(.+)$', line)
            if m_adm:
                hora = m_adm.group(1)
                enfermero = m_adm.group(2).strip()
                j = i + 1
                while j < len(all_lines) and not all_lines[j].strip():
                    j += 1
                if j < len(all_lines):
                    drug_line = all_lines[j].strip()
                    if (
                        drug_line
                        and not re.match(r'^\d{1,2}:\d{2}', drug_line)
                        and drug_line not in skip
                        and 'Usuario Impresi' not in drug_line
                    ):
                        _, _, total_mg = _extraer_dosis_comercial_internacion(drug_line)
                        administraciones.append(
                            {
                                'fecha': fecha_actual,
                                'hora': hora,
                                'enfermero': enfermero,
                                'medicamento': drug_line,
                                'dosis_mg': total_mg,
                            }
                        )
                        i = j + 1
                        continue

        i += 1

    return paciente_info, indicaciones, administraciones
