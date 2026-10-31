"""
Motore Espropri Italia — Backend REST API
Proprietà intellettuale: Nicola Valigi (Houdinick)
Ambiente: Antigravity (AGY)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from stima_delta import router as stima_router

app = FastAPI(
    title="Motore Espropri Italia API",
    description="Feed REST e intelligence per piani particellari e procedure D.P.R. 327/2001",
    version="1.2.0"
)

# CORS Middleware aperto per chiamate locali e dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stima_router)
from stima_delta import router_no_prefix as stima_no_prefix_router
app.include_router(stima_no_prefix_router)

DATA_PATH = Path(__file__).parent / "data" / "opere.json"
STATIC_INDEX = Path(__file__).parent / "index.html"
QUADRO_INTERFERENZE_HTML = Path(__file__).parent / "quadro_interferenze.html"
DOSSIER_PATH = Path(__file__).parent / "DOSSIER_ARCHITETTURALE.md"


class StimaPeriziaRequest(BaseModel):
    tipologia: str = Field("agricola", description="'edificabile' oppure 'agricola'")
    valore_venale_unitario: float = Field(..., gt=0, description="Valore venale a metro quadro (€/mq)")
    superficie_mq: float = Field(..., gt=0, description="Superficie catastale espropriata (mq)")
    soprassuoli_eur: float = Field(0.0, ge=0, description="Valore soprassuoli/piantumazioni/fabbricati rurali (€)")
    coltivatore_diretto: bool = Field(False, description="Proprietario coltivatore diretto o IAP")
    cessione_volontaria: bool = Field(True, description="Accettazione cessione volontaria ex art. 45")
    vam_unitario: Optional[float] = Field(None, ge=0, description="Valore Agricolo Medio di zona (€/mq) ex art. 40 c. 4")


class StimaPeriziaResponse(BaseModel):
    indennita_base_eur: float
    indennita_finale_eur: float
    maggiorazione_eur: float
    maggiorazione_descrizione: str
    normativa_riferimento: str
    dettagli_calcolo: Dict[str, Any]


def load_opere() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_opere(opere: List[Dict[str, Any]]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(opere, f, ensure_ascii=False, indent=2)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if STATIC_INDEX.exists():
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(STATIC_INDEX, headers=headers)
    return HTMLResponse("<h1>Motore Espropri Italia API attivo</h1><p>Visita <a href='/api/opere'>/api/opere</a></p>")


@app.get("/quadro-interferenze", response_class=HTMLResponse)
@app.get("/interferenze", response_class=HTMLResponse)
@app.get("/quadro_interferenze.html", response_class=HTMLResponse)
async def serve_quadro_interferenze():
    if QUADRO_INTERFERENZE_HTML.exists():
        return FileResponse(QUADRO_INTERFERENZE_HTML)
    return HTMLResponse("<h1>Quadro interferenze in preparazione</h1>")


# Endpoint WFS regionale (esempio Lombardia / Geoportale Nazionale)
WFS_URL = "https://www.geoportale.regione.lombardia.it/geoserver/wfs"


class TracciatoInterferenzeRequest(BaseModel):
    tracciato_geojson: Dict[str, Any]
    buffer_meters: float = 25.0


@app.post("/api/catasto/interferenze")
@app.post("/catasto/interferenze")
def get_particelle_sotto_tracciato(req: TracciatoInterferenzeRequest):
    """
    Calcola l'ingombro metrico bufferizzato del tracciato di progetto ed effettua la query WFS
    o intersezione spaziale per isolare le particelle catastali impattate.
    """
    try:
        import geopandas as gpd
        import requests
        from shapely.geometry import shape

        tracciato_geojson = req.tracciato_geojson
        buffer_meters = req.buffer_meters

        # 1. Parsing tracciato in GeoDataFrame
        if "features" in tracciato_geojson:
            gdf_tracciato = gpd.GeoDataFrame.from_features(tracciato_geojson["features"], crs="EPSG:4326")
        elif "geometry" in tracciato_geojson:
            gdf_tracciato = gpd.GeoDataFrame.from_features([tracciato_geojson], crs="EPSG:4326")
        else:
            geom = shape(tracciato_geojson)
            gdf_tracciato = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")

        gdf_metric = gdf_tracciato.to_crs(epsg=32632)

        # 2. Calcolo del buffer e del Bounding Box
        buffer_geom = gdf_metric.geometry.buffer(buffer_meters).unary_union

        # Conversione bbox per la query WFS
        gdf_bbox = gpd.GeoDataFrame(geometry=[buffer_geom.envelope], crs="EPSG:32632").to_crs(epsg=4326)
        minx, miny, maxx, maxy = gdf_bbox.total_bounds
        bbox_str = f"{miny},{minx},{maxy},{maxx},urn:ogc:def:crs:EPSG:4326"

        # 3. Richiesta WFS limitata al bounding box dell'opera
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "ct_particelle",
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
            "bbox": bbox_str
        }

        try:
            resp = requests.get(WFS_URL, params=params, timeout=10)
            if resp.status_code == 200:
                gdf_catasto = gpd.read_file(resp.text)
            else:
                gdf_catasto = gpd.GeoDataFrame()
        except Exception:
            gdf_catasto = gpd.GeoDataFrame()

        # 4. Clip spaziale ed estrazione particelle interferite
        if not gdf_catasto.empty:
            gdf_catasto_metric = gdf_catasto.to_crs(epsg=32632)
            intersecate = gdf_catasto_metric[gdf_catasto_metric.intersects(buffer_geom)].copy()
            intersecate["sup_totale_mq"] = intersecate.geometry.area
            intersecate["sup_interferita_mq"] = intersecate.geometry.intersection(buffer_geom).area
            return intersecate.to_crs(epsg=4326).__geo_interface__
        else:
            # Fallback resiliente con poligono bufferizzato georiferito
            gdf_buffer_res = gpd.GeoDataFrame(geometry=[buffer_geom], crs="EPSG:32632").to_crs(epsg=4326)
            return {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": gdf_buffer_res.geometry.iloc[0].__geo_interface__,
                        "properties": {
                            "buffer_meters": buffer_meters,
                            "bbox": [minx, miny, maxx, maxy],
                            "info": "Fascia buffer generata con successo"
                        }
                    }
                ]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Motore Espropri Italia",
        "owner": "Nicola Valigi (Houdinick)",
        "framework": "D.P.R. 327/2001 e s.m.i."
    }


@app.get("/debug-env")
async def debug_env(request: Request):
    return {
        "path": request.url.path,
        "raw_path": request.scope.get("raw_path", b"").decode("utf-8", "ignore"),
        "headers": dict(request.headers)
    }

@app.get("/data/opere.json")
@app.get("/opere.json")
async def serve_opere_json():
    return load_opere()

@app.get("/specifiche-dossier")
@app.get("/api/specifiche-dossier")
async def get_specifiche_dossier():
    return {
        "titolo": "Motore Espropri Italia — Dossier Architetturale & Specifiche di Sistema",
        "quadro_giuridico": "D.P.R. 8 giugno 2001, n. 327 e s.m.i.",
        "autore": "Nicola Valigi (Houdinick)",
        "scala_maturita": [
            {"step": 1, "fase": "VINCOLO_PREORDINATO", "descrizione": "Vincolo preordinato all'esproprio (artt. 9-10)"},
            {"step": 2, "fase": "AVVISO_AVVIO_PROCEDIMENTO", "descrizione": "Avviso avvio procedimento e comunicazione ex art. 11 c. 2"},
            {"step": 3, "fase": "DICHIARAZIONE_PU", "descrizione": "Dichiarazione di Pubblica Utilità (art. 12)"},
            {"step": 4, "fase": "DEPOSITO_PIANO_PARTICELLARE", "descrizione": "Deposito piano particellare grafico e ditte (art. 16)"},
            {"step": 5, "fase": "DETERMINA_INDENNITA_PROVVISORIA", "descrizione": "Determina indennità provvisoria (art. 20)"},
            {"step": 6, "fase": "CONCORDAMENTO_ACCORDO_CESSIONE", "descrizione": "Accordo di cessione volontaria o deposito CDP (artt. 21, 26)"},
            {"step": 7, "fase": "DECRETO_ESPROPRIO", "descrizione": "Decreto di esproprio e immissione in possesso (artt. 23-24)"}
        ],
        "dossier_disponibile": DOSSIER_PATH.exists()
    }


@app.post("/api/stima-perizia", response_model=StimaPeriziaResponse)
async def calcola_stima_perizia(req: StimaPeriziaRequest):
    """
    Motore di stima peritale D.P.R. 327/2001:
    - Edificabili: art. 37 + Corte Cost. 348/2007 (+10% cessione volontaria art. 45 c. 2 lett. a)
    - Agricole: art. 40 + Corte Cost. 181/2011 (Valore venale effettivo + soprassuoli)
    - Coltivatore Diretto / IAP: indennità aggiuntiva VAM (art. 40 c. 4)
    - Cessione Volontaria Agricola: 1.5x non coltivatore, 3.0x coltivatore diretto (art. 45 c. 2 lett. c)
    """
    sup = req.superficie_mq
    v_unit = req.valore_venale_unitario
    soprassuoli = req.soprassuoli_eur
    v_base = sup * v_unit

    if req.tipologia.lower() == "edificabile":
        indennita_base = v_base
        normativa = "Art. 37 D.P.R. 327/2001 (Corte Cost. sent. 348/2007)"
        
        if req.cessione_volontaria:
            maggiorazione = indennita_base * 0.10
            indennita_finale = indennita_base + maggiorazione
            desc = "+10% Cessione Volontaria (art. 45 c. 2 lett. a D.P.R. 327/2001)"
        else:
            maggiorazione = 0.0
            indennita_finale = indennita_base
            desc = "Valore Venale Puro (art. 37 D.P.R. 327/2001)"

        dettagli = {
            "tipologia": "Edificabile",
            "superficie_mq": sup,
            "valore_unitario_mq": v_unit,
            "valore_venale_totale": v_base,
            "soprassuoli": 0.0,
            "maggiorazione_cessione_percentuale": 10 if req.cessione_volontaria else 0
        }

    else:
        # Agricola / Non edificabile
        normativa = "Art. 40 D.P.R. 327/2001 (Corte Cost. sent. 181/2011)"
        indennita_base = v_base + soprassuoli

        if req.cessione_volontaria:
            if req.coltivatore_diretto:
                # Triplo del valore agricolo effettivo (art. 45 c. 2 lett. c)
                indennita_finale = (v_base * 3.0) + soprassuoli
                maggiorazione = indennita_finale - indennita_base
                desc = "Triplo Valore Agricolo per Coltivatore Diretto/IAP (art. 45 c. 2 lett. c D.P.R. 327/2001)"
            else:
                # 1.5x valore agricolo effettivo (art. 45 c. 2 lett. c)
                indennita_finale = (v_base * 1.5) + soprassuoli
                maggiorazione = indennita_finale - indennita_base
                desc = "+50% per Cessione Volontaria Non Coltivatore (art. 45 c. 2 lett. c D.P.R. 327/2001)"
        else:
            # Senza cessione volontaria: se coltivatore diretto, spetta VAM aggiuntivo art. 40 c. 4
            if req.coltivatore_diretto:
                vam_val = (req.vam_unitario or v_unit) * sup
                indennita_finale = indennita_base + vam_val
                maggiorazione = vam_val
                desc = "Indennità base + Indennità Aggiuntiva VAM Coltivatore Diretto (art. 40 c. 4 D.P.R. 327/2001)"
            else:
                indennita_finale = indennita_base
                maggiorazione = 0.0
                desc = "Valore Agricolo Effettivo + Soprassuoli (art. 40 D.P.R. 327/2001)"

        dettagli = {
            "tipologia": "Agricola",
            "superficie_mq": sup,
            "valore_unitario_mq": v_unit,
            "valore_agricolo_terreno": v_base,
            "soprassuoli": soprassuoli,
            "coltivatore_diretto": req.coltivatore_diretto,
            "cessione_volontaria": req.cessione_volontaria
        }

    return StimaPeriziaResponse(
        indennita_base_eur=round(indennita_base, 2),
        indennita_finale_eur=round(indennita_finale, 2),
        maggiorazione_eur=round(maggiorazione, 2),
        maggiorazione_descrizione=desc,
        normativa_riferimento=normativa,
        dettagli_calcolo=dettagli
    )


@app.get("/opere")
@app.get("/api/opere")
async def get_opere(
    regione: Optional[str] = Query(None, description="Filtra per regione (es. Lombardia, Veneto)"),
    stato: Optional[str] = Query(None, description="Filtra per stato_opera (es. AVANZATA_SENZA_ELENCO)"),
    q: Optional[str] = Query(None, description="Ricerca testuale su titolo, cup o ente")
):
    opere = load_opere()

    if regione and regione != "ALL":
        opere = [o for o in opere if o.get("regione", "").lower() == regione.lower()]

    if stato:
        opere = [o for o in opere if o.get("stato_opera") == stato]

    if q:
        query = q.lower().strip()
        opere = [
            o for o in opere
            if query in o.get("titolo", "").lower()
            or query in (o.get("cup") or "").lower()
            or query in o.get("ente", "").lower()
            or query in o.get("comune", "").lower()
        ]

    return opere


@app.get("/opere/{slug}")
@app.get("/api/opere/{slug}")
async def get_opera_by_slug(slug: str):
    opere = load_opere()
    for o in opere:
        if o.get("slug") == slug:
            return o
    raise HTTPException(status_code=404, detail="Opera non trovata")


@app.post("/opere")
@app.post("/api/opere")
async def create_or_update_opera(opera_data: Dict[str, Any]):
    opere = load_opere()
    slug = opera_data.get("slug") or f"OPERA-{Date.now()}"
    opera_data["slug"] = slug

    # Aggiorna se esistente o inserisci in cima
    updated = False
    for i, o in enumerate(opere):
        if o.get("slug") == slug:
            opere[i] = opera_data
            updated = True
            break
    if not updated:
        opere.insert(0, opera_data)

    save_opere(opere)
    return {"status": "success", "slug": slug, "total": len(opere)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
