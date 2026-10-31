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
    """Rimuove a capo spuri e spazi multipli tipici dei layout PDF."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_float(val: Optional[str]) -> float:
    """Converte stringhe numeriche formattate all'italiana (es. '1.450,50' o '1450') in float."""
    if not val:
        return 0.0
    val_clean = clean_text(val).replace("mq", "").replace("m²", "").strip()
    # Rimuove punti delle migliaia e converte virgola decimale
    val_clean = val_clean.replace(".", "").replace(",", ".")
    match = re.search(r"[-+]?\d*\.\d+|\d+", val_clean)
    return float(match.group()) if match else 0.0


def extract_cf(text: str) -> Optional[str]:
    """Cerca un Codice Fiscale standard (16 caratteri) o una Partita IVA (11 cifre)."""
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


def extract_piano_particellare(pdf_path: str | Path) -> List[Dict[str, Any]]:
    """
    Estrae le particelle catastali dal PDF utilizzando pdfplumber.
    Implementa tolleranze esplicite per tabelle senza bordi netti e
    gestisce righe multilinea per gli intestatari.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File non trovato: {pdf_file}")

    records: List[Dict[str, Any]] = []

    # Configurazione di estrazione mirata per tabelle tecniche di enti pubblici
    table_settings = {
        "vertical_strategy": "text",       # oppure "lines" se la tabella ha griglie complete
        "horizontal_strategy": "text",
        "snap_tolerance": 4,
        "join_tolerance": 3,
        "edge_min_length": 3,
        "min_words_vertical": 2
    }

    col_map = {
        "comune": -1,
        "foglio": -1,
        "mappale": -1,
        "sub": -1,
        "ditta": -1,
        "sup_totale": -1,
        "sup_esproprio": -1,
        "sup_asservimento": -1,
        "sup_occupazione": -1
    }

    with pdfplumber.open(pdf_file) as pdf:
        header_detected = False

        for page_idx, page in enumerate(pdf.pages, start=1):
            # Prova prima con impostazioni standard per tabelle con righe
            tables = page.extract_tables()
            
            # Fallback su impostazioni esplicite se non rileva griglie
            if not tables:
                tables = page.extract_tables(table_settings)

            for table in tables:
                if not table:
                    continue

                for row in table:
                    # Rimuove valori None e pulisce ogni cella
                    cleaned_row = [clean_text(cell) for cell in row]
                    
                    # Salta righe vuote
                    if not any(cleaned_row):
                        continue

                    row_joined = " ".join(cleaned_row).lower()

                    # Riconoscimento dinamico dell'intestazione colonne
                    if not header_detected and ("foglio" in row_joined or "fg" in row_joined) and ("mapp" in row_joined or "part" in row_joined):
                        for idx, cell in enumerate(cleaned_row):
                            c_low = cell.lower()
                            if "comune" in c_low:
                                col_map["comune"] = idx
                            elif "foglio" in c_low or c_low in ["fg", "f."]:
                                col_map["foglio"] = idx
                            elif "mapp" in c_low or "part" in c_low:
                                col_map["mappale"] = idx
                            elif "sub" in c_low:
                                col_map["sub"] = idx
                            elif any(k in c_low for k in ["ditta", "proprietari", "intestatar", "nominativ"]):
                                col_map["ditta"] = idx
                            elif "occup" in c_low or "to" in c_low:
                                col_map["sup_occupazione"] = idx
                            elif "asserv" in c_low or "servit" in c_low:
                                col_map["sup_asservimento"] = idx
                            elif "esprop" in c_low or "esp" in c_low:
                                col_map["sup_esproprio"] = idx
                            elif "tot" in c_low or "sup" in c_low:
                                if col_map["sup_totale"] == -1:
                                    col_map["sup_totale"] = idx

                        header_detected = True
                        continue

                    # Se non è ancora stata trovata l'intestazione, salta la riga
                    if not header_detected:
                        continue

                    # Estrazione dei valori posizionali in base alla mappa colonne
                    def get_val(key: str) -> str:
                        pos = col_map.get(key, -1)
                        return cleaned_row[pos] if 0 <= pos < len(cleaned_row) else ""

                    foglio = get_val("foglio")
                    mappale = get_val("mappale")
                    raw_ditta = get_val("ditta")

                    # Validazione minima: deve esserci un identificativo catastale valido
                    if not foglio or not mappale:
                        # Fallback euristico tramite regex se le colonne sono slittate
                        match_fg = re.search(r"\b(?:fg\.?|foglio)?\s*(\d+)\b", row_joined)
                        match_map = re.search(r"\b(?:mapp\.?|part\.?)\s*(\d+[a-z]?)\b", row_joined)
                        if match_fg and match_map:
                            foglio = match_fg.group(1)
                            mappale = match_map.group(1)
                        else:
                            continue

                    # Salta righe di totale o ripetizioni di header
                    if "totale" in foglio.lower() or "foglio" in foglio.lower():
                        continue

                    # Pulizia mappale (es. "124/a" -> "124")
                    mappale_clean = mappale.replace(" ", "")

                    # Estrazione ditta e CF/P.IVA
                    cf = extract_cf(raw_ditta)
                    ditta_nome = raw_ditta
                    if cf:
                        ditta_nome = raw_ditta.replace(cf, "").strip(" -–,;/")

                    sup_esp = parse_float(get_val("sup_esproprio"))
                    sup_ass = parse_float(get_val("sup_asservimento"))
                    sup_occ = parse_float(get_val("sup_occupazione"))
                    sup_tot = parse_float(get_val("sup_totale"))

                    record = {
                        "foglio": foglio,
                        "mappale": mappale_clean,
                        "sub": get_val("sub") or None,
                        "comune": get_val("comune") or None,
                        "intestatario": ditta_nome or "Ditta non specificata",
                        "codice_fiscale": cf,
                        "superfici_mq": {
                            "totale": sup_tot,
                            "esproprio": sup_esp,
                            "asservimento": sup_ass,
                            "occupazione_temporanea": sup_occ
                        },
                        "metadati": {
                            "fonte_pagina": page_idx
                        }
                    }
                    records.append(record)

    return records


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
