#!/usr/bin/env python3
"""
Test suite pytest per il Motore Espropri Italia.
Verifica:
1. Validità aritmetica ed estimativa del calcolatore Delta Indennità (D.P.R. 327/2001).
2. Endpoint REST FastAPI.
3. Filtri di selezione telemetrica delle opere (PdA, Scadenze settimanali).
"""

import pytest
from fastapi.testclient import TestClient

# Import dei moduli interni del progetto
from stima_delta import (
    calcola_indennita_peritale,
    InputStimaPerizia,
    DestinazioneUrbanistica,
    TipologiaIntervento,
    router as stima_router,
)
from fastapi import FastAPI

# Inizializzazione app FastAPI minimale per TestClient isolato
app = FastAPI()
app.include_router(stima_router)
client = TestClient(app)


# ============================================================================
# 1. TEST UNITARI: CORRETTEZZA MATEMATICA ESTIMATIVA (D.P.R. 327/2001)
# ============================================================================

def test_calcolo_esproprio_totale_edificabile_standard():
    """
    Verifica esproprio totale su area edificabile (Art. 37 DPR 327/2001 post C.Cost. 348/2007).
    Nessuna maggiorazione CD, nessuna cessione volontaria.
    """
    payload = InputStimaPerizia(
        superficie_mq=1000.0,
        destinazione=DestinazioneUrbanistica.EDIFICABILE,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=40.0,         # Ente offre 40 €/mq -> Totale 40.000 €
        valore_venale_mercato_mq=120.0,    # Valore venale peritale 120 €/mq -> Totale 120.000 €
        saggio_deprezzamento_asservimento=0.5,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=5000.0,     # Muro di recinzione
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=False,
    )

    res = calcola_indennita_peritale(payload)

    # 1.000 mq * 40 €/mq = 40.000 €
    assert res.totale_offerta_ente == 40000.0
    # (1.000 * 120 €/mq) + 5.000 € soprassuoli = 125.000 €
    assert res.totale_stima_peritale == 125000.0
    # 125.000 € - 40.000 € = 85.000 €
    assert res.delta_recuperabile == 85000.0
    # Percentuale recupero: (85.000 / 40.000) * 100 = 212.5%
    assert res.percentuale_recupero == 212.5
    # Base onorario al 10% del delta recuperato = 8.500 €
    assert res.base_onorario_tecnico_consigliato == 8500.0


def test_calcolo_asservimento_con_relitto_e_cd_iap():
    """
    Verifica asservimento con conduttore Coltivatore Diretto / IAP (Art. 40 c. 4)
    e deprezzamento della porzione residua (Art. 33).
    """
    payload = InputStimaPerizia(
        superficie_mq=3500.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ASSERVIMENTO,
        offerta_unitaria_ente=4.50,         # Ente offre 4.5 €/mq -> 15.750 €
        valore_venale_mercato_mq=18.0,      # Mercato 18.0 €/mq
        saggio_deprezzamento_asservimento=0.50, # 50% di svalutazione fascia
        deprezzamento_relitto_euro=5000.0,  # Danno porzione interclusa/danneggiata
        valore_soprassuoli_euro=3200.0,
        frutti_pendenti_euro=800.0,
        is_coltivatore_diretto_o_iap=True,  # Ha diritto al VAM aggiuntivo
        vam_tabellare_mq=6.20,              # VAM 6.2 €/mq * 3500 mq = 21.700 €
        adesione_cessione_volontaria=False,
    )

    res = calcola_indennita_peritale(payload)

    # 3500 * 4.50 = 15.750 €
    assert res.totale_offerta_ente == 15750.0

    # Dettagli peritali attesi:
    # Suolo asservito: 3500 * 18.0 * 0.50 = 31.500 €
    assert res.dettaglio_calcolo["indennita_suolo_reale"] == 31500.0
    # Danno relitto: 5.000 €
    assert res.dettaglio_calcolo["deprezzamento_relitto_art33"] == 5000.0
    # Soprassuoli e frutti: 3.200 + 800 = 4.000 €
    assert res.dettaglio_calcolo["soprassuoli_e_frutti"] == 4000.0
    # Maggiorazione CD: 3500 * 6.20 = 21.700 €
    assert res.dettaglio_calcolo["indennita_aggiuntiva_cd_iap_art40"] == 21700.0

    # Totale Stima = 31.500 + 5.000 + 4.000 + 21.700 = 62.200 €
    assert res.totale_stima_peritale == 62200.0
    # Delta = 62.200 - 15.750 = 46.450 €
    assert res.delta_recuperabile == 46450.0
    assert pytest.approx(res.percentuale_recupero, rel=1e-2) == 294.92


def test_maggiorazione_cessione_volontaria_art45():
    """
    Verifica l'applicazione della maggiorazione del 50% su area agricola
    in caso di stipula di accordo di cessione volontaria (Art. 45 c. 2 lett. a).
    """
    payload = InputStimaPerizia(
        superficie_mq=2000.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=10.0,
        valore_venale_mercato_mq=20.0,      # Base reale: 2000 * 20 = 40.000 €
        saggio_deprezzamento_asservimento=0.5,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=0.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=True,   # +50% sul suolo
    )

    res = calcola_indennita_peritale(payload)

    # Suolo base: 40.000 €
    assert res.dettaglio_calcolo["indennita_suolo_reale"] == 40000.0
    # Maggiorazione 50%: 20.000 €
    assert res.dettaglio_calcolo["maggiorazione_cessione_art45"] == 20000.0
    # Totale: 60.000 €
    assert res.totale_stima_peritale == 60000.0


def test_occupazione_temporanea_art50():
    """
    Verifica occupazione temporanea di cantiere: 1/12 del valore venale all'anno (Art. 50).
    Durata: 2 anni.
    """
    payload = InputStimaPerizia(
        superficie_mq=1200.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.OCCUPAZIONE_TEMPORANEA,
        offerta_unitaria_ente=1.0,          # Offerta ente: 1.200 €
        valore_venale_mercato_mq=12.0,      # Valore intero suolo = 14.400 €
        saggio_deprezzamento_asservimento=0.0,
        deprezzamento_relitto_euro=0.0,
        valore_soprassuoli_euro=0.0,
        frutti_pendenti_euro=0.0,
        is_coltivatore_diretto_o_iap=False,
        vam_tabellare_mq=0.0,
        adesione_cessione_volontaria=False,
        anni_occupazione=2.0,               # 2 anni
    )

    res = calcola_indennita_peritale(payload)

    # Quota annuale = 14.400 / 12 = 1.200 €/anno -> Per 2 anni = 2.400 €
    assert res.totale_stima_peritale == 2400.0
    # Delta = 2.400 - 1.200 = 1.200 €
    assert res.delta_recuperabile == 1200.0


def test_offerta_superiore_alla_stima_delta_non_negativo():
    """
    Se l'offerta dell'ente risulta per paradosso superiore al valore di stima,
    il delta recuperabile deve rimanere 0.0 (nessuna perdita per il periziando).
    """
    payload = InputStimaPerizia(
        superficie_mq=500.0,
        destinazione=DestinazioneUrbanistica.AGRICOLA,
        intervento=TipologiaIntervento.ESPROPRIO_TOTALE,
        offerta_unitaria_ente=50.0,         # Ente offre 25.000 €
        valore_venale_mercato_mq=20.0,      # Perizia vale 10.000 €
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


# ============================================================================
# 2. TEST INTEGRATIVI ENDPOINT FASTAPI
# ============================================================================

def test_api_stima_delta_endpoint_success():
    """Verifica risposta 200 OK e JSON payload dell'endpoint FastAPI."""
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
        "anni_occupazione": 1.0
    }

    response = client.post("/api/stima/delta-recuperabile", json=payload_json)
    assert response.status_code == 200
    data = response.json()

    assert data["totale_offerta_ente"] == 50000.0
    assert data["totale_stima_peritale"] == 150000.0
    assert data["delta_recuperabile"] == 100000.0
    assert data["base_onorario_tecnico_consigliato"] == 10000.0


def test_api_stima_delta_validazione_pydantic():
    """Verifica fallimento con errore 422 se la superficie è non valida (<= 0)."""
    invalid_payload = {
        "superficie_mq": 0.0,  # gt=0 violato
        "destinazione": "agricola",
        "intervento": "esproprio_totale",
        "offerta_unitaria_ente": 10.0,
        "valore_venale_mercato_mq": 20.0
    }
    response = client.post("/api/stima/delta-recuperabile", json=invalid_payload)
    assert response.status_code == 422


# ============================================================================
# 3. TEST UNITARI: LOGICA FILTRI TELEMETRIA OPERE (PdA & Settimana)
# ============================================================================

@pytest.fixture
def mock_dataset_opere():
    """Dataset di test con casistiche eterogenee di opere e piani particellari."""
    return [
        {
            "slug": "opera-terna-1",
            "titolo": "Raccordo RTN 380kV",
            "giorni_residui": 5,           # Scade in settimana (<= 7)
            "particelle": [{"foglio": "12", "mappale": "101"}] # Ha PdA depositato
        },
        {
            "slug": "opera-anas-tangenziale",
            "titolo": "Variante SS42",
            "giorni_residui": 28,          # Termini ampi (> 7)
            "particelle": [{"foglio": "4", "mappale": "22"}, {"foglio": "4", "mappale": "23"}] # Ha PdA
        },
        {
            "slug": "opera-metanodotto-snam",
            "titolo": "Metanodotto DN 600",
            "giorni_residui": 3,           # Scade in settimana (<= 7)
            "particelle": []               # PdA NON ancora depositato
        },
        {
            "slug": "opera-ferrovia-rfi",
            "titolo": "Raddoppio Ferroviario",
            "giorni_residui": None,        # Fase preliminare, nessun termine aperto
            "particelle": None
        }
    ]


def filtra_opere(opere, criterio: str):
    """Implementazione Python pura della logica usata nel controller JS / backend."""
    if criterio == "pda":
        return [o for o in opere if o.get("particelle") and len(o["particelle"]) > 0]
    elif criterio == "settimana":
        return [
            o for o in opere 
            if o.get("giorni_residui") is not None and 0 <= o["giorni_residui"] <= 7
        ]
    return opere


def test_filtro_pda_solo_opere_con_elenco_ditte(mock_dataset_opere):
    """Il filtro PdA deve restituire solo opere con almeno 1 particella censita."""
    risultati = filtra_opere(mock_dataset_opere, "pda")
    slugs = [o["slug"] for o in risultati]

    assert len(risultati) == 2
    assert "opera-terna-1" in slugs
    assert "opera-anas-tangenziale" in slugs
    assert "opera-metanodotto-snam" not in slugs
    assert "opera-ferrovia-rfi" not in slugs


def test_filtro_settimana_scadenze_imminenti(mock_dataset_opere):
    """Il filtro settimana deve isolare solo le opere con termini compresi tra 0 e 7 giorni."""
    risultati = filtra_opere(mock_dataset_opere, "settimana")
    slugs = [o["slug"] for o in risultati]

    assert len(risultati) == 2
    assert "opera-terna-1" in slugs         # giorni_residui = 5
    assert "opera-metanodotto-snam" in slugs # giorni_residui = 3
    assert "opera-anas-tangenziale" not in slugs # giorni_residui = 28
    assert "opera-ferrovia-rfi" not in slugs
