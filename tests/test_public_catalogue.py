"""Il rilascio deve funzionare senza distribuire l'archivio privato."""
import hashlib
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

import server
from public_catalogue import PublishedArchive, PUBLIC_CATALOGUE_PATH
from tools.export_public_catalogue import export_public_catalogue


def test_catalogo_deploy_senza_database_o_nominativi(monkeypatch, tmp_path):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('MOTORE_ARCHIVE_ROOT', raising=False)
    root = tmp_path / 'assente'
    monkeypatch.setattr(server, 'DEFAULT_ROOT', root)
    monkeypatch.setattr(server, 'DATA_PATH', root / 'opere.json')
    client = TestClient(server.app)
    response = client.get('/api/opere')
    assert response.status_code == 200
    opere = response.json()
    assert len(opere) == 7
    assert all(op['tipo_dati'] == 'documentale' and op['fonte_atto_url'] for op in opere)
    assert all(op['geo'] is None for op in opere)  # niente pin ricostruiti
    located = [op for op in opere if op['ditte']]
    assert len(located) == 1
    rows = client.get(f"/api/opere/{located[0]['slug']}/particelle").json()
    assert len(rows) == 5
    assert len({row['riferimento_catastale'] for row in rows}) == 3
    assert all(row['fonte_geometria'] and row['fonte_geometria_sha256'] and row['licenza_geometria'] for row in rows)
    assert all(row['intestatario'] is None and 'raw' not in row and 'codice_fiscale' not in row for row in rows)
    status = client.get('/api/archivio/stato').json()
    assert status['modalita'] == 'catalogo_pubblico_sola_lettura'
    assert status['originali_locali_pubblicati'] is False
    assert not root.exists()  # letture serverless senza mkdir/SQLite/WAL


def test_documenti_pubblici_rimandano_all_ente(monkeypatch):
    monkeypatch.setenv('MOTORE_PUBLIC_CATALOGUE_ONLY', '1')
    client = TestClient(server.app)
    opera = next(op for op in client.get('/api/opere').json() if op['documenti'])
    document = opera['documenti'][0]
    response = client.get(f"/api/documenti/{document['id']}/file", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == document['fonte_url']
    assert client.get('/api/documenti/assente/file').status_code == 404


def test_catalogo_restituisce_copie_isolate():
    archive = PublishedArchive()
    first = archive.catalogue()
    first[0]['titolo'] = 'modificato'
    assert archive.catalogue()[0]['titolo'] != 'modificato'


def test_esportatore_non_pubblica_dati_personali_e_non_modifica_database(tmp_path):
    root = tmp_path / 'private'
    root.mkdir()
    con = sqlite3.connect(root / 'archivio.sqlite3')
    con.executescript('''CREATE TABLE opere (slug TEXT, metadata TEXT);
        CREATE TABLE documenti (id TEXT, opera_slug TEXT, titolo TEXT, fonte_url TEXT,
        pagina_fonte TEXT, sha256 TEXT, acquisito_il TEXT, tipo TEXT, attivo INT,
        totale_pagine INT, stato TEXT);
        CREATE TABLE righe (id TEXT, documento_id TEXT, pagina INT, indice INT, payload TEXT);''')
    meta = dict(slug='opera', titolo='Opera da atto', tipo_dati='documentale', fonte_atto_url='https://ente.it/atto',
                intestatario='NOME_RISERVATO', nota_privata='CONTATTO_RISERVATO')
    con.execute('INSERT INTO opere VALUES (?,?)', ('opera', json.dumps(meta)))
    row = dict(comune='Comune', foglio='1', mappale='2', intestatario='NOME_RISERVATO', codice_fiscale='CF_RISERVATO',
               raw={'nota':'CONTATTO_RISERVATO'}, stato_identificativi='verificati_su_documento',
               geometry={'type':'Polygon','coordinates':[[[9,45],[9.01,45],[9.01,45.01],[9,45]]]},
               crs_geometry='EPSG:4326', fonte_geometria='https://ente.it/wfs', fonte_geometria_sha256='a'*64,
               licenza_geometria='CC BY 4.0', riferimento_catastale='COMUNE/1/2')
    con.execute('INSERT INTO documenti VALUES (?,?,?,?,?,?,?,?,?,?,?)', ('d','opera','Documento','https://ente.it/pdf','https://ente.it/atto','b'*64,'2026-11-01','elenco_ditte',1,1,'estratto'))
    con.execute('INSERT INTO righe VALUES (?,?,?,?,?)', ('r','d',1,1,json.dumps(row)))
    con.commit()
    con.close()
    before = hashlib.sha256((root / 'archivio.sqlite3').read_bytes()).hexdigest()
    destination = tmp_path / 'public.json'
    result = export_public_catalogue(root, destination)
    assert result['particelle_uniche'] == 1
    content = destination.read_text()
    for forbidden in ('NOME_RISERVATO','CONTATTO_RISERVATO','CF_RISERVATO','codice_fiscale','nota_privata','"raw"'):
        assert forbidden not in content
    assert hashlib.sha256((root / 'archivio.sqlite3').read_bytes()).hexdigest() == before
