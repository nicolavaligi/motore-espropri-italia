"""Ubicazione reale delle particelle: match esatto di comune, foglio e mappale.

Non sposta nominativi sul centro del comune o su punti casuali dell'opera.
Le risposte originali WFS sono archiviate e i buchi dei poligoni conservati.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET

import httpx
from shapely.geometry import shape
from pyproj import Transformer
TO_WGS84=Transformer.from_crs(6706,4326,always_xy=True)

from production_store import ProductionStore, utcnow

WFS='https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php'
CRS='urn:ogc:def:crs:EPSG::6706'
GML='{http://www.opengis.net/gml/3.2}'


def cadastral_reference(code,sheet,parcel,section=''):
    f=re.fullmatch(r'(\d{1,4})([A-Z]?)',str(sheet).strip().upper())
    p=re.fullmatch(r'\d+[A-Z]?',str(parcel).strip().upper())
    section=str(section or '').strip().upper()
    if not re.fullmatch(r'[A-Z]\d{3}',code) or not re.fullmatch(r'[A-Z]?',section) or not f or not p:
        raise ValueError('Identificativo catastale ambiguo o incompleto')
    zone=f'{code}{section}{int(f[1]):04}{f[2] or "0"}0' if section else f'{code}_{int(f[1]):04}{f[2] or "0"}0'
    return f'{zone}.{int(p[0]) if p[0].isdigit() else p[0]}'


def parse_features(xml):
    root=ET.fromstring(xml)
    if any('Exception' in node.tag for node in root.iter()):
        raise ValueError('Il WFS ha rifiutato la richiesta')
    results=[]
    for member in root.iter():
        local=member.tag.rsplit('}',1)[-1]
        if local not in {'CadastralParcel','CadastralZoning'}:continue
        fields={n.tag.rsplit('}',1)[-1].upper():(n.text or '').strip() for n in member if len(n)==0}
        ref=fields.get('NATIONALCADASTRALREFERENCE') or fields.get('NATIONALCADASTRALZONINGREFERENCE')
        if not ref:continue
        polygons=[]
        for poly in member.iter():
            if poly.tag.rsplit('}',1)[-1] not in {'Polygon','PolygonPatch'}:continue
            rings=[]
            for ring_type in ('exterior','interior'):
                for boundary in poly:
                    if boundary.tag.rsplit('}',1)[-1]!=ring_type:continue
                    positions=next((n for n in boundary.iter() if n.tag.rsplit('}',1)[-1]=='posList'),None)
                    if positions is None:continue
                    dimension=int(positions.get('srsDimension','2'))
                    values=[float(v) for v in (positions.text or '').split()]
                    if dimension not in {2,3} or len(values)%dimension:raise ValueError('Coordinate GML non valide')
                    ring=[list(TO_WGS84.transform(values[i+1],values[i])) for i in range(0,len(values),dimension)]
                    if any(not(math.isfinite(x) and math.isfinite(y)) or not(-180<=x<=180 and -90<=y<=90) for x,y in ring):
                        raise ValueError('Coordinate catastali non valide')
                    if ring and ring[0]!=ring[-1]:ring.append(ring[0])
                    if len(ring)>=4:rings.append(ring)
            if rings:polygons.append(rings)
        geometry=({'type':'Polygon','coordinates':polygons[0]} if len(polygons)==1 else
                  {'type':'MultiPolygon','coordinates':polygons}) if polygons else None
        if geometry and not shape(geometry).is_valid:raise ValueError(f'Geometria WFS non valida per {ref}')
        corners={n.tag.rsplit('}',1)[-1]:(n.text or '').split() for n in member.iter()
                 if n.tag.rsplit('}',1)[-1] in {'lowerCorner','upperCorner'}}
        bbox=None
        if corners.get('lowerCorner') and corners.get('upperCorner'):
            bbox=tuple(map(float,corners['lowerCorner'][:2]+corners['upperCorner'][:2]))
        results.append({'reference':ref,'geometry':geometry,'bbox':bbox})
    matched=root.get('numberMatched')
    returned=root.get('numberReturned')
    if matched and matched.isdigit() and returned and returned.isdigit() and int(matched)>int(returned):
        raise ValueError('Risposta WFS troncata: suddividere il bounding box')
    return results


def tiles(bbox,size=.004):
    s,w,n,e=bbox
    ny=max(1,math.ceil((n-s)/size));nx=max(1,math.ceil((e-w)/size))
    if nx*ny>2500:raise ValueError('Foglio troppo esteso: necessario un perimetro di ricerca più preciso')
    return [(s+(n-s)*i/ny,w+(e-w)*j/nx,s+(n-s)*(i+1)/ny,w+(e-w)*(j+1)/nx)
            for i in range(ny) for j in range(nx)]


class CadastralLocator:
    def __init__(self,store=None,client=None):
        self.store=store or ProductionStore()
        self.client=client or httpx.Client(timeout=25)
        self.memo={}
        self.zones={}
        self.cache=self.store.root/'geometrie'
        self.cache.mkdir(exist_ok=True)

    def fetch(self,feature_type,bbox):
        params={'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':feature_type,
                'srsName':CRS,'count':1000,'bbox':','.join(f'{v:.8f}' for v in bbox)+','+CRS}
        response=self.client.get(WFS,params=params)
        response.raise_for_status()
        if len(response.content)>40*1024*1024:raise ValueError('Risposta WFS oltre il limite')
        # Prima validare il GML, poi conservare risposta e URI effettivo.
        features=parse_features(response.content)
        sha=hashlib.sha256(response.content).hexdigest()
        (self.cache/f'{sha}.gml').write_bytes(response.content)
        evidence={'fonte_geometria':str(response.request.url),'fonte_geometria_sha256':sha,'geometria_acquisita_il':utcnow(),
                  'crs_sorgente':CRS,'crs_geometry':'EPSG:4326','licenza_geometria':'CC BY 4.0 — Agenzia delle Entrate'}
        return features,evidence

    def locate(self,code,sheet,parcel,center,section=''):
        reference=cadastral_reference(code,sheet,parcel,section)
        base=cadastral_reference(code,sheet,'1',section).rsplit('.',1)[0]
        cache_file=self.cache/f'{reference}.json'
        if cache_file.exists():return json.loads(cache_file.read_text())
        if base not in self.memo:
            lat,lon=center;sheet_bbox=None
            for radius in (.02,.05,.12):
                features,_=self.fetch('CP:CadastralZoning',(lat-radius,lon-radius,lat+radius,lon+radius))
                # Some municipalities publish a census section in the zoning
                # identifier (e.g. B300A091700). Use it only when unique.
                tail=base.rsplit('_',1)[-1]
                patterns=[re.escape(code)+re.escape(section)+re.escape(tail)] if section else [
                    re.escape(code)+'_'+r'[A-Z]?'+re.escape(tail),
                    re.escape(code)+r'[A-Z]'+re.escape(tail)]
                exact=[f for f in features if any(re.fullmatch(p,f['reference']) for p in patterns)]
                if len(exact)>1 and not section:
                    raise ValueError('Sezione censuaria ambigua: specificare la sezione prima di localizzare')
                exact=exact[0] if exact else None
                if exact and exact['bbox']:
                    self.zones[base]=exact['reference']
                    sheet_bbox=exact['bbox'];break
            if not sheet_bbox:
                self.memo[base]={};self.zones[base]=None
            else:
                parcels={}
                for bbox in tiles(sheet_bbox):
                    found,evidence=self.fetch('CP:CadastralParcel',bbox)
                    for feature in found:
                        if feature['geometry']:
                            value=dict(evidence,geometry=feature['geometry'],riferimento_catastale=feature['reference'],stato_geometria='localizzata_wfs')
                            parcels[feature['reference']]=value
                            if re.fullmatch(r'[A-Z]\d{3}[A-Z]?_\d{4}[A-Z0-9]{2}\.\d+[A-Z]?',feature['reference']):
                                (self.cache/f"{feature['reference']}.json").write_text(json.dumps(value))
                self.memo[base]=parcels
        zone=self.zones.get(base)
        actual_reference=reference if section or not zone else f'{zone}.{int(str(parcel)) if str(parcel).isdigit() else str(parcel).upper()}'
        return self.memo[base].get(actual_reference,{'geometry':None,'stato_geometria':'non_trovata','riferimento_catastale':actual_reference})


def normalize_name(value):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD',str(value)).casefold() if c.isalnum())


def localize_opera(slug,reference_dir,store=None,limit=None):
    store=store or ProductionStore()
    reference_dir=Path(reference_dir)
    comuni=json.loads((reference_dir/'comuni_catastali.json').read_text())['comuni']
    coordinates=json.loads((reference_dir/'comuni_coords.json').read_text())
    locator=CadastralLocator(store)
    done=0;missing=0;network_errors=0
    rows=store.rows(slug)
    try:
        for row in rows:
            if limit is not None and done+missing>=limit:break
            matches=[c for c in comuni if normalize_name(c['nome'])==normalize_name(row.get('comune'))]
            centers=[c for c in coordinates if normalize_name(c['name'])==normalize_name(row.get('comune'))]
            if len(matches)!=1 or len(centers)!=1:missing+=1;continue
            try:
                location=locator.locate(matches[0]['codice_catastale'],row['foglio'],row['mappale'],(centers[0]['lat'],centers[0]['lon']))
            except (httpx.HTTPError,OSError) as error:
                network_errors+=1
                store.log_attempt(slug,WFS,'errore_localizzazione',str(error));break
            except ValueError as error:
                store.log_attempt(slug,WFS,'localizzazione_da_verificare',str(error));missing+=1;continue
            with store.connect() as con:
                original=con.execute('SELECT payload FROM righe WHERE id=?',(row['id'],)).fetchone()
                payload=json.loads(original['payload']);payload.update(location)
                con.execute('UPDATE righe SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),row['id']))
            if location.get('geometry'):done+=1
            else:missing+=1
    finally:
        locator.client.close();store.export_catalogue()
    return {'localizzate':done,'non_localizzate':missing,'errori_rete':network_errors,'interrotto':bool(network_errors),'righe_totali':len(rows)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opera',required=True);parser.add_argument('--reference-dir',required=True);parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    print(json.dumps(localize_opera(args.opera,args.reference_dir,limit=args.limit)))
