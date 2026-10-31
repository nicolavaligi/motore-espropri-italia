import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from bur_crawler import BurEspropriCrawler

def test_is_atto_art16_matching():
    crawler = BurEspropriCrawler()
    
    # Titolo tipico art. 16
    assert crawler.is_atto_art16(
        "Avviso ex art. 16 DPR 327/2001",
        "Deposito del piano particellare delle aree interessate"
    ) is True

    assert crawler.is_atto_art16(
        "Lavori elettrodotto",
        "Avviso di deposito piano particellare d'esproprio"
    ) is True

    # Atto estraneo (es. delibera ordinaria)
    assert crawler.is_atto_art16(
        "Approvazione bilancio previsione",
        "Seduta del consiglio comunale delibera n. 12"
    ) is False

def test_calcola_scadenza_default_e_specifica():
    crawler = BurEspropriCrawler()
    data_pub = datetime(2026, 10, 1)

    # Caso default: 30 giorni
    scad_default = crawler.calcola_scadenza(data_pub, "Deposito atti a disposizione per consultazione.")
    assert scad_default["giorni_concessi"] == 30
    assert scad_default["data_scadenza"] == "2026-10-31"

    # Caso con giorni specificati nel testo: 45 giorni
    scad_spec = crawler.calcola_scadenza(data_pub, "Termine di 45 giorni per la presentazione delle osservazioni.")
    assert scad_spec["giorni_concessi"] == 45
    assert scad_spec["data_scadenza"] == "2026-11-15"

def test_indicizza_nuovo_avviso_non_pertinente():
    crawler = BurEspropriCrawler()
    avviso = {
        "titolo": "Nomina commissione edilizia",
        "descrizione": "Decreto sindacale per incarichi",
        "data_pubblicazione": datetime.now()
    }
    assert crawler.indicizza_nuovo_avviso(avviso) is None

def test_indicizza_nuovo_avviso_pertinente_con_cup(tmp_path):
    crawler = BurEspropriCrawler()
    avviso = {
        "titolo": "Deposito Piano Particellare ex art 16 dpr 327",
        "descrizione": "Progetto con CUP E81B24000340001 per ampliamento viabilità. 30 giorni per osservazioni.",
        "ente": "Provincia di Lecco",
        "data_pubblicazione": datetime(2026, 10, 20),
        "pdf_url": None,
        "lat": 45.85,
        "lng": 9.39
    }

    with patch.object(crawler, "salva_o_aggiorna_opera", return_value=None):
        opera = crawler.indicizza_nuovo_avviso(avviso)

    assert opera is not None
    assert opera["cup"] == "E81B24000340001"
    assert opera["ente_promotore"] == "Provincia di Lecco"
    assert opera["fase_procedimento"] == 4
    assert opera["stato_codice"] == "PDA"
    assert opera["lat"] == 45.85
