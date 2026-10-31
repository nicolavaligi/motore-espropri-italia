#!/usr/bin/env python3
"""
Modulo Notifiche Email Settimanali — Motore Espropri Italia
Autore: Nicola Valigi (Houdinick)
Invia un riepilogo a n.valig@gmail.com con:
- Testo riassuntivo delle procedure in Fase 4 (Art. 16 DPR 327/2001) e target 🟡
- Allegato CSV generato dinamicamente con tutte le ditte/particelle censite
- Allegati PDF dei piani particellari scaricati negli ultimi 7 giorni (con limite di dimensione)
"""

from __future__ import annotations

import csv
import io
import json
import os
import smtplib
from datetime import date, datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Tuple

DESTINATARIO_DEFAULT = "n.valig@gmail.com"
BASE_DIR = Path(__file__).parent
DATA_OPERE = BASE_DIR / "data" / "opere.json" if (BASE_DIR / "data" / "opere.json").exists() else BASE_DIR / "opere.json"
PDF_ARCHIVIO_DIR = BASE_DIR / "data" / "pdf_archivio"

# Soglia massima per singolo allegato o batch (20 MB per rispetto limiti provider SMTP)
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def genera_report_testo() -> Tuple[str, int, list]:
    """Legge opere.json e restituisce il report testuale, il conteggio target e le opere filtrate."""
    if not DATA_OPERE.exists():
        return "Nessun archivio opere.json trovato.", 0, []

    try:
        with open(DATA_OPERE, "r", encoding="utf-8") as f:
            opere = json.load(f)
    except Exception as e:
        return f"Errore lettura opere.json: {e}", 0, []

    # Seleziona le opere avanzate / Fase 4
    target = [
        o for o in opere 
        if o.get("stato_opera") in ("AVANZATA_SENZA_ELENCO", "ELENCO_PUBBLICATO")
        or o.get("maturita_step") == 4
        or o.get("fase_procedurale") == "DEPOSITO_PIANO_PARTICELLARE"
        or o.get("has_pda") is True
    ]

    linee = [
        f"🏛 REPORT MOTORE ESPROPRI ITALIA — LUNEDÌ {date.today().strftime('%d/%m/%Y')}",
        "=" * 68,
        f"Totale procedure target individuate: {len(target)}",
        ""
    ]

    for i, op in enumerate(target[:20], 1):
        titolo = op.get("titolo") or op.get("nome", "Senza titolo")
        cup = op.get("cup") or "N.D."
        ente = op.get("ente") or "N.D."
        scadenza = op.get("scadenza_osservazioni") or op.get("scadenza") or "30 gg da pubblicazione"
        stato = op.get("stato_opera", "FASE 4")
        n_ditte = len(op.get("ditte", []))

        linee.append(f"{i}. [{stato}] {titolo}")
        linee.append(f"   Ente: {ente} | CUP: {cup}")
        linee.append(f"   Scadenza termini: {scadenza} | Ditte censite: {n_ditte}")
        if op.get("azione") and isinstance(op["azione"], dict) and op["azione"].get("deposito_presso"):
            linee.append(f"   Deposito: {op['azione']['deposito_presso']}")
        elif op.get("deposito_presso"):
            linee.append(f"   Deposito: {op['deposito_presso']}")
        linee.append("-" * 68)

    if not target:
        linee.append("Nessuna nuova opera avanzata o piano particellare rilevato negli ultimi 7 giorni.")

    return "\n".join(linee), len(target), target


def genera_csv_particelle(opere: list) -> Tuple[str, bytes]:
    """
    Estrae tutte le ditte e particelle catastali accertate dalle opere target
    e produce un payload CSV codificato in UTF-8 con BOM per compatibilità Excel.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Intestazione Colonne Standard Catasto DPR 327/2001
    writer.writerow([
        "Codice Opera / Slug",
        "CUP",
        "Ente Espropriante",
        "Intestatario / Ditta",
        "Codice Fiscale / P.IVA",
        "Comune Catastale",
        "Foglio",
        "Mappali",
        "Sub",
        "Superficie Esproprio (mq)",
        "Indennità Provvisoria (€)",
        "Stima Delta Attivo"
    ])

    righe_totali = 0
    for op in opere:
        slug = op.get("slug") or op.get("id") or "ND"
        cup = op.get("cup") or ""
        ente = op.get("ente") or ""

        for d in op.get("ditte", []):
            writer.writerow([
                slug,
                cup,
                ente,
                d.get("intestatario") or d.get("nome") or "",
                d.get("cf") or d.get("codice_fiscale") or "",
                d.get("comune") or op.get("comune") or "",
                d.get("foglio") or "",
                d.get("mappali") or d.get("mappale") or "",
                d.get("sub") or "",
                d.get("sup_mq") or d.get("superficie") or "",
                d.get("indennita") or d.get("indennita_eur") or "",
                "SÌ" if d.get("delta") else "NO"
            ])
            righe_totali += 1

    nome_file = f"estrazione_particelle_{date.today().strftime('%Y%m%d')}.csv"
    # Aggiunge UTF-8 BOM per apertura immediata in Excel senza problemi di caratteri accentati
    payload = ("\ufeff" + output.getvalue()).encode("utf-8")
    return nome_file, payload


def raccogli_pdf_recenti(giorni: int = 7) -> List[Path]:
    """Cerca nella cartella archivio i PDF modificati o scaricati negli ultimi N giorni."""
    if not PDF_ARCHIVIO_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=giorni)
    pdf_trovati = []

    for file_path in PDF_ARCHIVIO_DIR.glob("*.pdf"):
        if file_path.is_file():
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime >= cutoff:
                pdf_trovati.append(file_path)

    # Ordina dai più recenti
    pdf_trovati.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pdf_trovati


def allega_file(msg: MIMEMultipart, nome_file: str, payload_bytes: bytes, maintype: str = "application", subtype: str = "octet-stream"):
    """Allega un flusso di byte al messaggio MIME."""
    part = MIMEBase(maintype, subtype)
    part.set_payload(payload_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{nome_file}"')
    msg.attach(part)


def invia_email(oggetto: str, corpo: str, opere_target: list, destinatario: str = DESTINATARIO_DEFAULT) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", destinatario)
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_pass:
        print("[EMAIL NOTIFIER] AVVISO: Variabile d'ambiente SMTP_PASS non rilevata.")
        print("--- ANTEPRIMA DEL REPORT CHE SAREBBE STATO INVIATO ---")
        print(corpo)
        return False

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = destinatario
    msg["Subject"] = oggetto

    # Corpo del messaggio
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    dimensione_totale = len(corpo.encode("utf-8"))

    # 1. Allega CSV Particelle Estratte
    csv_nome, csv_bytes = genera_csv_particelle(opere_target)
    allega_file(msg, csv_nome, csv_bytes, "text", "csv")
    dimensione_totale += len(csv_bytes)
    print(f"[EMAIL NOTIFIER] Allegato generato: {csv_nome} ({len(csv_bytes) / 1024:.1f} KB)")

    # 2. Allega PDF recenti (fino al limite consentito)
    pdf_recenti = raccogli_pdf_recenti(giorni=7)
    pdf_allegati = 0

    for pdf_path in pdf_recenti:
        pdf_size = pdf_path.stat().st_size
        if dimensione_totale + pdf_size > MAX_ATTACHMENT_BYTES:
            print(f"[EMAIL NOTIFIER] Limite dimensione raggiunto. Salto: {pdf_path.name}")
            continue

        try:
            with open(pdf_path, "rb") as f:
                allega_file(msg, pdf_path.name, f.read(), "application", "pdf")
            dimensione_totale += pdf_size
            pdf_allegati += 1
            print(f"[EMAIL NOTIFIER] Allegato PDF aggiunto: {pdf_path.name} ({pdf_size / 1024:.1f} KB)")
        except Exception as e:
            print(f"[EMAIL NOTIFIER] Errore lettura PDF {pdf_path.name}: {e}")

    # Invio SMTP
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[EMAIL NOTIFIER] Report settimanale inviato con successo a {destinatario} ({pdf_allegati} PDF + 1 CSV allegati).")
        return True
    except Exception as e:
        print(f"[EMAIL NOTIFIER] Errore durante l'invio SMTP: {e}")
        return False


if __name__ == "__main__":
    report, n_opere, target = genera_report_testo()
    titolo = f"🏛 [Motore Espropri Italia] Report Settimanale Espropri: {n_opere} target rilevati ({date.today().strftime('%d/%m/%Y')})"
    invia_email(titolo, report, target)
