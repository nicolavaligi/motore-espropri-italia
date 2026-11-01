import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

import server
from extract_particellare import parse_raw_table_rows


def feature(geometry):
    return {'type':'Feature','geometry':geometry.__geo_interface__,'properties':{'mappale':'1'}}


def test_overlay_reale_utm_conserva_aree_e_provenienza():
    payload={'ingombro_geojson':feature(box(9,45,9.001,45.001)),
             'particelle_geojson':feature(box(8.999,44.999,9.002,45.002)),
             'fonte_ingombro_url':'https://ente.it/progetto', 'fonte_catasto_url':'https://ente.it/catasto'}
    response=TestClient(server.app).post('/api/catasto/interferenze',json=payload)
    assert response.status_code==200
    data=response.json();p=data['features'][0]['properties']
    assert 8000 < p['sup_interferita_mq'] < 9000
    assert p['sup_interferita_mq'] < p['sup_totale_mq']
    assert data['metadata']['crs_calcolo']=='EPSG:32632'
    assert p['dati_catastali_verificati'] is False
    assert p['fonte_ingombro_url']==payload['fonte_ingombro_url']
    # L'ingombro duplicato non raddoppia l'area.
    payload['ingombro_geojson']={'type':'FeatureCollection','features':[payload['ingombro_geojson']]*2}
    again=TestClient(server.app).post('/api/catasto/interferenze',json=payload).json()
    assert again['features'][0]['properties']['sup_interferita_mq']==pytest.approx(p['sup_interferita_mq'])


def test_unita_e_superfici_ambigue_non_inventate():
    for header, value in [('Sup. Esproprio', '200'), ('Sup. Esproprio mq','circa 200'), ('Sup. Esproprio mq','-20')]:
        row=parse_raw_table_rows([['Foglio','Mappale',header],['1','2',value]])[0]
        assert row['superfici_mq']['esproprio'] is None
    row=parse_raw_table_rows([['Foglio','Mappale','Sup. Esproprio mq'],['1','2','0']])[0]
    assert row['superfici_mq']['esproprio']==0
