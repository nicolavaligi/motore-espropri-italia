"""Overlay riproducibile tra poligoni documentati, senza geometrie sintetiche."""
from datetime import datetime, timezone
import math

import geopandas as gpd
from shapely.geometry import shape

from production_store import public_url


def polygon_frame(data):
    if not isinstance(data, dict) or data.get('crs'):
        raise ValueError('Richiesto GeoJSON RFC 7946 WGS84, senza CRS alternativo')
    items = data.get('features') if data.get('type') == 'FeatureCollection' else [data]
    if not isinstance(items, list) or not items or len(items) > 10000:
        raise ValueError('Richieste da 1 a 10000 geometrie poligonali')
    records = []
    for item in items:
        if not isinstance(item, dict) or item.get('crs'):
            raise ValueError('Feature non valida o CRS alternativo')
        geometry = item.get('geometry') if item.get('type') == 'Feature' else item
        if not isinstance(geometry, dict) or geometry.get('type') not in {'Polygon', 'MultiPolygon'}:
            raise ValueError('Servono poligoni reali: un asse o un punto non definisce una superficie')
        geom = shape(geometry)
        if geom.is_empty or not geom.is_valid:
            raise ValueError('Geometria vuota o non valida: correggere la sorgente conservando l’originale')
        from shapely import get_coordinates
        if not all(math.isfinite(float(v)) for point in get_coordinates(geom, include_z=geom.has_z) for v in point):
            raise ValueError('Coordinate non finite')
        x1, y1, x2, y2 = geom.bounds
        if not (-180 <= x1 <= x2 <= 180 and -80 <= y1 <= y2 <= 84):
            raise ValueError('Coordinate fuori dai limiti geografici UTM')
        records.append(dict(item.get('properties') or {}, geometry=geom))
    return gpd.GeoDataFrame(records, geometry='geometry', crs=4326)


def overlay_documentato(ingombro, particelle, fonte_ingombro, fonte_catasto):
    public_url(fonte_ingombro)
    public_url(fonte_catasto)
    project, parcels = polygon_frame(ingombro), polygon_frame(particelle)
    bounds = project.total_bounds
    # Una sola UTM locale: estensioni maggiori richiedono un'analisi dedicata.
    if bounds[2] - bounds[0] > 6 or bounds[3] - bounds[1] > 6:
        raise ValueError('Ingombro troppo esteso per una singola proiezione UTM locale')
    crs = project.estimate_utm_crs()
    footprint = project.to_crs(crs).geometry.union_all()
    metric = parcels.to_crs(crs)
    # L'indice spaziale limita le intersezioni costose ai soli candidati.
    candidates = metric.iloc[metric.sindex.query(footprint, predicate='intersects')].copy()
    candidates['sup_totale_mq'] = candidates.geometry.area
    candidates['sup_interferita_mq'] = candidates.geometry.intersection(footprint).area
    candidates = candidates[candidates['sup_interferita_mq'] > 0]
    candidates['dati_catastali_verificati'] = False
    candidates['fonte_catasto_url'] = fonte_catasto
    candidates['fonte_ingombro_url'] = fonte_ingombro
    result = candidates.to_crs(4326).__geo_interface__
    result['metadata'] = {
        'tipo_dati': 'elaborato_da_geometrie_fornite', 'crs_output': 'EPSG:4326',
        'crs_calcolo': crs.to_string(), 'unita_superficie': 'm²',
        'predicato': 'intersects con area positiva; esclusi contatti di bordo',
        'particelle_input': len(parcels), 'particelle_interferite': len(candidates),
        'fonte_ingombro_url': fonte_ingombro, 'fonte_catasto_url': fonte_catasto,
        'elaborato_il': datetime.now(timezone.utc).isoformat(),
        'completezza': 'non_certificata',
        'nota': 'Superfici calcolate sulle geometrie fornite. Fonti dichiarate dall’utente; titolarità e confini legali non verificati. Non sommare righe catastali senza controllare duplicati e sovrapposizioni.'
    }
    return result
