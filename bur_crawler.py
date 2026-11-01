#!/usr/bin/env python3
"""
Modulo: bur_crawler.py
Descrizione: Crawler per il monitoraggio dei Bollettini Ufficiali Regionali (BUR).
Rileva gli avvisi di deposito del piano particellare ditte (Art. 16 D.P.R. 327/2001),
scarica gli atti e invoca la pipeline di parsing particellare.
"""

import hashlib
import json
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

from extract_particellare import extract_piano_particellare

# Directory di archivio locale per PDF scaricati
ARCHIVE_DIR = Path("data/pdf_archivio")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# Path dataset: preferenza per data/opere.json usato dal server FastAPI
OPERE_FILE = Path("data/opere.json") if (Path("data") / "opere.json").exists() else Path("opere.json")

# Espressioni regolari per il matching procedurale stringente
REGEX_ART_16 = re.compile(
    r"(?:art(?:icolo)?\.?\s*16.*(?:327/2001|d\.?p\.?r\.?\s*327)|"
    r"deposito\s+(?:del\s+)?piano\s+particellare|"
    r"piano\s+particellare\s+d(?:'|i\s+)esproprio|"
    r"avviso\s+di\s+deposito.*espropri)",
    re.IGNORECASE
)

REGEX_CUP = re.compile(r"\b[A-Z0-9]{15}\b")
REGEX_GIORNI_OSSERVAZIONI = re.compile(r"(\d{2})\s*(?:giorni|gg).*(?:osservazion|opposiz)", re.IGNORECASE)


class BurEspropriCrawler:
    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) MotoreEspropriCrawler/1.0"
            },
            timeout=30.0,
            follow_redirects=True
        )

    def is_atto_art16(self, titolo: str, testo_sommario: str) -> bool:
        """Verifica se il sommario o il titolo dell'atto riguarda la Fase 4 ex art. 16."""
        full_text = f"{titolo} {testo_sommario}"
        return bool(REGEX_ART_16.search(full_text))

    def calcola_scadenza(self, data_pubblicazione: datetime, testo_atto: str) -> Dict[str, Any]:
        """
        Calcola i termini perentori (standard 30 giorni ex art. 16 c. 11 D.P.R. 327/2001,
        o termine specifico estratto dal bando).
        """
        match_gg = REGEX_GIORNI_OSSERVAZIONI.search(testo_atto)
        giorni_termine = int(match_gg.group(1)) if match_gg else 30

        data_scadenza = data_pubblicazione + timedelta(days=giorni_termine)
        giorni_residui = (data_scadenza.date() - datetime.now().date()).days

        return {
            "giorni_concessi": giorni_termine,
            "data_scadenza": data_scadenza.strftime("%Y-%m-%d"),
            "giorni_residui": max(0, giorni_residui),
            "in_scadenza": 0 <= giorni_residui <= 7
        }

    def processa_allegato_pdf(self, pdf_url: str, slug_opera: str) -> List[Dict[str, Any]]:
        """Scarica il PDF, lo archivia con checksum e invoca extract_piano_particellare."""
        resp = self.client.get(pdf_url)
        resp.raise_for_status()

        pdf_bytes = resp.content
        file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:12]
        pdf_path = ARCHIVE_DIR / f"{slug_opera}_{file_hash}.pdf"

        # Salva in archivio persistente
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Parsing particellare
        return extract_piano_particellare(pdf_path)

    def indicizza_nuovo_avviso(self, avviso: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analizza un singolo avviso individuato nell'indice BUR.
        Se contiene tabelle particellari o link ad allegati PDF, crea il record opera.
        """
        titolo = avviso.get("titolo", "")
        descrizione = avviso.get("descrizione", "")

        if not self.is_atto_art16(titolo, descrizione):
            return None

        # Estrazione CUP (se presente nel testo)
        match_cup = REGEX_CUP.search(f"{titolo} {descrizione}")
        cup = match_cup.group(0) if match_cup else "NON_SPECIFICATO"

        slug = f"opera-{datetime.now().strftime('%Y%m')}-{cup[-6:].lower()}"

        data_pubb = avviso.get("data_pubblicazione", datetime.now())
        scadenza_info = self.calcola_scadenza(data_pubb, descrizione)

        particelle = []
        pdf_url = avviso.get("pdf_url")
        if pdf_url:
            try:
                particelle = self.processa_allegato_pdf(pdf_url, slug)
            except Exception as e:
                print(f"[WARN] Parsing PDF fallito per {pdf_url}: {e}")

        tot_esp = sum(p.get("superfici_mq", {}).get("esproprio", 0.0) for p in particelle)
        tot_ass = sum(p.get("superfici_mq", {}).get("asservimento", 0.0) for p in particelle)

        nuova_opera = {
            "slug": slug,
            "titolo": titolo,
            "cup": cup,
            "ente_promotore": avviso.get("ente", "Ente Promotore da Atto"),
            "data_pubblicazione": data_pubb.strftime("%Y-%m-%d"),
            "termini_osservazioni": scadenza_info,
            "giorni_residui": scadenza_info["giorni_residui"],
            "stato_codice": "PDA", # Fase 4: Piano Particellare Depositato
            "fase_procedimento": 4,
            "lat": avviso.get("lat"), # Coordinate solo se fornite dalla fonte
            "lng": avviso.get("lng"),
            "sup_totale_esproprio_mq": round(tot_esp, 2),
            "sup_totale_asservimento_mq": round(tot_ass, 2),
            "particelle": particelle,
            "fonte_atto_url": avviso.get("link_atto", "")
        }

        self.salva_o_aggiorna_opera(nuova_opera)
        return nuova_opera

    def salva_o_aggiorna_opera(self, opera: Dict[str, Any]):
        raise RuntimeError("Scrittura legacy disabilitata: usare collect_public_records.py e l’archivio documentale di produzione")


if __name__ == "__main__":
    from collect_public_records import main
    main()
