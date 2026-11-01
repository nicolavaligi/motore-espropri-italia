#!/usr/bin/env python3
"""
Modulo per l'estrazione e normalizzazione di piani particellari grafici/descrittivi
da PDF tecnici di opere pubbliche (espropri e asservimenti ex D.P.R. 327/2001).
Output conforme allo schema JSON del Motore Espropri Italia.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import pdfplumber


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_float(val: Optional[str]) -> float:
    if not val:
        return 0.0
    val_clean = clean_text(val).replace("mq", "").replace("m²", "").strip()
    if "," in val_clean:
        val_clean = val_clean.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})+", val_clean):
        val_clean = val_clean.replace(".", "")
    match = re.search(r"[-+]?\d*\.\d+|[-+]?\d+", val_clean)
    return float(match.group()) if match else 0.0


def extract_cf(text: str) -> Optional[str]:
    cf_match = re.search(
        r"\b[A-Z]{6}[0-9]{2}[A-E-H-L-M-P-R-S-T][0-9]{2}[A-Z][0-9]{3}[A-Z]\b",
        text.upper()
    )
    if cf_match:
        return cf_match.group(0)
    piva_match = re.search(r"\b\d{11}\b", text)
    if piva_match:
        return piva_match.group(0)
    return None


def parse_raw_table_rows(table_rows: List[List[str]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    col_map = {
        "comune": -1, "foglio": -1, "mappale": -1, "sub": -1,
        "ditta": -1, "sup_totale": -1, "sup_esproprio": -1,
        "sup_asservimento": -1, "sup_occupazione": -1,
        "cf": -1, "quota": -1, "diritto": -1, "sezione": -1
    }
    header_detected = False

    for row in table_rows:
        cleaned_row = [clean_text(cell) for cell in row]
        if not any(cleaned_row):
            continue

        row_joined = " ".join(cleaned_row).lower()

        if not header_detected and ("foglio" in row_joined or "fg" in row_joined) and ("mapp" in row_joined or "part" in row_joined):
            for idx, cell in enumerate(cleaned_row):
                c_low = cell.lower()
                if "comune" in c_low:
                    col_map["comune"] = idx
                elif "foglio" in c_low or "fg" in c_low or c_low.startswith("f."):
                    col_map["foglio"] = idx
                elif "mapp" in c_low or "part" in c_low:
                    col_map["mappale"] = idx
                elif "sub" in c_low:
                    col_map["sub"] = idx
                elif any(k in c_low for k in ["codice fiscale", "c.f.", "p.iva", "partita iva"]):
                    col_map["cf"] = idx
                elif "quota" in c_low:
                    col_map["quota"] = idx
                elif "diritto" in c_low or "titolar" in c_low:
                    col_map["diritto"] = idx
                elif "sezione" in c_low:
                    col_map["sezione"] = idx
                elif any(k in c_low for k in ["ditta", "proprietari", "intestatar", "nominativ"]):
                    col_map["ditta"] = idx
                elif "occup" in c_low:
                    col_map["sup_occupazione"] = idx
                elif "asserv" in c_low or "servit" in c_low:
                    col_map["sup_asservimento"] = idx
                elif "esprop" in c_low or "esp" in c_low:
                    col_map["sup_esproprio"] = idx
                elif "tot" in c_low or "sup" in c_low:
                    if col_map["sup_totale"] == -1:
                        col_map["sup_totale"] = idx
            header_row = cleaned_row
            header_detected = True
            continue

        if not header_detected:
            continue

        def get_val(key: str) -> str:
            pos = col_map.get(key, -1)
            return cleaned_row[pos] if 0 <= pos < len(cleaned_row) else ""

        foglio = get_val("foglio")
        mappale = get_val("mappale")
        raw_ditta = get_val("ditta")

        if not foglio or not mappale:
            continue
        if "totale" in foglio.lower() or "foglio" in foglio.lower():
            continue

        cf = extract_cf(get_val("cf")) or extract_cf(raw_ditta)
        ditta_nome = raw_ditta
        if cf:
            ditta_nome = raw_ditta.replace(cf, "").strip(" -–,;/")

        def optional_surface(key):
            value = get_val(key)
            header = header_row[col_map[key]] if col_map[key] >= 0 else ''
            # Un numero senza unità dichiarata non diventa automaticamente m².
            unit_declared = bool(re.search(r"(?:\bmq\b|m²|m2|m\^2)", value + ' ' + header, re.I))
            number = re.sub(r"(?:\bmq\b|m²|m2|m\^2)", '', value, flags=re.I).strip()
            if not unit_declared or not re.fullmatch(r"\d+(?:[.,]\d+)*", number):
                return None
            return parse_float(number)

        record = {
            "foglio": foglio,
            "mappale": mappale.replace(" ", ""),
            "sub": get_val("sub") or None,
            "comune": get_val("comune") or None,
            "intestatario": ditta_nome or "Ditta non specificata",
            "codice_fiscale": cf,
            "quota": get_val("quota") or None,
            "diritto": get_val("diritto") or None,
            "sezione": get_val("sezione") or None,
            "raw": {"celle": row, "intestazione": raw_ditta},
            "superfici_mq": {
                "totale": optional_surface("sup_totale"),
                "esproprio": optional_surface("sup_esproprio"),
                "asservimento": optional_surface("sup_asservimento"),
                "occupazione_temporanea": optional_surface("sup_occupazione")
            }
        }
        record['qualita_superfici'] = {
            'unita_output': 'm²',
            'nota': 'Valori nulli se unità assente o testo ambiguo; verificare celle e intestazioni originali.',
            'intestazioni_originali': header_row,
        }
        records.append(record)

    return records


def extract_piano_particellare(pdf_path: str | Path) -> List[Dict[str, Any]]:
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File non trovato: {pdf_file}")

    all_records: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                records = parse_raw_table_rows(table)
                for r in records:
                    r["metadati"] = {"fonte_pagina": page_idx}
                all_records.extend(records)
    return all_records


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extract_particellare.py <percorso_file.pdf> [output.json]")
        sys.exit(1)

    pdf_in = Path(sys.argv[1])
    json_out = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf_in.with_suffix(".json")

    try:
        risultati = extract_piano_particellare(pdf_in)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(risultati, f, ensure_ascii=False, indent=2)

        print(f"Estratte con successo {len(risultati)} particelle da '{pdf_in.name}' -> salvate in '{json_out.name}'")
    except Exception as e:
        print(f"Errore durante l'elaborazione del PDF: {e}", file=sys.stderr)
        sys.exit(1)
