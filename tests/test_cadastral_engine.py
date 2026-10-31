import pytest
from fastapi.testclient import TestClient
import geopandas as gpd
from shapely.geometry import LineString, Polygon
from server import app
from motore_cadastral_engine import (
    normalizza_codice,
    ParametriEconomici,
    ParametriEconomiciComune,
    calcola_quadro_indennitario_analitico,
    analizza_interferenze_e_interclusione
)

client = TestClient(app)

def test_normalizza_codice():
    assert normalizza_codice("00123") == "123"
    assert normalizza_codice("  00456B  ") == "456B"
    assert normalizza_codice(None) == ""
    assert normalizza_codice("") == ""

def test_calcola_quadro_indennitario_analitico():
    parametri = ParametriEconomiciComune(
        valore_venale_agricolo_mq=5.0,
        valore_agricolo_medio_mq=3.2,
        valore_venale_edificabile_mq=90.0,
        saggio_asservimento=0.35,
        durata_anni_cantiere=2.0
    )

    row = {
        "comune": "Vicenza",
        "foglio": "34",
        "mappale": "128",
        "destinazione": "Agricola",
        "QUALIFICA_SOGGETTO": "PROPRIETARIO_COLTIVATORE_IAP",
        "sup_esproprio_mq": 1000.0,
        "sup_asservimento_mq": 500.0,
        "sup_cantiere_mq": 200.0,
        "sup_residua_mq": 300.0,
        "relitto_critico": True
    }

    res = calcola_quadro_indennitario_analitico(row, parametri, opzione_cessione_volontaria=True)
    assert res["comune"] == "Vicenza"
    assert res["indennita"]["esproprio_base_eur"] == 5000.0
    # CD/IAP cessione volontaria: maggiorazione pari a base * 2
    assert res["indennita"]["aggiuntiva_cd_iap_eur"] == 10000.0
    assert res["indennita"]["totale_liquidabile_eur"] > 15000.0

def test_analizza_interferenze_e_interclusione_topologica():
    # Creazione particella mock (quadrato 100x100m)
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    gdf_catasto = gpd.GeoDataFrame([{"COMUNE": "Milano", "FOGLIO": "1", "NUMERO": "10", "geometry": poly}], crs="EPSG:32632")
    
    # Linea tracciato che attraversa il poligono
    line = LineString([(-50, 50), (150, 50)])
    gdf_tracciato = gpd.GeoDataFrame([{"geometry": line}], crs="EPSG:32632")

    params = ParametriEconomici(buffer_esproprio_m=10.0, buffer_asservimento_m=20.0, buffer_cantiere_m=5.0)
    res = analizza_interferenze_e_interclusione(gdf_catasto, gdf_tracciato, params=params, target_crs="EPSG:32632")

    assert not res.empty
    assert res.iloc[0]["sup_esproprio_mq"] > 0
    assert bool(res.iloc[0]["has_progetto"]) is True

def test_api_catasto_interferenze():
    payload = {
        "tracciato_geojson": {
            "type": "LineString",
            "coordinates": [[11.530, 45.542], [11.540, 45.548]]
        },
        "buffer_meters": 25.0
    }
    resp = client.post("/api/catasto/interferenze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
