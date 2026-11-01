"""Confini di produzione: originali, provenienza, OCR e localizzazione senza dati inventati."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from production_store import ProductionStore
from collect_public_records import OfficialCollector
from cadastral_locator import cadastral_reference, parse_features, CadastralLocator
from extract_particellare import parse_float, parse_raw_table_rows
from import_rfi_archive import normalized_page
import server


def pdf_bytes():
    # Fixture minima valida, confinata ai temporanei del test.
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << >> /Contents 4 0 R >>',
             b'<< /Length 0 >>\nstream\n\nendstream']
    out=b'%PDF-1.4\n';offsets=[]
    for n,obj in enumerate(objects,1):
        offsets.append(len(out));out+=f'{n} 0 obj\n'.encode()+obj+b'\nendobj\n'
    start=len(out);out+=b'xref\n0 5\n0000000000 65535 f \n'
    for offset in offsets:out+=f'{offset:010} 00000 n \n'.encode()
    return out+f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()


def opera():
    return {'slug':'opera-test','titolo':'Opera documentata','tipo_dati':'documentale',
            'fonte_atto_url':'https://ente.gov.it/opera','ente_promotore':'Ente'}


@pytest.fixture
def archive(tmp_path):
    store=ProductionStore(tmp_path/'archive');store.register_opera(opera());return store


def document(store,source='https://ente.gov.it/ditte.pdf'):
    return store.archive_pdf('opera-test',pdf_bytes(),source,'https://ente.gov.it/opera','Elenco ditte',kind='elenco_ditte')


def one_page():
    return [{'pagina':1,'righe':[{'comune':'Comune','foglio':'12','mappale':'34','sub':None,
                                'intestatario':'Intestazione di test','stato_estrazione':'ocr_da_verificare',
                                'raw':{'celle':['12','34']}}]}]


def test_documenti_deduplicati_per_contenuto_e_opera(archive):
    first=document(archive);second=document(archive,'https://ente.gov.it/copia.pdf')
    assert first==second
    docs=archive.documents('opera-test');assert len(docs)==1
    assert (archive.root/'documenti'/docs[0]['filename']).read_bytes()==pdf_bytes()


def test_html_non_archiviato_come_pdf(archive):
    with pytest.raises(ValueError,match='PDF'):
        archive.archive_pdf('opera-test',b'<html>Access denied</html>','https://ente.gov.it/file.pdf','https://ente.gov.it/opera','Documento')
    assert archive.status()['documenti']==0


def test_estrazione_collegata_a_originale_pagina_checksum(archive):
    doc=document(archive);archive.save_extraction(doc,one_page(),1,'test')
    row=archive.rows('opera-test')[0]
    assert row['fonte_pagina']==1 and row['fonte_sha256']==archive.document(doc)['sha256']
    assert row['documento_url']==f'/api/documenti/{doc}/file#page=1'
    assert not row.get('geometry')
    assert row['stato_geometria']=='non_localizzata'
    assert row['raw']['celle']==['12','34']


def test_riestrazione_idempotente_e_rollback_su_riga_invalida(archive):
    doc=document(archive)
    for _ in range(2):archive.save_extraction(doc,one_page(),1,'test')
    assert len(archive.rows('opera-test'))==1
    with pytest.raises(ValueError):archive.save_extraction(doc,[{'pagina':1,'righe':[{'foglio':'12'}]}],1,'rotto')
    assert len(archive.rows('opera-test'))==1


def test_nessun_punto_catastale_o_importo_generato(archive):
    doc=document(archive);archive.save_extraction(doc,one_page(),1,'test')
    op=archive.catalogue()[0]
    assert op['ditte'][0]['indennita'] is None
    assert not op['ditte'][0].get('geometry')
    assert op['geo'] is None and op['completezza_catastale']=='non_certificata'
    assert op['stato_opera']=='DOCUMENTI_ARCHIVIATI'


def test_coordinate_senza_fonte_rifiutate(archive):
    with pytest.raises(ValueError,match='Coordinate'):
        archive.register_opera(dict(opera(),coordinate={'lat':45,'lng':9}))


def test_ocr_conserva_originale_ma_non_promuove_superfici(archive):
    page=normalized_page({'pagina':1,'comune':'Comune','ditta':'NOME ORIGINALE IDENTIFICAZIONE CATASTALE',
                          'righe':[{'foglio':'12','mappale':'34','mq_esproprio_sede':'999'},
                                   {'foglio':'ambiguo','mappale':'34'}]})
    assert len(page['righe'])==1
    row=page['righe'][0]
    assert row['stato_estrazione']=='ocr_da_verificare' and row['superfici_mq']=={}
    assert row['raw']['celle']['mq_esproprio_sede']=='999'
    assert row['geometry'] is None


def test_parser_colonna_cf_separata_e_decimali_italiani():
    rows=parse_raw_table_rows([['Foglio','Mappale','Intestatario','Codice fiscale','Quota','Sup. Esproprio'],
                              ['12','34','ROSSI MARIO','RSSMRA80A01H501Z','1/2','12,50']])
    assert rows[0]['codice_fiscale']=='RSSMRA80A01H501Z'
    assert rows[0]['quota']=='1/2'
    assert parse_float('12.50')==12.5
    assert parse_float('1.250')==1250


def test_collector_archivia_allegato_e_non_segue_navigazione_generica(archive):
    visited=[]
    def transport(request):
        visited.append(request.url.path)
        if request.url.path=='/opera':
            return httpx.Response(200,headers={'Content-Type':'text/html'},text='<html><a href="/ditte.pdf">Elenco ditte</a><a href="/espropri">Tutti gli espropri</a></html>')
        return httpx.Response(200,headers={'Content-Type':'application/pdf'},content=pdf_bytes())
    collector=OfficialCollector(archive,httpx.Client(transport=httpx.MockTransport(transport)),validate_dns=False)
    result=collector.run_source({'opera':opera(),'pages':['https://ente.gov.it/opera'],'allowed_hosts':['ente.gov.it']})
    assert result['documenti_archiviati']==1 and result['errori']==0
    assert visited==['/opera','/ditte.pdf']
    assert archive.documents('opera-test')[0]['totale_pagine']==1
    with archive.connect() as con:
        assert con.execute('select stato from pagine').fetchone()[0]=='ocr_necessario'


def test_download_fallito_distinto_da_elenco_vuoto(archive):
    def transport(request):raise httpx.ConnectError('Rete non disponibile',request=request)
    collector=OfficialCollector(archive,httpx.Client(transport=httpx.MockTransport(transport)),validate_dns=False)
    result=collector.run_source({'opera':opera(),'pages':['https://ente.gov.it/opera'],'allowed_hosts':['ente.gov.it']})
    assert result['errori']==1 and result['stato']=='parziale'
    assert archive.status()['ultime_acquisizioni'][0]['stato']=='errore_download'


def test_redirect_fuori_dagli_host_non_seguito(archive):
    collector=OfficialCollector(archive,httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(302,headers={'location':'http://127.0.0.1/private'}))),validate_dns=False)
    with pytest.raises(ValueError,match='Host'):
        collector.fetch('https://ente.gov.it/file',{'ente.gov.it'})


def test_limite_download_streaming(archive):
    collector=OfficialCollector(archive,httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=b'123456'))),max_bytes=3,validate_dns=False)
    with pytest.raises(ValueError,match='dimensionale'):collector.fetch('https://ente.gov.it/file',{'ente.gov.it'})


def gml(exterior='45 9 45 10 46 10 46 9 45 9',interior=''):
    hole=f'<gml:interior><gml:LinearRing><gml:posList>{interior}</gml:posList></gml:LinearRing></gml:interior>' if interior else ''
    return f'''<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:cp="urn:test" numberMatched="1" numberReturned="1"><wfs:member><cp:CadastralParcel><cp:nationalCadastralReference>A001_001200.34</cp:nationalCadastralReference><cp:geometry><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{exterior}</gml:posList></gml:LinearRing></gml:exterior>{hole}</gml:Polygon></cp:geometry></cp:CadastralParcel></wfs:member></wfs:FeatureCollection>'''


def test_gml_inverte_assi_e_preserva_buchi():
    features=parse_features(gml(interior='45.2 9.2 45.2 9.4 45.4 9.4 45.4 9.2 45.2 9.2'))
    assert features[0]['reference']=='A001_001200.34'
    polygon=features[0]['geometry'];assert len(polygon['coordinates'])==2
    assert polygon['coordinates'][0][0]==pytest.approx([9,45],abs=1e-5)


def test_risposta_wfs_troncata_o_eccezione_non_equivale_ad_assenza():
    with pytest.raises(ValueError,match='troncata'):parse_features(gml().replace('numberMatched="1"','numberMatched="2"'))
    with pytest.raises(ValueError,match='rifiutato'):parse_features('<ExceptionReport><Exception/></ExceptionReport>')


def test_identificativi_ambigui_non_geocodificati():
    assert cadastral_reference('A001','12','34')=='A001_001200.34'
    assert cadastral_reference('A001','12B','34')=='A001_0012B0.34'
    with pytest.raises(ValueError):cadastral_reference('A001','12/13','34')
    with pytest.raises(ValueError):cadastral_reference('A001','12','34,35')


def test_verifica_tracciata_e_preservata_da_riestrazione(archive):
    doc=document(archive);archive.save_extraction(doc,one_page(),1,'test')
    row=archive.rows('opera-test')[0]
    archive.review_row(row['id'],{'intestatario':'Nome verificato dal documento'},'Operatore locale')
    archive.save_extraction(doc,one_page(),1,'nuovo-parser')
    reviewed=archive.rows('opera-test')[0]
    assert reviewed['intestatario']=='Nome verificato dal documento'
    assert reviewed['stato_estrazione']=='verificata_su_documento'
    with archive.connect() as con:assert con.execute('select count(*) from revisioni').fetchone()[0]==1


def test_correzione_riferimenti_invalida_geometria_precedente(archive):
    doc=document(archive);archive.save_extraction(doc,one_page(),1,'test')
    row=archive.rows('opera-test')[0]
    with archive.connect() as con:
        payload=json.loads(con.execute('select payload from righe where id=?',(row['id'],)).fetchone()[0])
        payload.update(geometry={'type':'Polygon','coordinates':[]},fonte_geometria='https://ente.gov.it/geo')
        con.execute('update righe set payload=? where id=?',(json.dumps(payload),row['id']))
    archive.review_row(row['id'],{'mappale':'35'},'Operatore locale')
    after=archive.rows('opera-test')[0]
    assert not after.get('geometry') and after['stato_geometria']=='non_localizzata'


def test_api_originale_e_righe_corrispondono_all_archivio(archive,monkeypatch):
    doc=document(archive);archive.save_extraction(doc,one_page(),1,'test');archive.export_catalogue()
    monkeypatch.setattr(server,'ProductionStore',lambda:archive)
    monkeypatch.setattr(server,'DATA_PATH',archive.root/'opere.json')
    client=TestClient(server.app)
    assert client.get(f'/api/documenti/{doc}/file').content==pdf_bytes()
    assert client.get('/api/documenti/mancante/file').status_code==404
    rows=client.get('/api/opere/opera-test/particelle').json()
    assert rows[0]['documento_id']==doc
    geo=client.get('/api/opere/opera-test/particelle.geojson').json()
    assert geo['features']==[] and geo['righe_senza_geometria']==1
    assert client.get('/api/archivio/stato').json()['documenti']==1


def test_dataset_statici_non_reintroducono_dati_dimostrativi():
    root=Path(__file__).resolve().parents[1]
    assert json.loads((root/'data/opere.json').read_text())==[]
    assert json.loads((root/'opere.json').read_text())==[]
    assert 'random' not in (root/'init_data.py').read_text()
    assert 'generateSampleParticellare' not in (root/'quadro_interferenze.html').read_text()


def test_revisione_documento_con_stesso_url_non_raddoppia_ditte_attive(archive):
    first=document(archive);archive.save_extraction(first,one_page(),1,'test')
    second=archive.archive_pdf('opera-test',pdf_bytes()+b'\n% revisione\n','https://ente.gov.it/ditte.pdf','https://ente.gov.it/opera','Nuova revisione',kind='elenco_ditte')
    archive.save_extraction(second,one_page(),1,'test')
    assert len(archive.documents('opera-test'))==2
    rows=archive.rows('opera-test');assert len(rows)==1 and rows[0]['documento_id']==second
    assert archive.document(first)['attivo']==0


def test_superficie_non_pubblicata_distinta_da_zero_esplicito():
    rows=parse_raw_table_rows([['Foglio','Mappale','Intestatario','Sup. Esproprio mq'],['12','34','Intestazione','0']])
    assert rows[0]['superfici_mq']['esproprio']==0
    assert rows[0]['superfici_mq']['totale'] is None
    assert rows[0]['superfici_mq']['asservimento'] is None
