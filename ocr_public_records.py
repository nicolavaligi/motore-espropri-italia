"""OCR riprendibile degli elenchi RFI: un risultato per pagina e revisione PDF.

python ocr_public_records.py --opera SLUG --workers 4
I risultati restano trascrizioni OCR da verificare, collegati agli originali.
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from pathlib import Path
import re

import pdfplumber
from import_rfi_archive import normalized_page
from ocr_rfi import ELENCHI, leggi_pagina
from production_store import ProductionStore


def extract_document(store, doc_id, workers=4):
    doc=store.document(doc_id)
    match=re.search(r'/File/Documento/(\d+)',doc['fonte_url'])
    if not match or match[1] not in ELENCHI:
        raise ValueError('Layout OCR non configurato per questo documento: originale archiviato, necessaria lettura dedicata')
    code=match[1];path=store.root/'documenti'/doc['filename']
    cache=store.root/'ocr'/doc['sha256'];cache.mkdir(parents=True,exist_ok=True)
    with pdfplumber.open(path) as pdf:total=len(pdf.pages)
    def page(number):
        output=cache/f'{number:04}.json'
        if output.exists():value=json.loads(output.read_text())
        else:
            try:value=leggi_pagina(path,number)
            except Exception as error:value={'pagina':number,'comune':ELENCHI[code],'righe':[],'errore':str(error)}
            value['source_sha256']=doc['sha256'];value['comune']=ELENCHI[code]
            output.write_text(json.dumps(value,ensure_ascii=False,indent=2))
        if value.get('source_sha256')!=doc['sha256']:raise ValueError('Cache OCR di un’altra revisione')
        return normalized_page(value)
    with ThreadPoolExecutor(max_workers=max(1,min(workers,8))) as pool:
        pages=list(pool.map(page,range(1,total+1)))
    store.save_extraction(doc_id,pages,total,'rfi-griglia-ocr-v1')
    return {'documento':doc_id,'pagine':total,'righe_ocr':sum(len(p['righe']) for p in pages)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opera',required=True);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();store=ProductionStore()
    for doc in store.documents(args.opera):
        if doc['tipo']!='elenco_ditte':continue
        try:result=extract_document(store,doc['id'],args.workers)
        except Exception as error:
            store.log_attempt(args.opera,doc['fonte_url'],'ocr_da_configurare',str(error))
            result={'documento':doc['id'],'errore':str(error)}
        print(json.dumps(result,ensure_ascii=False),flush=True)
    store.export_catalogue()


if __name__=='__main__':main()
