"""Raccolta ripetibile da pagine ufficiali specifiche dell'opera.

python collect_public_records.py --manifest config/fonti_pubbliche.json
Nessuna email, nessuna pubblicazione e nessun dato inventato.
"""
from __future__ import annotations

import argparse
from collections import deque
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx
import pdfplumber

from extract_particellare import extract_piano_particellare
from production_store import ProductionStore, public_url

RELEVANT = re.compile(r'particell|elenco.{0,20}ditt|espropri|allegat|elaborat|documentaz|download|scarica', re.I)


class OfficialCollector:
    def __init__(self, store=None, client=None, max_bytes=80*1024*1024, validate_dns=True):
        self.store = store or ProductionStore()
        self.client = client or httpx.Client(timeout=httpx.Timeout(35, connect=10), follow_redirects=False,
                                             headers={'User-Agent':'MotoreEspropri/2.0 archivio documentale'})
        self.max_bytes = max_bytes
        self.validate_dns = validate_dns

    def check_url(self, url, hosts):
        public_url(url)
        parts = urlsplit(url)
        host = parts.hostname.lower()
        if parts.port not in {None, 80, 443} or host not in hosts:
            raise ValueError(f'Host non autorizzato dal manifest: {host}')
        if self.validate_dns:
            addresses = socket.getaddrinfo(host, parts.port or (443 if parts.scheme=='https' else 80))
            if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError('Indirizzo di rete non pubblico')

    def fetch(self, url, hosts):
        """Redirect verificati singolarmente, limiti dimensione e tentativi finiti."""
        current = url
        for _ in range(6):
            self.check_url(current, hosts)
            for attempt in range(3):
                with self.client.stream('GET', current) as response:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt<2:
                        time.sleep(min(2**attempt, 4))
                        continue
                    if response.status_code in {301, 302, 303, 307, 308}:
                        current = urljoin(current, response.headers['location'])
                        break
                    response.raise_for_status()
                    length = response.headers.get('content-length')
                    if length and int(length)>self.max_bytes:
                        raise ValueError('Documento oltre il limite dimensionale configurato')
                    chunks=[]; total=0
                    for chunk in response.iter_bytes():
                        total+=len(chunk)
                        if total>self.max_bytes:raise ValueError('Documento oltre il limite dimensionale configurato')
                        chunks.append(chunk)
                    return b''.join(chunks), response.headers.get('content-type',''), current
            else:
                raise RuntimeError('Tentativi HTTP esauriti')
        raise ValueError('Troppi redirect')

    def extract(self, doc_id):
        doc = self.store.document(doc_id)
        path = self.store.root / 'documenti' / doc['filename']
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            text_lengths=[len((p.extract_text() or '').strip()) for p in pdf.pages]
        if text_lengths and max(text_lengths)<30:
            from ocr_rfi import ELENCHI
            code=re.search(r'/File/Documento/(\d+)',doc['fonte_url'])
            if code and code[1] in ELENCHI:
                from ocr_public_records import extract_document
                return extract_document(self.store,doc_id)['righe_ocr']
        rows=extract_piano_particellare(path)
        pages=[]
        for number in range(1,total+1):
            found=[dict(r,stato_estrazione='estratta_da_testo') for r in rows if r['metadati']['fonte_pagina']==number]
            pages.append({'pagina':number,'righe':found,
                          'stato':'estratta_da_testo' if found else ('ocr_necessario' if text_lengths[number-1]<30 else 'nessuna_riga_riconosciuta'),
                          'nota':None if found else 'Nessuna riga catastale riconosciuta; non equivale ad assenza di ditte'})
        self.store.save_extraction(doc_id,pages,total,'pdfplumber-v2')
        return len(rows)

    def run_source(self, source):
        op=source['opera'];self.store.register_opera(op)
        slug=op['slug']
        hosts=set(source['allowed_hosts'])
        queue=deque((url,0,'Pagina fonte') for url in source['pages'])
        seen=set(); docs=0; visited=0; errors=0; limited=False
        limits=source.get('limits',{})
        max_pages=limits.get('pages',30);max_docs=limits.get('documents',200)
        max_depth=limits.get('depth',2)
        while queue:
            url,depth,label=queue.popleft()
            if url in seen:continue
            seen.add(url)
            if visited>=max_pages or docs>=max_docs:
                limited=True
                self.store.log_attempt(slug,url,'limite_raggiunto','Copertura parziale: limiti scansione raggiunti')
                break
            try:
                body,mime,final_url=self.fetch(url,hosts)
                visited+=1
                if body.lstrip().startswith(b'%PDF-'):
                    doc_id=self.store.archive_pdf(slug,body,final_url,source['pages'][0],label,kind='elenco_ditte' if re.search(r'elenco.*ditt',label,re.I) else 'documento')
                    # Gli originali si conservano anche quando il parser non riconosce le righe.
                    try:self.extract(doc_id)
                    except Exception as e:
                        errors+=1
                        self.store.log_attempt(slug,final_url,'errore_estrazione',str(e))
                    docs+=1;self.store.log_attempt(slug,final_url,'archiviato',doc_id)
                    continue
                if 'html' not in mime and not body.lstrip().lower().startswith((b'<!doctype',b'<html')):
                    self.store.log_attempt(slug,final_url,'formato_non_supportato',mime)
                    continue
                if depth>=max_depth:
                    self.store.log_attempt(slug,final_url,'limite_profondita','Eventuali allegati di pagine successive non visitati')
                    continue
                soup=BeautifulSoup(body,'html.parser')
                for a in soup.select('a[href]'):
                    href=urljoin(final_url,a['href']).split('#')[0]
                    text=a.get_text(' ',strip=True)
                    if urlsplit(href).hostname not in hosts:continue
                    is_pdf=bool(re.search(r'\.pdf(?:\?|$)|/File/Documento/\d+|/docalbo/',href,re.I))
                    follow_patterns=source.get('follow_pages',[])
                    is_page=any(re.search(pattern,href) for pattern in follow_patterns)
                    if not is_pdf and not is_page:continue
                    if source.get('discovery_only'):
                        self.store.log_attempt(slug,href,'abbinamento_da_verificare',text)
                        continue
                    if RELEVANT.search(text+' '+href) or is_pdf and source.get('all_pdf_links',False) or is_page:
                        queue.append((href,depth+1,text or href.rsplit('/',1)[-1]))
                self.store.log_attempt(slug,final_url,'pagina_consultata',f'{len(queue)} collegamenti in coda')
            except Exception as e:
                errors+=1
                self.store.log_attempt(slug,url,'errore_download',str(e))
        self.store.export_catalogue()
        return {'opera':slug,'pagine_consultate':visited,'documenti_archiviati':docs,'errori':errors,'limiti_raggiunti':limited,
                'stato':'parziale' if errors or limited else 'scansione_eseguita_completezza_non_certificata'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',default='config/fonti_pubbliche.json')
    parser.add_argument('--opera')
    args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_text())
    collector=OfficialCollector()
    failures=0
    try:
        for source in manifest['sources']:
            if args.opera and source['opera']['slug']!=args.opera:continue
            result=collector.run_source(source)
            failures+=result['errori']
            print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:
        collector.client.close()
    if failures:raise SystemExit(2)


if __name__=='__main__':main()
