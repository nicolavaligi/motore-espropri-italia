#!/usr/bin/env python3
"""
Modulo Notifiche Email Settimanali — Motore Espropri Italia
Autore: Nicola Valigi (Houdinick)

Invia un riepilogo a n.valig@gmail.com con:
1. Riepilogo testuale delle procedure target (Fase 4 / Art. 16 DPR 327/2001).
2. Esportazione CSV formattata (ditte, mappali, indennità stimate).
3. Archivio compresso .ZIP con tutti i PDF particellari scaricati negli ultimi 7 giorni.
"""

from __future__ import annotations

import csv
import io
import json
import os
import smtplib
import time
import zipfile
from production_store import DEFAULT_ROOT
from datetime import date, datetime
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

DESTINATARIO = "n.valig@gmail.com"
BASE_DIR = Path(__file__).resolve().parent
DATA_OPERE = DEFAULT_ROOT / "opere.json"
PDF_DIR = DEFAULT_ROOT / "documenti"

# Soglia massima complessiva allegati per policy SMTP (20 MB)
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def genera_report_testo() -> tuple[str, list[dict], int]:
    """Genera il corpo testuale del messaggio e isola le opere target."""
    if not DATA_OPERE.exists():
        return "Nessun archivio opere.json trovato.", [], 0

    try:
        with open(DATA_OPERE, "r", encoding="utf-8") as f:
            opere = json.load(f)
    except Exception as e:
        return f"Errore lettura opere.json: {e}", [], 0

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

        linee.append(f"{i}. [{stato}] {titolo}")
        linee.append(f"   Ente: {ente} | CUP: {cup}")
        linee.append(f"   Scadenza termini: {scadenza}")
        if op.get("ditte"):
            linee.append(f"   Ditte censite nel piano: {len(op['ditte'])}")
        linee.append("-" * 68)

    if not target:
        linee.append("Nessuna nuova opera avanzata o piano particellare rilevato questa settimana.")

    return "\n".join(linee), target, len(target)


def genera_csv_particelle(opere_target: list[dict]) -> tuple[str, bytes]:
    """Genera un CSV in-memory con intestatari, particelle e valori economici."""
    buffer = io.StringIO()
    # Scrive BOM UTF-8 per compatibilità nativa con Excel su Windows/macOS
    buffer.write("\ufeff")

    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "Opera_Slug",
        "CUP",
        "Ente_Espropriante",
        "Comune",
        "Intestatario_Ditta",
        "Foglio",
        "Mappali",
        "Superficie_mq",
        "Indennita_Stimata_EUR",
        "Delta_Potenziale",
        "Note"
    ])

    righe_scritte = 0
    for op in opere_target:
        slug = op.get("slug", "")
        cup = op.get("cup", "")
        ente = op.get("ente", "")
        ditte = op.get("ditte", [])

        for d in ditte:
            writer.writerow([
                slug,
                cup,
                ente,
                d.get("comune", op.get("comune", "")),
                d.get("intestatario", ""),
                d.get("foglio", ""),
                d.get("mappali", ""),
                str(d.get("sup_mq", "")).replace(".", ","),
                str(d.get("indennita", "")).replace(".", ","),
                "Sì" if d.get("delta") else "No",
                d.get("note", "")
            ])
            righe_scritte += 1

    filename = f"estrazione_particelle_{date.today().strftime('%Y%m%d')}.csv"
    return filename, buffer.getvalue().encode("utf-8")


def crea_zip_pdf_settimana(giorni: int = 7) -> tuple[str, bytes, int]:
    """
    Raccoglie tutti i PDF scaricati negli ultimi N giorni in data/pdf_archivio
    e li comprime in un archivio ZIP in-memory.
    """
    if not PDF_DIR.exists():
        return "", b"", 0

    adesso = time.time()
    limite_temporale = adesso - (giorni * 86400)
    pdf_files = []

    for file_path in PDF_DIR.glob("**/*.pdf"):
        if file_path.is_file():
            # Controlla data di modifica o creazione
            mtime = file_path.stat().st_mtime
            if mtime >= limite_temporale:
                pdf_files.append(file_path)

    if not pdf_files:
        return "", b"", 0

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for p in pdf_files:
            # Archivia solo il nome del file senza la struttura assoluta dei percorsi
            zip_file.write(p, arcname=p.name)

    zip_data = zip_buffer.getvalue()
    zip_filename = f"piani_particellari_settimana_{date.today().strftime('%Y%m%d')}.zip"
    return zip_filename, zip_data, len(pdf_files)


def invia_email(oggetto: str, corpo: str, allegati: list[tuple[str, bytes]], destinatario: str = DESTINATARIO) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", DESTINATARIO)
    smtp_pass = os.getenv("SMTP_PASS")

    # Verifica dimensioni totali allegati
    totale_peso = sum(len(d) for _, d in allegati)
    if totale_peso > MAX_ATTACHMENT_BYTES:
        mb_tot = totale_peso / (1024 * 1024)
        print(f"[EMAIL NOTIFIER] AVVISO: Allegati troppo pesanti ({mb_tot:.2f} MB > 20 MB). Archivio PDF escluso per sicurezza.")
        allegati = [a for a in allegati if not a[0].endswith(".zip")]

    if not smtp_pass:
        print("[EMAIL NOTIFIER] AVVISO: SMTP_PASS non configurato in ambiente.")
        print(f"-> Destinatario: {destinatario}")
        print(f"-> Allegati pronti ({len(allegati)}): {[a[0] for a in allegati]}")
        print("\n--- ANTEPRIMA TESTO REPORT ---\n")
        print(corpo)
        return False

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = destinatario
    msg["Subject"] = Header(oggetto, "utf-8").encode()
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    # Aggiunta allegati
    for nome_file, byte_data in allegati:
        part = MIMEApplication(byte_data)
        part.add_header("Content-Disposition", "attachment", filename=Header(nome_file, "utf-8").encode())
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[EMAIL NOTIFIER] Email inviata con successo a {destinatario} ({len(allegati)} allegati)")
        return True
    except Exception as e:
        print(f"[EMAIL NOTIFIER] Errore invio email: {e}")
        return False


def run():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Avvio aggregazione report e compressione...")
    report_text, target, n_opere = genera_report_testo()

    allegati = []

    # 1. Genera CSV
    csv_nome, csv_bytes = genera_csv_particelle(target)
    if csv_bytes:
        allegati.append((csv_nome, csv_bytes))
        print(f"-> Generato allegato: {csv_nome} ({len(csv_bytes)} bytes)")

    # 2. Genera archivio ZIP compresso con i PDF degli ultimi 7 giorni
    zip_nome, zip_bytes, n_pdf = crea_zip_pdf_settimana(giorni=7)
    if n_pdf > 0:
        allegati.append((zip_nome, zip_bytes))
        mb_zip = len(zip_bytes) / (1024 * 1024)
        print(f"-> Creato archivio compresso: {zip_nome} ({n_pdf} PDF, {mb_zip:.2f} MB)")
    else:
        print("-> Nessun nuovo PDF scaricato negli ultimi 7 giorni da comprimere.")

    titolo = f"🏛 [Motore Espropri Italia] Report Settimanale Espropri: {n_opere} target | {n_pdf} nuovi PDF"
    invia_email(titolo, report_text, allegati)


if __name__ == "__main__":
    run()
