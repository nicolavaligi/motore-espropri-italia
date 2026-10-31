#!/usr/bin/env python3
"""
Modulo per il calcolo peritale estimativo e del Delta Recuperabile
nelle procedure espropriative e di asservimento (D.P.R. 327/2001).
Adeguato alle Sentenze Corte Costituzionale n. 348/2007 e n. 181/2011.
"""

from enum import Enum
from typing import Optional
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
    ASSERVIMENTO = "asservimento"  # elettrodotti, metanodotti, sottoservizi
    OCCUPAZIONE_TEMPORANEA = "occupazione_temporanea"


class InputStimaPerizia(BaseModel):
    # Dati dimensionali
    superficie_mq: float = Field(..., gt=0, description="Superficie interessata dall'intervento in mq")
    destinazione: DestinazioneUrbanistica
    intervento: TipologiaIntervento

    # Offerta Ente Espropriante (Parametri Tabellari/Base)
    offerta_unitaria_ente: float = Field(
        ..., ge=0, description="Indennità provvisoria/base offerta dall'ente (€/mq)"
    )

    # Parametri Estimativi Reali di Mercato (Valore Venale)
    valore_venale_mercato_mq: float = Field(
        ..., gt=0, description="Valore di mercato accertato da indagine OMI o metodo MCA (€/mq)"
    )

    # Criteri di Asservimento o Deprezzamento Parziale
    saggio_deprezzamento_asservimento: float = Field(
        0.50, ge=0.0, le=1.0, description="Percentuale svalutazione fascia asservita (standard 0.20 - 0.50)"
    )
    deprezzamento_relitto_euro: float = Field(
        0.0, ge=0.0, description="Perdita di valore subita dalla porzione residua non espropriata ex art. 33 (€)"
    )

    # Soprassuoli, Impianti e Danni Accessori
    valore_soprassuoli_euro: float = Field(
        0.0, ge=0.0, description="Valore di ricostruzione piantumazioni, recinzioni, pozzi, manufatti (€)"
    )
    frutti_pendenti_euro: float = Field(
        0.0, ge=0.0, description="Valore dei frutti pendenti o anticipazioni colturali ex art. 40 c. 4 (€)"
    )

    # Qualifiche Soggettive dell'Espropriando
    is_coltivatore_diretto_o_iap: bool = Field(
        False, description="Presenza di Coltivatore Diretto o Imprenditore Agricolo Professionale sul fondo"
    )
    vam_tabellare_mq: float = Field(
        0.0, ge=0.0, description="Valore Agricolo Medio tabellare provinciale (€/mq, per maggiorazione art. 40)"
    )
    adesione_cessione_volontaria: bool = Field(
        False, description="Accettazione tempestiva / stipula cessione volontaria ex art. 45"
    )

    # Durata occupazione (solo se occupazione_temporanea)
    anni_occupazione: float = Field(
        1.0, ge=0.0, description="Durata in anni dell'occupazione d'urgenza o temporanea"
    )


class OutputStimaPerizia(BaseModel):
    totale_offerta_ente: float
    totale_stima_peritale: float
    delta_recuperabile: float
    percentuale_recupero: float
    dettaglio_calcolo: dict
    base_onorario_tecnico_consigliato: float


def calcola_indennita_peritale(p: InputStimaPerizia) -> OutputStimaPerizia:
    """
    Esegue il conteggio analitico delle componenti indennitarie.
    """
    # 1. Calcolo Proposta Ente Base
    indennita_base_ente = p.offerta_unitaria_ente * p.superficie_mq

    # 2. Determinazione Indennità di Stima Reale secondo la tipologia
    if p.intervento in [TipologiaIntervento.ESPROPRIO_TOTALE, TipologiaIntervento.ESPROPRIO_PARZIALE]:
        # Valore Venale pieno dell'area espropriata (art. 37 per edificabili, art. 40 per agricole post C. Cost. 181/2011)
        indennita_suolo_reale = p.valore_venale_mercato_mq * p.superficie_mq

        # Danno per deprezzamento del relitto residuo (art. 33 D.P.R. 327/2001)
        danno_relitto = p.deprezzamento_relitto_euro if p.intervento == TipologiaIntervento.ESPROPRIO_PARZIALE else 0.0

    elif p.intervento == TipologiaIntervento.ASSERVIMENTO:
        # Metodo differenziale: svalutazione della fascia d'asservimento
        indennita_suolo_reale = (
            p.valore_venale_mercato_mq * p.superficie_mq * p.saggio_deprezzamento_asservimento
        )
        danno_relitto = p.deprezzamento_relitto_euro

    elif p.intervento == TipologiaIntervento.OCCUPAZIONE_TEMPORANEA:
        # Art. 50 DPR 327/2001: 1/12 del valore venale per ogni anno di occupazione
        indennita_suolo_reale = (p.valore_venale_mercato_mq * p.superficie_mq / 12.0) * p.anni_occupazione
        danno_relitto = 0.0

    # 3. Soprassuoli e Frutti Pendenti
    indennita_soprassuoli = p.valore_soprassuoli_euro + p.frutti_pendenti_euro

    # 4. Maggiorazione per Coltivatore Diretto / IAP (Art. 40, comma 4)
    # Se agricolo e condotto direttamente da CD/IAP: spetta un'indennità aggiuntiva pari al VAM
    indennita_maggiorazione_cd = 0.0
    if p.is_coltivatore_diretto_o_iap and p.destinazione == DestinazioneUrbanistica.AGRICOLA:
        if p.vam_tabellare_mq > 0:
            indennita_maggiorazione_cd = p.vam_tabellare_mq * p.superficie_mq
        else:
            # Stima prudenziale se manca il VAM: 50% del valore agricolo di mercato
            indennita_maggiorazione_cd = (p.valore_venale_mercato_mq * p.superficie_mq) * 0.5

    # 5. Maggiorazioni per Cessione Volontaria (Art. 45 D.P.R. 327/2001)
    # Se accettata: +50% su aree agricole non coltivate direttamente; triplo VAM se CD/IAP; +10% su fabbricati/edificabili
    maggiorazione_cessione_volontaria = 0.0
    if p.adesione_cessione_volontaria:
        if p.destinazione == DestinazioneUrbanistica.AGRICOLA:
            if not p.is_coltivatore_diretto_o_iap:
                maggiorazione_cessione_volontaria = indennita_suolo_reale * 0.50
        elif p.destinazione == DestinazioneUrbanistica.EDIFICABILE:
            maggiorazione_cessione_volontaria = indennita_suolo_reale * 0.10

    # Totale Complessivo Peritale
    totale_perizia = (
        indennita_suolo_reale
        + danno_relitto
        + indennita_soprassuoli
        + indennita_maggiorazione_cd
        + maggiorazione_cessione_volontaria
    )

    # 6. Delta Recuperabile e Metriche Finanziarie
    delta_recuperabile = max(0.0, totale_perizia - indennita_base_ente)
    percentuale_recupero = (
        (delta_recuperabile / indennita_base_ente * 100.0) if indennita_base_ente > 0 else 100.0
    )

    # Stima del compenso tecnico suggerito (a scaglioni o success fee sul delta)
    # Riferimento parametri forensi/tecnici: 8% - 12% del delta recuperato
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
    """Endpoint REST FastAPI per il calcolo in tempo reale dal cruscotto."""
    return calcola_indennita_peritale(payload)
