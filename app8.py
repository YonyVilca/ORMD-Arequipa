# app8.py
# -*- coding: utf-8 -*-
import re
import sys
import json
import csv
import unicodedata
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Meses + variantes comunes de OCR
MESES = {
    'ene': '01', 'enero': '01', 'ene.': '01', 'eng': '01', 'enr': '01',
    'feb': '02', 'febrero': '02', 'feb.': '02',
    'mar': '03', 'marzo': '03', 'mar.': '03',
    'abr': '04', 'abril': '04', 'abr.': '04',
    'may': '05', 'mayo': '05', 'may.': '05',
    'jun': '06', 'junio': '06', 'jun.': '06',
    'jul': '07', 'julio': '07', 'jul.': '07',
    'ago': '08', 'agosto': '08', 'ago.': '08',
    'sep': '09', 'sept': '09', 'septiembre': '09', 'sep.': '09',
    'set': '09', 'setiembre': '09', 'set.': '09',
    'oct': '10', 'octubre': '10', 'oct.': '10',
    'nov': '11', 'noviembre': '11', 'nov.': '11',
    'dic': '12', 'diciembre': '12', 'dic.': '12'
}

CSV_ORDER = [
    'Nombres', 'Apellidos', 'DNI',
    'Fecha de Nacimiento', 'Libro', 'Folio', 'Clase',
    'Unidad de alta', 'Fecha de alta',
    'Unidad de Baja', 'Fecha de baja', 'Grado'
]

INVALID_LONE_VALUES = {"", "-", "=", ":"}

TITLE_STOPWORDS = (
    r'Unidad\s+de\s+Baja|SERVICIO\s+DE\s+LA\s+RESERVA|SERVICIO\s+EN\s+EL\s+ACTIVO|'
    r'Fecha\s+de\s+Baja|Fecha\s+de\s+Alta|CALIFICACI[ÓO]N|Nº?\s+de\s+sorteo|'
    r'Modalidad\s+SMV|INSTITUTO|FILIACI[ÓO]N\s+DEL\s+INSCRITO|Apellidos|Apeltidos|Apelidos|Nombres'
)

# === Helpers ===
def norm_spaces(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = (s.replace('—', '-').replace('–', '-').replace('¬', ' ')
           .replace('“', '"').replace('”', '"')
           .replace('‘', "'").replace('’', "'").replace('′', "'"))
    s = s.replace('¡', '').replace('«', '').replace('»', '')
    s = s.replace('Nº', 'N°').replace('No.', 'N°').replace('No ', 'N° ')
    # elimina barras verticales sueltas pegadas a palabras
    s = re.sub(r'\s*\|\s*', ' | ', s)
    # espacios
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s

def post_clean_value(v: str) -> str:
    v = (v or "").strip(" .:\t\r\n\"'")
    return "" if v in INVALID_LONE_VALUES else v

def normalize_name(v: str) -> str:
    if not v:
        return ""
    # corta en otra barra vertical si la hay
    v = v.split('|')[0]
    # quita comillas y símbolos
    v = v.replace('"', ' ').replace("'", ' ').replace('`', ' ')
    v = re.sub(r'[<>•·*_=:+\-–—]+', ' ', v)
    # deja solo letras españolas y espacios
    v = re.sub(r'[^A-ZÁÉÍÓÚÑ ]+', ' ', v.upper())
    v = re.sub(r'\s{2,}', ' ', v).strip()
    return v

def norm_fecha_tokens(d: str, m: str, a: str) -> str:
    m_key = (m or "").strip().lower()
    m_key = (m_key
             .replace('é', 'e').replace('í', 'i').replace('ó', 'o')
             .replace('á', 'a').replace('ú', 'u').rstrip('.'))
    mnum = MESES.get(m_key)
    if not mnum:
        return f"{d}-{m}-{a}"
    return f"{int(a):04d}-{int(mnum):02d}-{int(d):02d}"

def parse_fecha_line(t: str, label_regex: str) -> str:
    # 31 - Ene - 2025 | 31/Ene/2025 | 31 Ene 2025
    pat = rf"(?i){label_regex}\s*:\s*(\d{{1,2}})\s*[-/ ]\s*([A-Za-zÁÉÍÓÚñ]{{3,}}\.?)\s*[-/ ]\s*(\d{{4}})"
    m = re.search(pat, t, flags=re.S)
    if m:
        return norm_fecha_tokens(*m.groups())
    pat2 = rf"(?i){label_regex}\s*:\s*(\d{{1,2}})[-/](\d{{1,2}})[-/](\d{{4}})"
    m2 = re.search(pat2, t, flags=re.S)
    if m2:
        d, mm, a = m2.groups()
        return f"{int(a):04d}-{int(mm):02d}-{int(d):02d}"
    return ""

def safe_strip(x: str) -> str:
    return (x or "").strip(" .:\t\r\n")

def fix_dni(raw: str) -> str:
    if not raw:
        return ""
    s = raw.upper()
    s = (s.replace('O', '0')
           .replace('I', '1')
           .replace('L', '1')
           .replace('B', '8')
           .replace('S', '5'))
    s = re.sub(r'\D', '', s)
    return s if 8 <= len(s) <= 11 else ""

def find_dni_ultra(t: str) -> str:
    # evita confundir el grupo sanguíneo
    texto_sin_grupo = []
    for line in t.splitlines():
        if re.search(r'(?i)\b(AB|A|B|O)\s*[+-]\b', line):
            continue
        texto_sin_grupo.append(line)
    ts = "\n".join(texto_sin_grupo)

    m = re.search(r'(?im)^\s*D\s*[^A-Za-z0-9]*\s*N\s*[^A-Za-z0-9]*\s*I\s*[:=]?\s*([^\n\r]+)$', ts)
    if m:
        cand = fix_dni(m.group(1))
        if cand:
            return cand

    header = "\n".join(ts.splitlines()[:8]).upper()
    header = header.replace('O', '0').replace('I', '1').replace('L', '1').replace('B', '8').replace('S', '5')
    num = re.search(r'\b(\d{8,11})\b', header)
    if num:
        return num.group(1)
    return ""

def extract_after_label_block(t: str, label_regex: str) -> str:
    m = re.search(label_regex, t, flags=re.S | re.I)
    if not m:
        return ""
    seg = t[m.end():]
    seg = re.sub(r'^[\s:.\-+*=>]+', '', seg)
    corte = re.search(rf'(?is)\b({TITLE_STOPWORDS}|$)', seg)
    val = seg[:corte.start()] if (corte and corte.start() > 0) else seg
    return post_clean_value(val)

def extract_same_line(t: str, label_regex: str) -> str:
    pat = rf'(?im)^\s*(?:{label_regex})\s*[:.\-+*]?\s*(.*?)\s*$'
    m = re.search(pat, t)
    return post_clean_value(m.group(1) if m else "")

# === Parser principal ===
def parse_text(texto: str) -> Dict[str, Any]:
    t = norm_spaces(texto)

    # Correcciones OCR típicas
    t = re.sub(r'(?i)\bCLASE\s*:\s*1(\d{4})\b', r'CLASE: \1', t)  # 12023 -> 2023
    t = re.sub(r'(?i)\bNombres?\s*:\s*-\s*', 'Nombres: ', t)
    t = re.sub(r'(?i)\bApe(?:llidos|ltidos|lidos)\s*:\s*-\s*', 'Apellidos: ', t)

    out: Dict[str, Any] = {k: "" for k in CSV_ORDER}

    # NOMBRES: permite basura antes/después y corta antes de otro '|'
    matches_nombres = list(re.finditer(r'(?im)^[^\n\r]*\bNombres\b\s*:?\s*([^\n\r]+)$', t))
    if matches_nombres:
        out['Nombres'] = normalize_name(matches_nombres[0].group(1))
    else:
        out['Nombres'] = ""

    # APELLIDOS: acepta Apellidos/Apeltidos/Apelidos; idem manejo de '|'
    matches_apellidos = list(re.finditer(r'(?im)^[^\n\r]*\bApe(?:llidos|ltidos|lidos)\b\s*:?\s*([^\n\r]+)$', t))
    if matches_apellidos:
        out['Apellidos'] = normalize_name(matches_apellidos[0].group(1))
    else:
        out['Apellidos'] = ""

    # DNI
    out['DNI'] = find_dni_ultra(t)

    # Fecha de Nacimiento — Dia/Día/Mes/Año con ":" opcional y variantes Año/Ano/Afio
    md = re.search(
        r'(?is)D[ií]a\s*:?\s*(\d{1,2}).*?Mes\s*:?\s*([A-Za-zÁÉÍÓÚñ\.]+).*?A(?:n|ñ|fi)[o0]\s*:?\s*(\d{4})',
        t
    )
    out['Fecha de Nacimiento'] = norm_fecha_tokens(*md.groups()) if md else ""

    # Libro / Folio
    ml = re.search(r'(?i)\bLibro\s*:\s*(\d{1,3})\b', t)
    mf = re.search(r'(?i)\bFolio\s*:\s*(\d{1,4})\b', t)
    if not (ml and mf):
        mhdr = re.search(r'^\s*:\s*(\d{1,3})\s+(\d{1,4})\b', t, flags=re.M)
        if mhdr:
            if not ml: ml = type('M', (), {'group': lambda _self, i=1: mhdr.group(i)})
            if not mf: mf = type('M', (), {'group': lambda _self, i=2: mhdr.group(i)})
    out['Libro'] = ml.group(1) if ml else ""
    out['Folio'] = mf.group(1) if mf else ""

    # Clase
    m = re.search(r'(?i)\bCLASE\s*:\s*(\d{4})\b', t)
    out['Clase'] = m.group(1) if m else ""

    # Unidad de alta (tolerante a OCR) + limpieza de símbolos
    etiqueta_unidad_alta = r'Uni\w*\s+de\s+al[ti][aáf]'
    unidad_alta = extract_after_label_block(t, etiqueta_unidad_alta)
    if unidad_alta:
        unidad_alta = unidad_alta.lstrip('> ').replace('*', ' ').replace('?', ' ')
        unidad_alta = re.sub(r'\s{2,}', ' ', unidad_alta).strip()
        unidad_alta = re.sub(r'\bN\s*°\s*', 'N° ', unidad_alta)
    out['Unidad de alta'] = unidad_alta

    # Fechas alta/baja
    out['Fecha de alta'] = parse_fecha_line(t, r"Fecha\s+de\s+Alta")
    out['Fecha de baja'] = parse_fecha_line(t, r"Fecha\s+de\s+Baja")

    # Unidad de Baja (misma línea)
    etiqueta_unidad_baja_line = r'Unidad\s+de\s+Baja'
    unidad_baja = extract_same_line(t, etiqueta_unidad_baja_line)
    if (not unidad_baja or
        re.search(r'(?i)SERVICIO\s+DE\s+LA\s+RESERVA|CALIFICACI[ÓO]N|Modalidad\s+SMV', unidad_baja) or
        re.fullmatch(r'^[^A-Za-zÁÉÍÓÚÑ0-9]+$', unidad_baja or '')):
        unidad_baja = ""
    out['Unidad de Baja'] = unidad_baja

    # Grado (antes de "Arma/Especialidad")
    m = re.search(r'(?is)\bGrado(?:\s*o\s*Clase)?\s*:\s*([^:\n]+?)(?=\s*Arma/Especialidad|$)', t)
    out['Grado'] = post_clean_value(m.group(1) if m else "")

    # Post-normalizaciones nombres/apellidos
    out['Nombres'] = re.sub(r'\s{2,}', ' ', out['Nombres']).strip()
    out['Apellidos'] = re.sub(r'\s{2,}', ' ', out['Apellidos']).strip()

    # Vacía símbolos sueltos
    if re.fullmatch(r'^[^A-Za-zÁÉÍÓÚÑ0-9]+$', out['Unidad de alta'] or ''):
        out['Unidad de alta'] = ""
    if out['Unidad de Baja'] in INVALID_LONE_VALUES:
        out['Unidad de Baja'] = ""
    if out['Grado'] in INVALID_LONE_VALUES or out['Grado'].lower().startswith('arma/especialidad'):
        out['Grado'] = ""

    return out

# === IO / CLI ===
def write_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_csv(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_ORDER)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in CSV_ORDER})

def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Extractor de campos para Hoja de Registro (OCR) robusto a errores comunes."
    )
    parser.add_argument("input", nargs="?", help="Archivo de texto con OCR (si se omite, lee de STDIN).")
    parser.add_argument("--out-json", help="Ruta de salida JSON (opcional).")
    parser.add_argument("--out-csv", help="Ruta de salida CSV (opcional).")
    parser.add_argument("--encoding", default="utf-8", help="Encoding del archivo de entrada (por defecto utf-8).")
    args = parser.parse_args()

    if args.input:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"[ERROR] No existe el archivo: {in_path}", file=sys.stderr)
            sys.exit(1)
        texto = in_path.read_text(encoding=args.encoding, errors="ignore")
    else:
        texto = sys.stdin.read()

    data = parse_text(texto)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.out_json:
        write_json(data, Path(args.out_json))
    if args.out_csv:
        write_csv([data], Path(args.out_csv))

if __name__ == "__main__":
    cli()
