import io
import zipfile
from pathlib import Path
from email_notifier import genera_report_testo, genera_csv_particelle, crea_zip_pdf_settimana


def test_genera_report_testo():
    report_text, target, n_opere = genera_report_testo()
    assert isinstance(report_text, str)
    assert "REPORT MOTORE ESPROPRI ITALIA" in report_text
    assert n_opere >= 0
    assert isinstance(target, list)


def test_genera_csv_particelle():
    fake_opere = [
        {
            "slug": "opera-test",
            "cup": "C12345678901234",
            "ente": "ANAS S.p.A.",
            "comune": "Roma",
            "ditte": [
                {
                    "comune": "Roma",
                    "intestatario": "Mario Rossi",
                    "foglio": "12",
                    "mappali": "101",
                    "sup_mq": 1500,
                    "indennita": 30000,
                    "delta": True,
                    "note": "Opposizione attiva"
                }
            ]
        }
    ]
    filename, csv_bytes = genera_csv_particelle(fake_opere)
    assert filename.startswith("estrazione_particelle_")
    assert filename.endswith(".csv")
    csv_str = csv_bytes.decode("utf-8")
    assert "\ufeff" in csv_str  # UTF-8 BOM
    assert "Mario Rossi" in csv_str
    assert "ANAS S.p.A." in csv_str
    assert "101" in csv_str


def test_crea_zip_pdf_settimana(tmp_path, monkeypatch):
    # Simula una directory con un PDF temporaneo recente
    pdf_test = tmp_path / "piano_ditte_test.pdf"
    pdf_test.write_bytes(b"%PDF-1.4 test particellare")

    import email_notifier
    monkeypatch.setattr(email_notifier, "PDF_DIR", tmp_path)

    zip_nome, zip_bytes, n_pdf = crea_zip_pdf_settimana(giorni=7)
    assert n_pdf == 1
    assert zip_nome.startswith("piani_particellari_settimana_")
    assert zip_nome.endswith(".zip")

    # Verifica integrità dello zip
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        nomi = zf.namelist()
        assert "piano_ditte_test.pdf" in nomi
        assert zf.read("piano_ditte_test.pdf") == b"%PDF-1.4 test particellare"
