"""Microservizio calendario — multi-tenant via /{client_id}/.

Un solo servizio per tutti i clienti. Il tenant si risolve dal path; config e orari
arrivano da config/clienti.json. Nessun cliente è cablato nel codice.

Endpoint:
    GET  /{client_id}/disponibilita?da=&a=&durata_min=&limite=
    POST /{client_id}/prenota
    POST /{client_id}/sposta
    POST /{client_id}/cancella
    GET  /{client_id}/prenotazioni?da=&a=
    GET  /health

Auth: header `X-API-Key` (variabile d'ambiente API_KEY). Se API_KEY non è impostata il
servizio parte APERTO e lo dichiara nei log — comodo in locale, da non fare su Railway.

Chiamato da: workflow n8n (WhatsApp) e Agent ElevenLabs (voce).
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config_loader import Cliente, ConfigError, adesso, carica_clienti
from slots import disponibilita, slot_prenotabile
from storage import (
    ConflittoPrenotazione,
    Prenotazione,
    PrenotazioneNonTrovata,
    crea_storage,
    nuova_prenotazione_id,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("calendario")

MAX_GIORNI_FINESTRA = 62  # tetto alla finestra richiesta, per non far esplodere il calcolo

app = FastAPI(title="Segretaria AaaS — Calendario", version="1.0.0")

storage = crea_storage()
API_KEY = os.getenv("API_KEY")

try:
    CLIENTI = carica_clienti()
except ConfigError as exc:  # config rotta = non parte. Meglio che rispondere a caso.
    raise SystemExit(f"config/clienti.json non valida: {exc}") from exc

log.info(
    "avvio: storage=%s, clienti=%s, auth=%s",
    type(storage).__name__,
    sorted(CLIENTI),
    "attiva" if API_KEY else "DISATTIVA (nessuna API_KEY)",
)


# --- auth e risoluzione tenant -------------------------------------------------

def verifica_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API key mancante o errata")


def risolvi_cliente(client_id: str) -> Cliente:
    """Il tenant deve esistere ED essere attivo. Nessun fallback su un cliente di default."""
    cliente = CLIENTI.get(client_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail=f"cliente '{client_id}' non configurato")
    if not cliente.attivo:
        raise HTTPException(status_code=403, detail=f"cliente '{client_id}' non attivo")
    return cliente


# --- modelli ------------------------------------------------------------------

class RichiestaPrenota(BaseModel):
    servizio: str = Field(min_length=1)
    nome_cliente: str = Field(min_length=1)
    telefono: str = Field(min_length=3)
    inizio: datetime
    durata_min: int | None = Field(default=None, gt=0, le=8 * 60)
    note: str | None = None


class RichiestaSposta(BaseModel):
    prenotazione_id: str
    nuovo_inizio: datetime


class RichiestaCancella(BaseModel):
    prenotazione_id: str


# --- error handling -----------------------------------------------------------

@app.exception_handler(ConflittoPrenotazione)
async def _conflitto(_: Request, exc: ConflittoPrenotazione) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"ok": False, "errore": "slot_occupato", "dettaglio": str(exc)},
    )


@app.exception_handler(PrenotazioneNonTrovata)
async def _non_trovata(_: Request, exc: PrenotazioneNonTrovata) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"ok": False, "errore": "prenotazione_non_trovata", "dettaglio": str(exc)},
    )


# --- endpoint -----------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "storage": type(storage).__name__,
        "clienti_attivi": sorted(c for c, v in CLIENTI.items() if v.attivo),
    }


@app.get("/{client_id}/disponibilita", dependencies=[Depends(verifica_api_key)])
def get_disponibilita(
    client_id: str,
    da: date | None = None,
    a: date | None = None,
    durata_min: int | None = None,
    limite: int | None = None,
) -> dict:
    cliente = risolvi_cliente(client_id)
    cfg = cliente.calendario
    ora = adesso(cfg.timezone)

    da = da or ora.date()
    a = a or (da + timedelta(days=7))
    if a < da:
        raise HTTPException(status_code=400, detail="'a' precede 'da'")
    if (a - da).days > MAX_GIORNI_FINESTRA:
        raise HTTPException(
            status_code=400, detail=f"finestra troppo ampia (max {MAX_GIORNI_FINESTRA} giorni)"
        )

    durata = durata_min or cfg.durata_slot_min
    prenotazioni = storage.elenca(
        client_id,
        da=datetime.combine(da, datetime.min.time(), tzinfo=cfg.timezone),
        a=datetime.combine(a + timedelta(days=1), datetime.min.time(), tzinfo=cfg.timezone),
    )
    liberi = disponibilita(cfg, prenotazioni, da, a, durata, ora, limite)

    log.info("disponibilita client=%s da=%s a=%s slot=%d", client_id, da, a, len(liberi))
    return {
        "ok": True,
        "client_id": client_id,
        "da": da.isoformat(),
        "a": a.isoformat(),
        "durata_min": durata,
        "slot": [s.to_dict() for s in liberi],
    }


@app.post("/{client_id}/prenota", dependencies=[Depends(verifica_api_key)])
def post_prenota(client_id: str, req: RichiestaPrenota) -> dict:
    cliente = risolvi_cliente(client_id)
    cfg = cliente.calendario
    ora = adesso(cfg.timezone)

    inizio = _con_fuso(req.inizio, cfg)
    durata = req.durata_min or cfg.durata_slot_min

    # Stesse regole della disponibilità: non si prenota nulla che non avremmo proposto.
    prenotazioni = storage.elenca(
        client_id, da=inizio - timedelta(hours=12), a=inizio + timedelta(hours=12)
    )
    ok, motivo = slot_prenotabile(inizio, durata, cfg, prenotazioni, ora)
    if not ok:
        log.info("prenota RIFIUTATA client=%s inizio=%s motivo=%s", client_id, inizio, motivo)
        raise HTTPException(status_code=409, detail=motivo)

    p = storage.crea(
        Prenotazione(
            id=nuova_prenotazione_id(),
            client_id=client_id,
            servizio=req.servizio,
            nome_cliente=req.nome_cliente,
            telefono=req.telefono,
            inizio=inizio,
            durata_min=durata,
            note=req.note,
        ),
        capienza=cfg.capienza_per_slot,
    )
    log.info("prenota OK client=%s id=%s inizio=%s", client_id, p.id, p.inizio)
    return {"ok": True, "prenotazione": p.to_dict()}


@app.post("/{client_id}/sposta", dependencies=[Depends(verifica_api_key)])
def post_sposta(client_id: str, req: RichiestaSposta) -> dict:
    cliente = risolvi_cliente(client_id)
    cfg = cliente.calendario
    ora = adesso(cfg.timezone)

    attuale = storage.leggi(client_id, req.prenotazione_id)
    if attuale.stato != "confermata":
        raise HTTPException(status_code=409, detail="la prenotazione è già cancellata")

    nuovo_inizio = _con_fuso(req.nuovo_inizio, cfg)
    prenotazioni = [
        p
        for p in storage.elenca(
            client_id, da=nuovo_inizio - timedelta(hours=12), a=nuovo_inizio + timedelta(hours=12)
        )
        if p.id != attuale.id  # la prenotazione non fa conflitto con se stessa
    ]
    ok, motivo = slot_prenotabile(nuovo_inizio, attuale.durata_min, cfg, prenotazioni, ora)
    if not ok:
        raise HTTPException(status_code=409, detail=motivo)

    p = storage.sposta(client_id, attuale.id, nuovo_inizio, capienza=cfg.capienza_per_slot)
    log.info("sposta OK client=%s id=%s -> %s", client_id, p.id, p.inizio)
    return {"ok": True, "prenotazione": p.to_dict()}


@app.post("/{client_id}/cancella", dependencies=[Depends(verifica_api_key)])
def post_cancella(client_id: str, req: RichiestaCancella) -> dict:
    risolvi_cliente(client_id)
    p = storage.cancella(client_id, req.prenotazione_id)
    log.info("cancella OK client=%s id=%s", client_id, p.id)
    return {"ok": True, "prenotazione": p.to_dict()}


@app.get("/{client_id}/prenotazioni", dependencies=[Depends(verifica_api_key)])
def get_prenotazioni(
    client_id: str,
    da: date | None = None,
    a: date | None = None,
    includi_cancellate: bool = False,
) -> dict:
    cliente = risolvi_cliente(client_id)
    tz = cliente.calendario.timezone
    inizio = datetime.combine(da, datetime.min.time(), tzinfo=tz) if da else None
    fine = (
        datetime.combine(a + timedelta(days=1), datetime.min.time(), tzinfo=tz) if a else None
    )
    prenotazioni = storage.elenca(
        client_id, da=inizio, a=fine, includi_cancellate=includi_cancellate
    )
    return {
        "ok": True,
        "client_id": client_id,
        "totale": len(prenotazioni),
        "prenotazioni": [p.to_dict() for p in prenotazioni],
    }


def _con_fuso(dt: datetime, cfg) -> datetime:
    """Un orario senza fuso arriva da n8n/ElevenLabs come ora locale del cliente."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=cfg.timezone)
    return dt.astimezone(cfg.timezone)
