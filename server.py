"""
Motore Espropri Italia — Backend REST API
Proprietà intellettuale: Nicola Valigi (Houdinick)
Ambiente: Antigravity (AGY)
"""

import json
import os
import tempfile
from copy import deepcopy
from threading import RLock
from typing import Literal
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from stima_delta import router as stima_router
from production_store import ProductionStore, DEFAULT_ROOT
from public_catalogue import PublishedArchive, PUBLIC_CATALOGUE_PATH

app = FastAPI(
    title="Motore Espropri Italia API",
    description="Feed REST e intelligence per piani particellari e procedure D.P.R. 327/2001",
    version="2.0.0"
)

# CORS Middleware aperto per chiamate locali e dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ArchiveGZipMiddleware(GZipMiddleware):
    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if path.startswith("/api/documenti/") or path in {"/api/catasto/wms", "/catasto/wms"}:
            await self.app(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)


app.add_middleware(ArchiveGZipMiddleware, minimum_size=1000)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(stima_router)
from stima_delta import router_no_prefix as stima_no_prefix_router
app.include_router(stima_no_prefix_router)

DATA_PATH = DEFAULT_ROOT / "opere.json"
STATIC_INDEX = Path(__file__).parent / "index.html"
QUADRO_INTERFERENZE_HTML = Path(__file__).parent / "quadro_interferenze.html"
DOSSIER_PATH = Path(__file__).parent / "DOSSIER_ARCHITETTURALE.md"


class StimaPeriziaRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    tipologia: Literal["agricola", "edificabile"] = Field("agricola", description="'edificabile' oppure 'agricola'")
    valore_venale_unitario: float = Field(..., gt=0, description="Valore venale a metro quadro (€/mq)")
    superficie_mq: float = Field(..., gt=0, description="Superficie catastale espropriata (mq)")
    soprassuoli_eur: float = Field(0.0, ge=0, description="Valore soprassuoli/piantumazioni/fabbricati rurali (€)")
    coltivatore_diretto: bool = Field(False, description="Proprietario coltivatore diretto o IAP")
    cessione_volontaria: bool = Field(True, description="Accettazione cessione volontaria ex art. 45")
    vam_unitario: Optional[float] = Field(None, ge=0, description="Valore Agricolo Medio di zona (€/mq) ex art. 40 c. 4")


    @model_validator(mode="after")
    def verifica_vam(self):
        if self.tipologia == "agricola" and self.coltivatore_diretto and not self.cessione_volontaria and self.vam_unitario is None:
            raise ValueError("Specificare il VAM unitario per l'indennità aggiuntiva CD/IAP")
        return self


class StimaPeriziaResponse(BaseModel):
    indennita_base_eur: float
    indennita_finale_eur: float
    maggiorazione_eur: float
    maggiorazione_descrizione: str
    normativa_riferimento: str
    dettagli_calcolo: Dict[str, Any]


_opere_lock = RLock()
_opere_cache = None
_opere_signature = None


def load_opere(*, copia: bool = True) -> List[Dict[str, Any]]:
    """Cache invalidata da percorso, inode, dimensione e modifica nanosecondi."""
    global _opere_cache, _opere_signature
    if os.environ.get('MOTORE_PUBLIC_CATALOGUE_ONLY') == '1':
        return PublishedArchive(PUBLIC_CATALOGUE_PATH).catalogue()
    with _opere_lock:
        try:
            stat = DATA_PATH.stat()
        except FileNotFoundError:
            if DATA_PATH == DEFAULT_ROOT / 'opere.json' and not os.environ.get('MOTORE_ARCHIVE_ROOT') and PUBLIC_CATALOGUE_PATH.is_file():
                return PublishedArchive(PUBLIC_CATALOGUE_PATH).catalogue()
            if os.environ.get("VERCEL"):
                raise HTTPException(status_code=503, detail="Archivio persistente non configurato per questa installazione. Nessun fallback a dati dimostrativi.")
            return []
        signature = (str(DATA_PATH), stat.st_ino, stat.st_mtime_ns, stat.st_size)
        if _opere_signature != signature:
            with DATA_PATH.open(encoding="utf-8") as stream:
                dati = json.load(stream)
            if not isinstance(dati, list):
                raise ValueError("Il dataset opere deve essere una lista")
            _opere_cache, _opere_signature = dati, signature
        return deepcopy(_opere_cache) if copia else _opere_cache


def save_opere(opere: List[Dict[str, Any]]) -> None:
    """Sostituzione atomica: una scrittura interrotta non tronca il dataset."""
    global _opere_signature
    with _opere_lock:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DATA_PATH.parent,
                                             suffix=".tmp", delete=False) as stream:
                temporary = stream.name
                json.dump(opere, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, DATA_PATH)
            _opere_signature = None
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


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


@app.get("/{filename}.js")
async def serve_js(filename: str):
    base_dir = Path(__file__).parent
    js_path = base_dir / f"{filename}.js"
    if js_path.exists() and js_path.is_file():
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="File JavaScript non trovato")


# Overlay esclusivamente tra geometrie fornite e documentate: nessun buffer predefinito.
class TracciatoInterferenzeRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    tracciato_geojson: Dict[str, Any] | None = None  # compatibilità: un asse non definisce l'occupazione
    ingombro_geojson: Dict[str, Any] | None = None
    particelle_geojson: Dict[str, Any] | None = None
    fonte_ingombro_url: str | None = None
    fonte_catasto_url: str | None = None


@app.post("/api/catasto/interferenze")
@app.post("/catasto/interferenze")
def get_particelle_sotto_tracciato(req: TracciatoInterferenzeRequest):
    if not all((req.ingombro_geojson, req.particelle_geojson,
                req.fonte_ingombro_url, req.fonte_catasto_url)):
        raise HTTPException(status_code=409, detail="Servono ingombro di progetto e particelle poligonali con le rispettive fonti. Nessuna fascia o particella viene simulata da un asse.")
    from spatial_quality import overlay_documentato
    try:
        return overlay_documentato(req.ingombro_geojson, req.particelle_geojson,
                                   req.fonte_ingombro_url, req.fonte_catasto_url)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/catasto/wms")
@app.get("/catasto/wms")
def proxy_catasto_wms(
    bbox: str = Query(..., description="BBOX in EPSG:3857 (minx,miny,maxx,maxy)"),
    service: str = "WMS",
    request: str = "GetMap",
    version: str = "1.3.0",
    layers: str = "CP.CadastralParcel,BU.Building",
    styles: str = "",
    format: str = "image/png",
    transparent: bool = True,
    crs: str = "EPSG:3857",
    width: int = 256,
    height: int = 256
):
    """
    Proxy resiliente WMS per il Catasto Agenzia delle Entrate con CORS headers aperti.
    Risolve il blocco di sicurezza del browser sulle richieste verso i geoportali statali.
    """
    import requests

    ade_url = (
        f"https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows01.php?"
        f"service={service}&request={request}&version={version}"
        f"&layers={layers}&styles={styles}&format={format}&transparent={str(transparent).lower()}"
        f"&crs={crs}&width={width}&height={height}&bbox={bbox}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    try:
        r = requests.get(ade_url, headers=headers, timeout=8)
        content_type = r.headers.get("content-type", "")
        if r.status_code == 200 and content_type.startswith("image/"):
            return Response(
                content=r.content,
                media_type="image/png",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400"
                }
            )
    except Exception:
        pass

    # 1x1 transparent PNG fallback resiliente in caso di timeout o errore del server AdE
    import base64
    transparent_png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg=="
    )
    return Response(
        content=transparent_png_1x1,
        media_type="image/png",
        headers={"Access-Control-Allow-Origin": "*"}
    )



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
    return load_opere(copia=False)

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
                vam_val = req.vam_unitario * sup
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
    opere = load_opere(copia=False)

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
            or query in (o.get("ente") or o.get("ente_promotore") or "").lower()
            or query in o.get("comune", "").lower()
        ]

    return opere


@app.get("/opere/{slug}")
@app.get("/api/opere/{slug}")
async def get_opera_by_slug(slug: str):
    opere = load_opere(copia=False)
    for o in opere:
        if o.get("slug") == slug:
            return o
    raise HTTPException(status_code=404, detail="Opera non trovata")


@app.post("/opere")
@app.post("/api/opere")
async def create_or_update_opera(opera_data: Dict[str, Any]):
    raise HTTPException(status_code=409, detail="Archivio di produzione: le opere e le ditte vengono acquisite da documenti degli enti con provenienza. Inserimento libero disabilitato.")





def archive_store():
    if os.environ.get('MOTORE_PUBLIC_CATALOGUE_ONLY') == '1':
        return PublishedArchive(PUBLIC_CATALOGUE_PATH)
    if not (DEFAULT_ROOT / 'archivio.sqlite3').is_file():
        if not os.environ.get('MOTORE_ARCHIVE_ROOT') and PUBLIC_CATALOGUE_PATH.is_file():
            return PublishedArchive(PUBLIC_CATALOGUE_PATH)
        if os.environ.get('VERCEL'):
            raise HTTPException(status_code=503, detail='Archivio documentale non disponibile. Nessun dato simulato disponibile.')
    return ProductionStore()


@app.get("/api/archivio/stato")
def archive_status():
    return archive_store().status()


@app.get("/api/opere/{slug}/documenti")
def opera_documents(slug: str):
    return archive_store().documents(slug)


@app.get("/api/opere/{slug}/particelle")
def opera_parcels(slug: str):
    return archive_store().rows(slug)


@app.get("/api/opere/{slug}/particelle.geojson")
def opera_parcels_geojson(slug: str):
    rows = archive_store().rows(slug)
    features = [{"type":"Feature", "id":r["id"], "geometry":r["geometry"],
                 "properties":{k:v for k,v in r.items() if k not in {"geometry", "raw"}}}
                for r in rows if r.get("geometry")]
    return {"type":"FeatureCollection", "features":features,
            "righe_archiviate":len(rows), "righe_localizzate":len(features),
            "righe_senza_geometria":len(rows)-len(features)}


@app.get("/api/apl/tratte/{tratta}.geojson")
def apl_candidate_geometry(tratta: Literal["B2", "C"]):
    """Geometrie originali dei KMZ APL importati, servite come layer candidato non certificato."""
    path = DEFAULT_ROOT / "apl" / "geometrie" / f"APL_{tratta}.geojson"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Geometrie APL non archiviate")
    return FileResponse(path, media_type="application/geo+json", headers={"Cache-Control":"private, no-store"})


@app.get("/api/documenti/{identifier}/file")
def archived_document(identifier: str):
    store = archive_store()
    doc = store.document(identifier)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento non archiviato")
    if isinstance(store, PublishedArchive):
        # L'originale resta presso l'ente: non distribuiamo copie dell'archivio locale.
        from production_store import public_url
        return RedirectResponse(public_url(doc['fonte_url']), status_code=307,
                                headers={'Cache-Control': 'public, max-age=3600'})
    path = store.root / "documenti" / (doc["sha256"] + ".pdf")
    if not path.is_file() or path.stat().st_size != doc["byte_size"]:
        raise HTTPException(status_code=409, detail="Originale mancante o archivio incoerente")
    return FileResponse(path, media_type="application/pdf", headers={"Cache-Control":"private, no-store"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
