#!/usr/bin/env python3
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter

router = APIRouter(prefix="/api/stima", tags=["Stima Peritale Espropri"])

class DestinazioneUrbanistica(str, Enum):
    EDIFICABILE = "edificabile"
    AGRICOLA = "agricola"
    NON_EDIFICABILE = "non_edificabile"

class TipologiaIntervento(str, Enum):
    ESPROPRIO_TOTALE = "esproprio_totale"
    ESPROPRIO_PARZIALE = "esproprio_parziale"
    ASSERVIMENTO = "asservimento"
    OCCUPAZIONE_TEMPORANEA = "occupazione_temporanea"

class InputStimaPerizia(BaseModel):
    superficie_mq: float = Field(..., gt=0)
    destinazione: DestinazioneUrbanistica
    intervento: TipologiaIntervento
    offerta_unitaria_ente: float = Field(..., ge=0)
    valore_venale_mercato_mq: float = Field(..., gt=0)
    saggio_deprezzamento_asservimento: float = Field(0.50, ge=0.0, le=1.0)
    deprezzamento_relitto_euro: float = Field(0.0, ge=0.0)
    valore_soprassuoli_euro: float = Field(0.0, ge=0.0)
    frutti_pendenti_euro: float = Field(0.0, ge=0.0)
    is_coltivatore_diretto_o_iap: bool = Field(False)
    vam_tabellare_mq: float = Field(0.0, ge=0.0)
    adesione_cessione_volontaria: bool = Field(False)
    anni_occupazione: float = Field(1.0, ge=0.0)

class OutputStimaPerizia(BaseModel):
    totale_offerta_ente: float
    totale_stima_peritale: float
    delta_recuperabile: float
    percentuale_recupero: float
    dettaglio_calcolo: dict
    base_onorario_tecnico_consigliato: float

def calcola_indennita_peritale(p: InputStimaPerizia) -> OutputStimaPerizia:
    indennita_base_ente = p.offerta_unitaria_ente * p.superficie_mq

    if p.intervento in [TipologiaIntervento.ESPROPRIO_TOTALE, TipologiaIntervento.ESPROPRIO_PARZIALE]:
        indennita_suolo_reale = p.valore_venale_mercato_mq * p.superficie_mq
        danno_relitto = p.deprezzamento_relitto_euro if p.intervento == TipologiaIntervento.ESPROPRIO_PARZIALE else 0.0
    elif p.intervento == TipologiaIntervento.ASSERVIMENTO:
        indennita_suolo_reale = p.valore_venale_mercato_mq * p.superficie_mq * p.saggio_deprezzamento_asservimento
        danno_relitto = p.deprezzamento_relitto_euro
    elif p.intervento == TipologiaIntervento.OCCUPAZIONE_TEMPORANEA:
        indennita_suolo_reale = (p.valore_venale_mercato_mq * p.superficie_mq / 12.0) * p.anni_occupazione
        danno_relitto = 0.0

    indennita_soprassuoli = p.valore_soprassuoli_euro + p.frutti_pendenti_euro

    indennita_maggiorazione_cd = 0.0
    if p.is_coltivatore_diretto_o_iap and p.destinazione == DestinazioneUrbanistica.AGRICOLA:
        if p.vam_tabellare_mq > 0:
            indennita_maggiorazione_cd = p.vam_tabellare_mq * p.superficie_mq
        else:
            indennita_maggiorazione_cd = (p.valore_venale_mercato_mq * p.superficie_mq) * 0.5

    maggiorazione_cessione_volontaria = 0.0
    if p.adesione_cessione_volontaria:
        if p.destinazione == DestinazioneUrbanistica.AGRICOLA and not p.is_coltivatore_diretto_o_iap:
            maggiorazione_cessione_volontaria = indennita_suolo_reale * 0.50
        elif p.destinazione == DestinazioneUrbanistica.EDIFICABILE:
            maggiorazione_cessione_volontaria = indennita_suolo_reale * 0.10

    totale_perizia = (
        indennita_suolo_reale
        + danno_relitto
        + indennita_soprassuoli
        + indennita_maggiorazione_cd
        + maggiorazione_cessione_volontaria
    )

    delta_recuperabile = max(0.0, totale_perizia - indennita_base_ente)
    percentuale_recupero = (delta_recuperabile / indennita_base_ente * 100.0) if indennita_base_ente > 0 else 100.0
    base_onorario = round(delta_recuperabile * 0.10, 2)

    return OutputStimaPerizia(
        totale_offerta_ente=round(indennita_base_ente, 2),
        totale_stima_peritale=round(totale_perizia, 2),
        delta_recuperabile=round(delta_recuperabile, 2),
        percentuale_recupero=round(percentuale_recupero, 2),
        dettaglio_calcolo={
            "indennita_suolo_reale": round(indennita_suolo_reale, 2),
            "deprezzamento_relitto_art33": round(danno_relitto, 2),
            "soprassuoli_e_frutti": round(indennita_soprassuoli, 2),
            "indennita_aggiuntiva_cd_iap_art40": round(indennita_maggiorazione_cd, 2),
            "maggiorazione_cessione_art45": round(maggiorazione_cessione_volontaria, 2),
        },
        base_onorario_tecnico_consigliato=base_onorario,
    )

@router.post("/delta-recuperabile", response_model=OutputStimaPerizia)
def api_calcola_delta(payload: InputStimaPerizia):
    return calcola_indennita_peritale(payload)
