import pytest
from unittest.mock import MagicMock, patch
from extract_particellare import (
    clean_text,
    parse_float,
    extract_cf,
    parse_raw_table_rows,
    extract_piano_particellare,
)

def test_clean_text_normalizzazione():
    raw = "  Comune di   Dervio \n\r (LC)  \n "
    assert clean_text(raw) == "Comune di Dervio (LC)"
    assert clean_text(None) == ""

def test_parse_float_formattazione_italiana():
    assert parse_float("1.450,50 mq") == 1450.5
    assert parse_float("250 m²") == 250.0
    assert parse_float("12.000") == 12000.0
    assert parse_float("") == 0.0
    assert parse_float(None) == 0.0

def test_extract_cf_e_piva():
    testo_con_cf = "ROSSI MARIO C.F. RSSMRA80A01H501Z PROPRIETARIO"
    assert extract_cf(testo_con_cf) == "RSSMRA80A01H501Z"

    testo_con_piva = "TERNA RETE ITALIA S.P.A. P.IVA 05779661007"
    assert extract_cf(testo_con_piva) == "05779661007"

    testo_senza_cf = "COMUNE DI BERGAMO"
    assert extract_cf(testo_senza_cf) is None

def test_parse_raw_table_rows_funzionamento():
    tabella_finta = [
        ["Comune", "Foglio", "Mappale", "Sub", "Intestatario / Ditta", "Sup. Totale", "Sup. Esproprio", "Sup. Asserv."],
        ["Dervio", "12", "101", "", "ROSSI MARIO RSSMRA80A01H501Z", "5.000 mq", "1.200,50 mq", "350 mq"],
        ["Dervio", "12", "102", "1", "SOCIETA AGRICOLA SRL 01234567890", "12.500 mq", "0", "4.200 mq"],
        ["", "TOTALE", "", "", "", "", "1.200,50 mq", "4.550 mq"] # Riga totale da ignorare
    ]

    risultati = parse_raw_table_rows(tabella_finta)

    assert len(risultati) == 2

    # Verifica record 1
    p1 = risultati[0]
    assert p1["foglio"] == "12"
    assert p1["mappale"] == "101"
    assert p1["intestatario"] == "ROSSI MARIO"
    assert p1["codice_fiscale"] == "RSSMRA80A01H501Z"
    assert p1["superfici_mq"]["totale"] == 5000.0
    assert p1["superfici_mq"]["esproprio"] == 1200.5
    assert p1["superfici_mq"]["asservimento"] == 350.0

    # Verifica record 2
    p2 = risultati[1]
    assert p2["foglio"] == "12"
    assert p2["mappale"] == "102"
    assert p2["sub"] == "1"
    assert p2["intestatario"] == "SOCIETA AGRICOLA SRL"
    assert p2["codice_fiscale"] == "01234567890"
    assert p2["superfici_mq"]["esproprio"] == 0.0
    assert p2["superfici_mq"]["asservimento"] == 4200.0

def test_extract_piano_particellare_con_mock_pdfplumber(tmp_path):
    # Crea un file dummy per passare la verifica path.exists()
    fake_pdf = tmp_path / "piano_particellare_test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 mock content")

    mock_table = [
        ["Fg.", "Particella", "Ditta Intestataria", "Sup. Esproprio"],
        ["8", "450", "BIANCHI LUIGI BNCLGU75C12A794X", "850,00 mq"]
    ]

    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [mock_table]

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    with patch("pdfplumber.open", return_value=mock_pdf):
        risultati = extract_piano_particellare(fake_pdf)

    assert len(risultati) == 1
    assert risultati[0]["foglio"] == "8"
    assert risultati[0]["mappale"] == "450"
    assert risultati[0]["intestatario"] == "BIANCHI LUIGI"
    assert risultati[0]["codice_fiscale"] == "BNCLGU75C12A794X"
    assert risultati[0]["superfici_mq"]["esproprio"] == 850.0
    assert risultati[0]["metadati"]["fonte_pagina"] == 1
