import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stima_delta import (
    calcola_indennita_peritale,
    InputStimaPerizia,
    DestinazioneUrbanistica,
    TipologiaIntervento,
    router as stima_router,
)

app = FastAPI()
app.include_router(stima_router)
client = TestClient(app)

def test_calcolo_esproprio_totale_edificabile_standard():
    payload = InputStimaPerizia(
        superficie_mq=1000.0,
        destinazione=DestinazioneUrbanistica.EDIFICABILE,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=40.0,
        valore_venale_mercato_mq=120.0,
        saggio_deprezzamento_asservimento=0.5,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=5000.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=False,
    )
    res = calcola_indennita_peritale(payload)
    assert res.totale_offerta_ente == 40000.0
    assert res.totale_stima_peritale == 125000.0
    assert res.delta_recuperabile == 85000.0
    assert res.percentuale_recupero == 212.5
    assert res.base_onorario_tecnico_consigliato == 8500.0

def test_calcolo_asservimento_con_relitto_e_cd_iap():
    payload = InputStimaPerizia(
        superficie_mq=3500.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ASSERVIMENTO,
        offerta_unitaria_ente=4.50,
        valore_venale_mercato_mq=18.0,
        saggio_deprezzamento_asservimento=0.50,
        deprezzamento_relitto_euro=5000.0,
        valore_soprassuoli_euro=3200.0,
        frutti_pendenti_euro=800.0,
        is_coltivatore_diretto_o_iap=True,
        vam_tabellare_mq=6.20,
        adesione_cessione_volontaria=False,
    )
    res = calcola_indennita_peritale(payload)
    assert res.totale_offerta_ente == 15750.0
    assert res.dettaglio_calcolo["indennita_suolo_reale"] == 31500.0
    assert res.dettaglio_calcolo["deprezzamento_relitto_art33"] == 5000.0
    assert res.dettaglio_calcolo["soprassuoli_e_frutti"] == 4000.0
    assert res.dettaglio_calcolo["indennita_aggiuntiva_cd_iap_art40"] == 21700.0
    assert res.totale_stima_peritale == 62200.0
    assert res.delta_recuperabile == 46450.0
    assert pytest.approx(res.percentuale_recupero, rel=1e-2) == 294.92

def test_maggiorazione_cessione_volontaria_art45():
    payload = InputStimaPerizia(
        superficie_mq=2000.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=10.0,
        valore_venale_mercato_mq=20.0,
        saggio_deprezzamento_asservimento=0.5,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=0.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=True,
    )
    res = calcola_indennita_peritale(payload)
    assert res.dettaglio_calcolo["indennita_suolo_reale"] == 40000.0
    assert res.dettaglio_calcolo["maggiorazione_cessione_art45"] == 20000.0
    assert res.totale_stima_peritale == 60000.0

def test_occupazione_temporanea_art50():
    payload = InputStimaPerizia(
        superficie_mq=1200.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.OCCUPAZIONE_TEMPORANEA,
        offerta_unitaria_ente=1.0,
        valore_venale_mercato_mq=12.0,
        saggio_deprezzamento_asservimento=0.0,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=0.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=False,
        anni_occupazione=2.0,
    )
    res = calcola_indennita_peritale(payload)
    assert res.totale_stima_peritale == 2400.0
    assert res.delta_recuperabile == 1200.0

def test_offerta_superiore_alla_stima_delta_non_negativo():
    payload = InputStimaPerizia(
        superficie_mq=500.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=50.0,
        valore_venale_mercato_mq=20.0,
        saggio_deprezzamento_asservimento=0.5,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=0.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=False,
    )
    res = calcola_indennita_peritale(payload)
    assert res.delta_recuperabile == 0.0
    assert res.base_onorario_tecnico_consigliato == 0.0

def test_api_stima_delta_endpoint_success():
    payload_json = {
        "superficie_mq": 1000.0,
        "destinazione": "edificabile",
        "intervento": "esproprio_totale",
        "offerta_unitaria_ente": 50.0,
        "valore_venale_mercato_mq": 150.0,
        "saggio_deprezzamento_asservimento": 0.5,
        "deprezzamento_relitto_euro": 0.0,
        "valore_soprassuoli_euro": 0.0,
        "frutti_pendenti_euro": 0.0,
        "is_coltivatore_diretto_o_iap": False,
        "vam_tabellare_mq": 0.0,
        "adesione_cessione_volontaria": False,
        "anni_occupazione": 1.0,
    }
    response = client.post("/api/stima/delta-recuperabile", json=payload_json)
    assert response.status_code == 200
    data = response.json()
    assert data["totale_offerta_ente"] == 50000.0
    assert data["totale_stima_peritale"] == 150000.0
    assert data["delta_recuperabile"] == 100000.0
    assert data["base_onorario_tecnico_consigliato"] == 10000.0

def test_api_stima_delta_validazione_pydantic():
    invalid_payload = {
        "superficie_mq": 0.0,
        "destinazione": "agricola",
        "intervento": "esproprio_totale",
        "offerta_unitaria_ente": 10.0,
        "valore_venale_mercato_mq": 20.0,
    }
    response = client.post("/api/stima/delta-recuperabile", json=invalid_payload)
    assert response.status_code == 422

@pytest.fixture
def mock_dataset_opere():
    return [
        {"slug": "opera-terna-1", "giorni_residui": 5, "particelle": [{"foglio": "12", "mappale": "101"}]},
        {"slug": "opera-anas-tangenziale", "giorni_residui": 28, "particelle": [{"foglio": "4", "mappale": "22"}]},
        {"slug": "opera-metanodotto-snam", "giorni_residui": 3, "particelle": []},
        {"slug": "opera-ferrovia-rfi", "giorni_residui": None, "particelle": None},
    ]

def filtra_opere(opere, criterio: str):
    if criterio == "pda":
        return [o for o in opere if o.get("particelle") and len(o["particelle"]) > 0]
    elif criterio == "settimana":
        return [o for o in opere if o.get("giorni_residui") is not None and 0 <= o["giorni_residui"] <= 7]
    return opere

def test_filtro_pda_solo_opere_con_elenco_ditte(mock_dataset_opere):
    risultati = filtra_opere(mock_dataset_opere, "pda")
    slugs = [o["slug"] for o in risultati]
    assert len(risultati) == 2
    assert "opera-terna-1" in slugs
    assert "opera-anas-tangenziale" in slugs
    assert "opera-metanodotto-snam" not in slugs
    assert "opera-ferrovia-rfi" not in slugs

def test_filtro_settimana_scadenze_imminenti(mock_dataset_opere):
    risultati = filtra_opere(mock_dataset_opere, "settimana")
    slugs = [o["slug"] for o in risultati]
    assert len(risultati) == 2
    assert "opera-terna-1" in slugs
    assert "opera-metanodotto-snam" in slugs
    assert "opera-anas-tangenziale" not in slugs
    assert "opera-ferrovia-rfi" not in slugs
