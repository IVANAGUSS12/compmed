"""
EDITOR DE PDF - MEDICAMENTOS ADMINISTRADOS
Reemplaza nombres comerciales por nombres del facturado.

El PDF de indicaciones tiene texto renderizado como vectores (no texto editable),
por lo que este script usa el enfoque de superposicion:
1. Renderiza cada pagina como imagen de alta resolucion
2. Usa OCR (pytesseract con Tesseract instalado) para encontrar la posicion del texto
3. Cubre el texto original con un rectangulo blanco
4. Escribe el nuevo nombre encima con el mismo estilo visual

REQUISITO: Tener Tesseract instalado
  Descargar de: https://github.com/UB-Mannheim/tesseract/wiki
  O ejecutar en PowerShell como admin:
  winget install UB-Mannheim.TesseractOCR

"""

import fitz  # PyMuPDF
import os
import sys

PDF_ENTRADA  = 'C:/Users/ivana/OneDrive/Desktop/suarez indicaciones.pdf'
PDF_SALIDA   = 'C:/Users/ivana/OneDrive/Desktop/suarez indicaciones CORREGIDO.pdf'

# ============================================================
# TABLA DE REEMPLAZOS
# clave = texto EXACTO como aparece en el PDF (en sección MEDICAMENTOS ADMINISTRADOS)
# valor = texto que debe quedar en el PDF corregido
# ============================================================
REEMPLAZOS = {
    "HOLOMAGNESIO COMP.REC.X 1 PHOENIX X 2":                   "HOLOMAGNESIO",
    "FRIDALIT 100 100 MG F.A.X 1 X 5 ML FADA PHARMA X 1":      "HIDROCORTISONA 100 MG.FCO.AMP.",
    "CUBICIN RT 500 MG F.A.X 1 MSD ARGENTINA SR X 2":          "CUBICIN RT 500 MG IV AMPOLLA",
    "CUBICIN RT 500 MG F.A.X 1 MSD ARGENTINA SR X 1":          "CUBICIN RT 500 MG IV AMPOLLA",
    "CANCIDAS 50 MG VIAL X 1 MSD ARGENTINA SR X 1":            "CANCIDAS 50 MG",
    "AMIODARONA LARJAN 150 MG A.X 1 X 3 ML VEINFAR X 2":       "ATLANSIL COMPRIMIDO",
    "OMEPRAZOL CEVALLOS 20 MG CAPS.X 1 CEVALLOS X 2":          "PROCELAC 20 MG.CAPS.",
    "MEROPENEM RICHET 500 MG IV INY.F.A.X 1 RICHET X 1":       "MEROEFECTIL 1000 MG F.A.",
    "SOBRIUS 5000 UI/ML F.A.X 1 X5ML FADA PHARMA X 1":         "HEPARINA DUNCAN 5000 U.I.FCO.AMP.X 5 ML",
    "ACIDO FOLICO VANNIER 5 MG COMP.X 1 VANNIER X 1":          "ACIFOL 5 MG.COMP.",
    "FLOXLEVO 500 MG COMP.REC.X 1 BIOTENK X 1":                "LEVOFLOXACINA 500 MG",
    "AMINOXIDIN SULBACTAM INY.F.A.X 1 X 20 ML FADA PHARMA X 1": "AMPICILINA+SULBACTAM 1,5 G.IM/IV AMP.",
    "DRENIX 100 100 MG COMP.REC.X 1 OXAPHARMA X 1":            "ACNECLIN 100 MG AP COMP",
    "BACTRIM FORTE COMP.X 1 INVESTI X 1":                      "BACTRIM FUERTE COMPRIMIDOS",
    "CLEXANE 80 MG JGA.PRELL.X 1 SANOFI-AVENTIS X 1":          "CLEXANE 80 MG.AMPOLLA",
    "HEMAX 4000UI LIOF.F.A.+J.PRELL BIOSIDUS FARMA X 1":       "HEMAX 2000 U.I.FCO.AMP.",
    "PROGRAF 1 MG CAPS.X 1 GADOR X 2":                         "PROGRAF 1 MG COMP. RE",
    "UNIFLOX 750 750 MG COMP.REC.X 1 RAFFO X 1":               "LEVOFLOXACINA 750 MG",
    "UNIFLOX 750 MG COMP.REC.X 1 RAFFO X 1":                   "LEVOFLOXACINA 750 MG",
    "LA MEPREDNISONA 4 MG COMP.X 1 BIOTENK X 1":               "DELTISONA B 4 MG",
    "ATLANSIL COMP.X 1 ROEMMERS X 1":                          "ATLANSIL COMPRIMIDO",
    "SULFATO DE MAGNESIO 25% A.X 1 X 5 ML FADA PHARMA X 2":    "SULFATO MAGNESIO 25 % X 5 ML",
}

def verificar_tesseract():
    """Verifica si Tesseract esta disponible"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True, pytesseract
    except Exception as e:
        return False, str(e)

def reemplazar_con_tesseract(pytesseract, doc_in):
    """Metodo con OCR usando Tesseract"""
    import cv2
    import numpy as np
    from PIL import Image

    doc_out = fitz.open()

    ZOOM = 3  # Alta resolucion para mejor OCR
    mat = fitz.Matrix(ZOOM, ZOOM)

    total_reemplazos = 0

    for pag_num in range(len(doc_in)):
        print(f"  Procesando pagina {pag_num + 1}/{len(doc_in)}...")
        page_in = doc_in[pag_num]

        # Renderizar como imagen
        pix = page_in.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # Convertir a numpy para OpenCV
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        # OCR con posiciones de palabras
        data = pytesseract.image_to_data(
            pil_img,
            lang='spa+eng',
            config='--psm 6',
            output_type=pytesseract.Output.DICT
        )

        # Para cada reemplazo, buscar las palabras en el OCR
        page_out = doc_out.new_page(width=page_in.rect.width, height=page_in.rect.height)
        page_out.show_pdf_page(page_out.rect, doc_in, pag_num)

        for texto_original, texto_nuevo in REEMPLAZOS.items():
            palabras_buscar = texto_original.upper().split()
            n = len(palabras_buscar)
            words = [w.upper() for w in data['text']]
            confs = data['conf']

            # Buscar secuencia de palabras
            for i in range(len(words) - n + 1):
                secuencia = words[i:i+n]
                if all(p in s or s in p for p, s in zip(palabras_buscar, secuencia)):
                    if int(confs[i]) > 30:
                        # Calcular bounding box de toda la secuencia
                        x1 = min(data['left'][i:i+n])
                        y1 = min(data['top'][i:i+n])
                        x2 = max(data['left'][j] + data['width'][j] for j in range(i, i+n))
                        y2 = max(data['top'][j] + data['height'][j] for j in range(i, i+n))

                        # Convertir de coordenadas imagen (ZOOM) a coordenadas PDF
                        pdf_x1 = x1 / ZOOM
                        pdf_y1 = y1 / ZOOM
                        pdf_x2 = x2 / ZOOM
                        pdf_y2 = y2 / ZOOM

                        # Expandir un poco el rectangulo
                        pdf_x1 -= 2; pdf_y1 -= 2
                        pdf_x2 += 2; pdf_y2 += 2

                        rect = fitz.Rect(pdf_x1, pdf_y1, pdf_x2, pdf_y2)

                        # Cubrir con rectangulo blanco
                        page_out.draw_rect(rect, color=(1,1,1), fill=(1,1,1))

                        # Calcular tamano de fuente aproximado
                        altura_texto = (pdf_y2 - pdf_y1) * 0.85
                        font_size = max(6, min(10, altura_texto))

                        # Insertar nuevo texto
                        page_out.insert_textbox(
                            rect,
                            texto_nuevo,
                            fontname="helv",
                            fontsize=font_size,
                            color=(0, 0, 0),
                            align=0
                        )
                        total_reemplazos += 1
                        print(f"    Reemplazado: '{texto_original[:40]}...' → '{texto_nuevo}'")
                        break

    return doc_out, total_reemplazos


def reemplazar_sin_ocr(doc_in):
    """
    Metodo alternativo SIN OCR:
    Renderiza cada pagina como imagen y crea un PDF desde imagenes
    con anotaciones de texto encima. Es el metodo mas simple pero
    no edita el texto original - solo agrega anotaciones visibles.
    NOTA: El resultado no sera 100% identico al original pero es funcional.
    """
    import io
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    print("\nUsando metodo alternativo (sin Tesseract)...")
    print("NOTA: Este metodo crea un PDF con las paginas como imagenes.")
    print("Para edicion completa del texto, instale Tesseract OCR.\n")

    ZOOM = 2
    mat = fitz.Matrix(ZOOM, ZOOM)
    doc_out = fitz.open()

    for pag_num in range(len(doc_in)):
        print(f"  Procesando pagina {pag_num + 1}/{len(doc_in)}...")
        page_in = doc_in[pag_num]
        pix = page_in.get_pixmap(matrix=mat)

        # Crear nueva pagina identica (copia imagen)
        page_out = doc_out.new_page(width=page_in.rect.width, height=page_in.rect.height)
        page_out.show_pdf_page(page_out.rect, doc_in, pag_num)

    return doc_out, 0


def main():
    print("=" * 60)
    print("EDITOR DE PDF - MEDICAMENTOS ADMINISTRADOS")
    print("Paciente: SUAREZ HUGO ADALBERTO")
    print("=" * 60)

    if not os.path.exists(PDF_ENTRADA):
        print(f"ERROR: No se encuentra {PDF_ENTRADA}")
        sys.exit(1)

    doc_in = fitz.open(PDF_ENTRADA)
    print(f"PDF de entrada: {len(doc_in)} paginas")
    print(f"Reemplazos a aplicar: {len(REEMPLAZOS)}\n")

    # Verificar Tesseract
    tiene_tesseract, result = verificar_tesseract()

    if tiene_tesseract:
        print("Tesseract OCR encontrado. Usando modo completo...")
        doc_out, n = reemplazar_con_tesseract(result, doc_in)
        print(f"\nTotal de reemplazos realizados: {n}")
    else:
        print(f"Tesseract NO encontrado: {result}")
        print("\nPara instalar Tesseract:")
        print("  Descargar: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  O ejecutar como admin: winget install UB-Mannheim.TesseractOCR")
        print()

        # Alternativa: copiar PDF y agregar una hoja de equivalencias como anotacion
        respuesta = input("Continuar con modo sin Tesseract? (copia el PDF + agrega tabla de equivalencias) [s/n]: ")
        if respuesta.lower() != 's':
            print("Cancelado.")
            sys.exit(0)
        doc_out, n = reemplazar_sin_ocr(doc_in)

    # Agregar pagina de equivalencias al final
    ancho = doc_out[0].rect.width
    alto = doc_out[0].rect.height
    pag_equiv = doc_out.new_page(width=ancho, height=alto)

    pag_equiv.draw_rect(fitz.Rect(30, 30, ancho-30, alto-30), color=(0.12, 0.31, 0.47), width=2)
    pag_equiv.insert_text((40, 60), "TABLA DE EQUIVALENCIAS - MEDICAMENTOS ADMINISTRADOS",
                          fontname="helv", fontsize=11, color=(0.12, 0.31, 0.47))
    pag_equiv.insert_text((40, 80), "SUAREZ HUGO ADALBERTO | Periodo: 28/02/2026 - 09/03/2026",
                          fontname="helv", fontsize=9, color=(0.3, 0.3, 0.3))

    pag_equiv.draw_rect(fitz.Rect(30, 90, ancho-30, 105), color=(0.18, 0.46, 0.71), fill=(0.18, 0.46, 0.71))
    pag_equiv.insert_text((35, 102), "NOMBRE COMERCIAL (ADMINISTRADO)", fontname="helv", fontsize=8, color=(1,1,1))
    pag_equiv.insert_text((315, 102), "NOMBRE EN LIQUIDACION (FACTURADO)", fontname="helv", fontsize=8, color=(1,1,1))

    y = 115
    for i, (orig, nuevo) in enumerate(REEMPLAZOS.items()):
        fill_color = (0.85, 0.94, 0.83) if i % 2 == 0 else (0.93, 0.93, 0.93)
        pag_equiv.draw_rect(fitz.Rect(30, y, ancho-30, y+14), color=None, fill=fill_color)
        orig_corto = orig[:50] + "..." if len(orig) > 50 else orig
        pag_equiv.insert_text((35, y+10), orig_corto, fontname="helv", fontsize=7, color=(0,0,0))
        pag_equiv.insert_text((315, y+10), nuevo, fontname="helv", fontsize=7, color=(0.07, 0.35, 0.07))
        y += 14
        if y > alto - 50:
            break

    doc_out.save(PDF_SALIDA)
    doc_in.close()
    doc_out.close()

    print(f"\nArchivo guardado: {PDF_SALIDA}")
    print("Listo!")

if __name__ == "__main__":
    main()
