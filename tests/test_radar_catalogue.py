from fastapi.testclient import TestClient
import server
from radar_catalogue import radar_catalogue


def test_radar_pubblico_coerente_senza_stati_o_persone_inventate(monkeypatch):
    monkeypatch.setenv('MOTORE_PUBLIC_CATALOGUE_ONLY', '1')
    client = TestClient(server.app)
    data = client.get('/api/radar').json()
    assert data['schema'] == 'motore-radar-v1'
    assert data['riepilogo']['opere'] == 7
    assert data['riepilogo']['documenti'] == 17
    assert data['riepilogo']['localizzate'] == 1
    assert data['riepilogo']['particelle_uniche'] == 3
    assert data['riepilogo']['senza_stato'] == 7
    assert data['acquisizioni']['monitoraggio'] == 'non_pubblicato'
    assert data['acquisizioni']['aggiornato_il']
    assert all(o['origine'] == 'ARCHIVIO_DOCUMENTALE' for o in data['opere'])
    assert all(o['stato_procedurale'] == 'DA_VERIFICARE' for o in data['opere'])
    assert all('ditte' not in o and 'intestatario' not in o for o in data['opere'])
    for route in ('/', '/radar', '/radar.html'):
        response = client.get(route)
        assert response.status_code == 200
        assert '/radar.js' in response.text
    assert 'map_workspace.js' in client.get('/mappa').text


def test_documento_generico_non_diventa_elenco_e_date_sono_cronologiche():
    opera = dict(slug='fixture', titolo='Fixture isolata', tipo_dati='documentale',
                 documenti=[dict(tipo='documento', titolo='Avviso procedimento', acquisito_il='2026-11-01T10:00:00+02:00')],
                 ditte=[], stato_opera='DOCUMENTI_ARCHIVIATI')
    data = radar_catalogue([opera], {'ultime_acquisizioni': [
        dict(eseguito_il='2026-11-01T09:00:00Z', stato='errore_download'),
        dict(eseguito_il='2026-11-01T10:30:00+02:00', stato='pagina_consultata')]})
    row = data['opere'][0]
    assert row['disponibilita'] == 'DOCUMENTI_DA_VERIFICARE'
    assert row['stato_procedurale'] == 'DA_VERIFICARE'
    assert not row['localizzata']
    assert data['acquisizioni']['ultimo_esito'] == 'errore_download'
    assert data['acquisizioni']['errori_tentativi'] == 1
    assert row['ultima_acquisizione_il'] == '2026-11-01T08:00:00+00:00'


def test_elenco_attivo_e_stato_esplicito_con_provenienza_di_catalogo():
    op = dict(slug='fixture', titolo='Fixture', stato_opera='AVANZATA_SENZA_ELENCO',
              fonte_atto_url='https://ente.example/atto', documenti=[
                  dict(tipo='elenco_ditte', titolo='Elenco precedente', attivo=0),
                  dict(tipo='documento', titolo='Piano particellare', attivo=1, fonte_url='https://ente.example/pdf')])
    row = radar_catalogue([op])['opere'][0]
    assert row['documenti'] == 1
    assert row['disponibilita'] == 'ELENCO_DISPONIBILE'
    assert row['stato_procedurale'] == 'AVANZATA_SENZA_ELENCO'
    assert row['host_fonti'] == ['ente.example']


def test_api_radar_non_espone_dettagli_privati_dei_tentativi(monkeypatch):
    monkeypatch.setattr(server, 'load_opere', lambda **kw: [dict(slug='fixture', titolo='Fixture')])
    class Archive:
        def status(self):
            return {'ultime_acquisizioni': [dict(eseguito_il='2026-11-01', stato='errore_download',
                                                dettaglio='DETTAGLIO_RISERVATO', url='/private/file.pdf')]}
    monkeypatch.setattr(server, 'archive_store', lambda: Archive())
    response = TestClient(server.app).get('/api/radar')
    assert response.status_code == 200
    assert 'DETTAGLIO_RISERVATO' not in response.text
    assert '/private/' not in response.text
