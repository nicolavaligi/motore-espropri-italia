"""
Motore Espropri Italia — Backend REST API
Proprietà intellettuale: Nicola Valigi (Houdinick)
Ambiente: Antigravity (AGY)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(
    title="Motore Espropri Italia API",
    description="Feed REST e intelligence per piani particellari e procedure D.P.R. 327/2001",
    version="1.0.0"
)

# CORS Middleware aperto per chiamate locali e dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = Path(__file__).parent / "data" / "opere.json"
STATIC_INDEX = Path(__file__).parent / "index.html"


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
        return FileResponse(STATIC_INDEX)
    return HTMLResponse("<h1>Motore Espropri Italia API attivo</h1><p>Visita <a href='/api/opere'>/api/opere</a></p>")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Motore Espropri Italia", "owner": "Nicola Valigi (Houdinick)"}


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


@app.get("/api/opere/{slug}")
async def get_opera_by_slug(slug: str):
    opere = load_opere()
    for o in opere:
        if o.get("slug") == slug:
            return o
    raise HTTPException(status_code=404, detail="Opera non trovata")


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
