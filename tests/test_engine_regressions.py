"""Casi reali di regressione per ingestione, topologia, stime e API."""
import json
import math
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from shapely.geometry import LineString, Polygon, box

import server
from motore_cadastral_engine import (
    ParametriEspropri, arricchisci_catasto_con_visure,
    calcola_quadro_indennitario_analitico, calcola_stime_espropriative,
    elabora_interferenze_spaziali, normalizza_codice,
)
from stima_delta import InputStimaPerizia, calcola_indennita_peritale


def frame(geometries, **columns):
    return gpd.GeoDataFrame(columns, geometry=geometries, crs=32632)


def test_non_coltivatore_non_riceve_maggiorazione():
    for qualifica in ("PROPRIETARIO_NON_COLTIVATORE", "NON COLTIVATORE", "PROPRIETARIO"):
        res = calcola_stime_espropriative(pd.DataFrame([{
            "QUALIFICA_SOGGETTO": qualifica, "sup_esproprio_mq": 1000,
        }]))
        assert res.iloc[0].IND_AGGIUNTIVA_CD_IAP == 0


def test_helper_e_batch_hanno_stesso_totale_con_soprassuoli():
    r = {"sup_esproprio_mq": 12.3456789, "ALBERI_PREGIO_QTA": 2,
         "RECINZIONE_ML": 4, "IMPIANTO_IRRIGUO": "false", "sup_fabbricati_abbattuti_mq": 3}
    params = ParametriEspropri()
    batch = calcola_stime_espropriative(pd.DataFrame([r]), params).iloc[0]
    helper = calcola_quadro_indennitario_analitico(r, params)
    assert helper["indennita"]["totale_liquidabile_eur"] == batch.TOTALE_INDENNITA_STIMATA
    assert batch.IND_SOPRASSUOLI_MANUFATTI == 2910
    assert batch.TOTALE_INDENNITA_STIMATA == round(sum(batch[c] for c in (
        "IND_ESPROPRIO_BASE", "IND_AGGIUNTIVA_CD_IAP", "IND_ASSERVIMENTO",
        "IND_CANTIERE_ART50", "IND_SOPRASSUOLI_MANUFATTI", "DANNO_RELITTO_ART33")), 2)


def test_visure_minime_comproprieta_e_codici_excel(tmp_path):
    catasto = frame([box(0, 0, 10, 10)], COMUNE=["Milano"], FOGLIO=[1.0], NUMERO=["0002"])
    path = tmp_path / "visure.csv"
    path.write_text("COMUNE;FOGLIO;MAPPALE;INTESTATO;QUOTA\nMILANO;001;2;Rossi;1/2\nMILANO;1.0;002;Bianchi;1/2\n")
    res = arricchisci_catasto_con_visure(catasto, str(path))
    assert len(res) == 1
    assert res.iloc[0].NUM_INTESTATI == 2
    assert "Rossi" in res.iloc[0].INTESTATI_COMPLETI
    assert "Bianchi" in res.iloc[0].INTESTATI_COMPLETI
    assert res.iloc[0].ALBERI_PREGIO_QTA == 0
    assert not res.iloc[0].IMPIANTO_IRRIGUO
    assert res.iloc[0].QUALIFICA_SOGGETTO == "PROPRIETARIO_NON_COLTIVATORE"
    assert normalizza_codice(1.0) == normalizza_codice("001")


def test_visure_preservano_dati_e_booleani(tmp_path):
    catasto = frame([box(0, 0, 10, 10)], COMUNE=["Milano"], FOGLIO=[1], NUMERO=[2], DESTINAZIONE_URB=["Edificabile"])
    path = tmp_path / "visure.csv"
    path.write_text("COMUNE;FOGLIO;MAPPALE;INTESTATO;IMPIANTO_IRRIGUO\nMILANO;1;2;Rossi;false\n")
    res = arricchisci_catasto_con_visure(catasto, str(path))
    assert res.iloc[0].DESTINAZIONE_URB == "Edificabile"
    assert not res.iloc[0].IMPIANTO_IRRIGUO


def test_superfici_precise_fasce_disgiunte_e_fabbricati_duplicati():
    catasto = frame([box(0, 0, 100.123456, 100)])
    traccia = frame([LineString([(-100, 50), (200, 50)])])
    fabbricato = box(10, 45, 20, 55)
    result = elabora_interferenze_spaziali(catasto, traccia, gdf_fabbricati=frame([fabbricato, fabbricato]))
    r = result.iloc[0]
    assert r.sup_esproprio_mq == pytest.approx(100.123456 * 24)
    assert r.sup_fabbricati_abbattuti_mq == 100
    assert r.sup_esproprio_mq + r.sup_residua_mq == pytest.approx(r.sup_totale_mq)
    assert r.sup_esproprio_mq + r.sup_asservimento_mq + r.sup_cantiere_mq <= r.sup_totale_mq
    assert not r.accessibilita_verificata


def test_geometrie_invalide_riparate_e_risultato_vuoto():
    catasto = frame([Polygon([(0, 0), (100, 100), (0, 100), (100, 0), (0, 0)])])
    traccia = frame([LineString([(-100, 50), (200, 50)])])
    assert elabora_interferenze_spaziali(catasto, traccia).geometry.is_valid.all()
    vuoto = elabora_interferenze_spaziali(frame([box(1000, 1000, 1100, 1100)]), traccia)
    assert vuoto.empty and vuoto.crs.to_epsg() == 32632


@pytest.mark.parametrize("params", [{"buffer_esproprio_m": -1}, {"saggio_asservimento": 2}, {"durata_anni_cantiere": math.nan}, {"buffer_asservimento_m": 1}])
def test_parametri_non_validi(params):
    with pytest.raises(ValueError):
        ParametriEspropri(**params)


def test_crs_geografico_rifiutato_per_misure_metriche():
    with pytest.raises(ValueError, match="metri"):
        elabora_interferenze_spaziali(frame([box(0, 0, 100, 100)]), frame([LineString([(0, 0), (100, 100)])]), target_crs=4326)


def test_cache_invalida_e_non_condivide_oggetti_mutabili(tmp_path, monkeypatch):
    path = tmp_path / "opere.json"
    monkeypatch.setattr(server, "DATA_PATH", path)
    server.save_opere([{"slug": "prima"}])
    server.load_opere()[0]["slug"] = "alterata"
    assert server.load_opere()[0]["slug"] == "prima"
    path.write_text('[{"slug":"seconda"}]')
    assert server.load_opere()[0]["slug"] == "seconda"
    with pytest.raises(ValueError):
        server.save_opere([{"value": math.nan}])
    assert json.loads(path.read_text()) == [{"slug": "seconda"}]


def test_inserimento_non_documentato_rifiutato_in_produzione(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_PATH", tmp_path / "opere.json")
    response = TestClient(server.app).post("/api/opere", json={"titolo": "Senza fonte", "ditte": [{"intestatario": "Non documentato"}]})
    assert response.status_code == 409
    assert not server.DATA_PATH.exists()


def test_api_rifiuta_interferenze_da_solo_asse():
    response = TestClient(server.app).post('/api/catasto/interferenze', json={
        'tracciato_geojson': {'type': 'LineString', 'coordinates': [[16, 38], [16.01, 38.01]]}})
    assert response.status_code == 409
    assert 'Nessuna fascia' in response.json()['detail']


def test_occupazione_non_riceve_cessione_o_vam():
    data = InputStimaPerizia(superficie_mq=100, destinazione="agricola", intervento="occupazione_temporanea",
                            offerta_unitaria_ente=1, valore_venale_mercato_mq=12,
                            is_coltivatore_diretto_o_iap=True, adesione_cessione_volontaria=True)
    result = calcola_indennita_peritale(data)
    assert result.totale_stima_peritale == 100
    assert result.dettaglio_calcolo["maggiorazione_cessione_art45"] == 0


def test_vam_non_inventato_e_numeri_finiti():
    data = dict(superficie_mq=100, destinazione="agricola", intervento="esproprio_totale",
                offerta_unitaria_ente=1, valore_venale_mercato_mq=12)
    with pytest.raises(ValidationError, match="VAM"):
        InputStimaPerizia(**data, is_coltivatore_diretto_o_iap=True)
    with pytest.raises(ValidationError):
        InputStimaPerizia(**dict(data, superficie_mq=math.inf))


def test_danno_interclusione_solo_sulla_porzione_che_perde_accesso():
    catasto = frame([box(0, 0, 100, 100)])
    asse = frame([LineString([(-50, 50), (150, 50)])])
    strada = frame([LineString([(-10, 0), (110, 0)])])
    result = elabora_interferenze_spaziali(catasto, asse, gdf_strade=strada,
                                           params=ParametriEspropri(buffer_esproprio_m=10))
    r = result.iloc[0]
    assert r.relitto_intercluso_art33
    assert r.sup_residua_mq == 8000
    assert r.sup_residua_interclusa_mq == 4000
    assert calcola_stime_espropriative(result).iloc[0].DANNO_RELITTO_ART33 == 20000


def test_fondo_gia_senza_accesso_non_imputa_danno_al_progetto():
    result = elabora_interferenze_spaziali(frame([box(0, 0, 100, 100)]),
        frame([LineString([(-50, 50), (150, 50)])]),
        gdf_strade=frame([LineString([(-50, -20), (150, -20)])]))
    assert not result.iloc[0].relitto_intercluso_art33
    assert result.iloc[0].sup_residua_interclusa_mq == 0


def test_solo_asservimento_non_genera_danno_relitto_da_esproprio():
    result = elabora_interferenze_spaziali(frame([box(15, 0, 25, 10)]),
        frame([LineString([(0, -50), (0, 50)])]))
    assert result.iloc[0].sup_esproprio_mq == 0
    assert not result.iloc[0].relitto_critico
    assert calcola_stime_espropriative(result).iloc[0].DANNO_RELITTO_ART33 == 0


def test_crs_automatico_italia_meridionale_e_geometria_nome_personalizzato():
    catasto = gpd.GeoDataFrame(geometry=[box(16.0, 38.0, 16.001, 38.001)], crs=4326).rename_geometry("geom")
    asse = gpd.GeoDataFrame(geometry=[LineString([(16, 38), (16.001, 38.001)])], crs=4326)
    result = elabora_interferenze_spaziali(catasto, asse)
    assert result.crs.to_epsg() == 32633
    assert result.geometry.name == "geom"
    assert 9000 < result.iloc[0].sup_totale_mq < 11000
    mercator = elabora_interferenze_spaziali(catasto.to_crs(3857), asse)
    assert mercator.crs.to_epsg() == 32633
    assert mercator.iloc[0].sup_totale_mq == pytest.approx(result.iloc[0].sup_totale_mq)
