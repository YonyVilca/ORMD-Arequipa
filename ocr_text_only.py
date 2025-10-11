# ocr_text_only.py
# Requisitos:
#   pip install opencv-python-headless pytesseract pdf2image pillow deskew
# Además: Tener Tesseract y Poppler instalados (y en PATH).
# En Windows: ajusta pytesseract.pytesseract.tesseract_cmd si hace falta.

import cv2, pytesseract, re, time, logging
import numpy as np
from pdf2image import convert_from_path
from PIL import Image
from deskew import determine_skew
from pathlib import Path

# ================== CONFIG ==================
PDF_PATH = '18.pdf'
OUT_TEXT = 'extracted_text.txt'

# Cambia a True para ejecución más rápida (menos filtros, 1 binarizado, 300 DPI)
FAST_MODE = True

# Si FAST_MODE=False => QUALITY_MODE: más calidad (más filtros, 2 binarizados, 400 DPI)
# Aun en QUALITY_MODE no generamos JSON ni dataframes: solo texto.

# (Opcional) En Windows, fija ruta a tesseract.exe:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# ============================================

def to_cv2(pil_img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)

def rotate_by_angle(img, angle):
    if abs(angle) < 0.8:  # Deskew solo si es notorio (acelera)
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def remove_lines_soft(bin_img):
    # bin_img: 0=negro, 255=blanco. Si no es así, invierte antes.
    inv = 255 - bin_img
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (24,1))  # suave/rápido
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1,24))
    horiz = cv2.morphologyEx(inv, cv2.MORPH_OPEN, hk, iterations=1)
    vert  = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vk, iterations=1)
    lines = cv2.bitwise_or(horiz, vert)
    cleaned = cv2.bitwise_and(inv, cv2.bitwise_not(lines))
    return 255 - cleaned

def preprocess_fast(img_bgr):
    # 300 DPI esperado; sin upscaling para ganar velocidad
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    angle = determine_skew(gray)
    img_bgr = rotate_by_angle(img_bgr, angle)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Un binarizado Otsu (rápido)
    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    return bin_img

def preprocess_quality(img_bgr, save_debug=False, page_number=1):
    # 400 DPI esperado; mejora contraste y prueba dos binarizados
    # Upscale x2 suave (si viniera a menor resolución)
    img_bgr = cv2.resize(img_bgr, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_LINEAR)

    gray0 = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    angle = determine_skew(gray0)
    img_bgr = rotate_by_angle(img_bgr, angle)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # Binarizados: Otsu y Adaptativo, escogemos por cantidad de texto (heurística barata)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    adp = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5)

    # Quita-líneas suave (sólo si aumenta longitud de OCR; probamos barato con image_to_string)
    cfg = '-l spa+eng --oem 1 --psm 6'
    t_otsu = pytesseract.image_to_string(otsu, config=cfg)
    t_adp  = pytesseract.image_to_string(adp,  config=cfg)
    cand = [('otsu', otsu, len(t_otsu)), ('adp', adp, len(t_adp))]

    # probar sin líneas para el mejor de los dos
    best_name, best_img, best_len = max(cand, key=lambda x: x[2])
    no_lines = remove_lines_soft(best_img)
    t_nl = pytesseract.image_to_string(no_lines, config=cfg)
    if len(t_nl) > best_len:
        best_img = no_lines
        best_name += '_nolines'

    if save_debug:
        cv2.imwrite(f'debug_page_{page_number}_{best_name}.png', best_img)

    return best_img

def fixups_for_display(t: str) -> str:
    # Arreglos ligeros de errores comunes
    s = t
    # CLASE: 12023 -> 2023 (si aparece un "1" pegado antes)
    s = re.sub(r'(CLASE:\s*)1?([12]\d{3})\b', r'\1\2', s)
    # Calzado 139 -> Calzado 39 (si mete un 1 fantasma)
    s = re.sub(r'\bCalzado\s+1?([2-5]?\d)\b', r'Calzado \1', s)
    # Setiembre -> Septiembre
    s = re.sub(r'\bSetiembre\b', 'Septiembre', flags=re.I, string=s)
    # Correos: eliminar espacios alrededor de @ y antes del TLD
    s = re.sub(r'\s*@\s*', '@', s)
    s = re.sub(r'(@[A-Za-z0-9.\-]+)\s+(\.[A-Za-z]{2,}\b)', r'\1\2', s)
    # Espacios dobles
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()

def main():
    if not Path(PDF_PATH).exists():
        raise FileNotFoundError(f'No se encontró {PDF_PATH}')

    dpi = 300 if FAST_MODE else 400
    logging.info(f'Leyendo PDF (dpi={dpi})...')
    t0 = time.perf_counter()

    pages = convert_from_path(PDF_PATH, dpi=dpi)
    logging.info(f'Páginas: {len(pages)}')

    all_text = []
    cfg = '-l spa+eng --oem 1 --psm 6'  # configuración estable para formularios con bloques

    for i, page in enumerate(pages, start=1):
        cv = to_cv2(page)
        if FAST_MODE:
            bin_img = preprocess_fast(cv)
        else:
            bin_img = preprocess_quality(cv, save_debug=True, page_number=i)

        # OCR de página (una sola pasada)
        txt = pytesseract.image_to_string(bin_img, config=cfg)
        all_text.append(f"--- Página {i} ---\n{txt.strip()}\n")

        # (Opcional) Guarda binario para inspección
        cv2.imwrite(f'processed_page_{i}.png', bin_img)

    # Escribe solo TEXTO
    with open(OUT_TEXT, 'w', encoding='utf-8') as f:
        f.write("\n".join(all_text))

    # Vista de consola con arreglos ligeros (no se guarda a archivo)
    print("\n--- Vista con correcciones suaves (solo consola) ---\n")
    print(fixups_for_display("\n".join(all_text)))

    elapsed = time.perf_counter() - t0
    logging.info(f"Listo. Texto → {OUT_TEXT}")
    logging.info(f"Tiempo total: {elapsed:.2f} s ({'FAST_MODE' if FAST_MODE else 'QUALITY_MODE'})")

if __name__ == '__main__':
    try:
        main()
    except pytesseract.TesseractNotFoundError:
        logging.error("Tesseract no está instalado o no está en PATH.")
    except Exception as e:
        if "Unable to find poppler" in str(e):
            logging.error("Poppler no encontrado: instálalo y/o usa poppler_path en convert_from_path().")
        else:
            logging.exception(e)
