"""Backend della Segretaria AaaS — multi-tenant via /{client_id}/.

Un solo servizio per tutti i clienti. Il tenant si risolve dal path (o dal numero in
arrivo); config, orari e vault arrivano da config/clienti.json e dal vault. Nessun
cliente è cablato nel codice.

Endpoint:
    GET  /health
    GET  /_tenant?numero=                     numero in arrivo -> client_id
    GET  /{client_id}/vault?file=faq,servizi  knowledge base (per costruire il prompt)
    GET  /{client_id}/disponibilita?da=&a=&durata_min=&limite=
    POST /{client_id}/prenota
    POST /{client_id}/sposta
    POST /{client_id}/cancella
    GET  /{client_id}/prenotazioni?da=&a=
    GET  /{client_id}/conversazione/{telefono}     memoria della chat
    POST /{client_id}/conversazione/{telefono}
    POST /{client_id}/pausa-bot/{telefono}         dopo un'escalation il bot tace
    POST /{client_id}/riattiva-bot/{telefono}
    GET  /{client_id}/eventi                       log strutturato (report settimanale)
    POST /{client_id}/eventi
    GET  /{client_id}/agenda?token=                agenda di oggi/domani per il titolare (HTML)

Auth: header `X-API-Key` (variabile d'ambiente API_KEY). Se API_KEY non è impostata il
servizio parte APERTO e lo dichiara nei log — comodo in locale, da non fare su Railway.

Chiamato da: workflow n8n (WhatsApp) e Agent ElevenLabs (voce). Nessuno dei due tiene una
propria copia di numeri, orari o FAQ: la fonte è una sola, questa.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import os
import secrets
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from config_loader import Cliente, ConfigError, adesso, carica_clienti, risolvi_da_numero
from slots import disponibilita, slot_prenotabile
from storage import (
    ConflittoPrenotazione,
    Conversazione,
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


class RichiestaConversazione(BaseModel):
    stato: dict = Field(default_factory=dict)


class RichiestaPausaBot(BaseModel):
    motivo: str = Field(min_length=1)


class RichiestaEvento(BaseModel):
    tipo: str = Field(min_length=1)
    telefono: str | None = None
    dati: dict = Field(default_factory=dict)


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


# --- tenant, vault, conversazioni, eventi -------------------------------------
# Servono al workflow n8n e all'Agent ElevenLabs. Stanno qui e non in n8n perche' la
# config e il vault devono avere UNA sola fonte: se n8n si tenesse una copia dei numeri
# o delle FAQ, prima o poi risponderebbe con quelle vecchie.

@app.get("/_tenant", dependencies=[Depends(verifica_api_key)])
def get_tenant(numero: str) -> dict:
    """Numero in arrivo -> cliente. 404 se il numero non e' di nessuno.

    Il 404 e' voluto e importante: n8n deve TACERE, non rispondere con un tenant di default.
    """
    cliente = risolvi_da_numero(CLIENTI, numero)
    if cliente is None:
        log.warning("numero non associato a nessun cliente: %s", numero)
        raise HTTPException(status_code=404, detail="numero non associato a nessun cliente")
    if not cliente.attivo:
        raise HTTPException(status_code=403, detail=f"cliente '{cliente.client_id}' non attivo")

    return {
        "ok": True,
        "client_id": cliente.client_id,
        "nome": cliente.nome,
        "provider_whatsapp": cliente.provider_whatsapp,
        "instance": cliente.instance,
        "delay_risposta_sec": {
            "min": cliente.delay_risposta_sec[0],
            "max": cliente.delay_risposta_sec[1],
        },
        "conferma_esplicita": cliente.conferma_esplicita,
        "soglia_confidenza": cliente.escalation.soglia_confidenza,
        "escalation": {
            "whatsapp": cliente.escalation.whatsapp,
            "agenda_token": cliente.escalation.agenda_token,
            "email": cliente.escalation.email,
        },
        "timezone": str(cliente.calendario.timezone),
        "durata_slot_min": cliente.calendario.durata_slot_min,
    }


FILE_VAULT_AMMESSI = {
    "orari", "servizi", "faq", "brand-voice",
    "vincoli", "prenotazioni", "escalation", "obiettivi",
}


@app.get("/{client_id}/vault", dependencies=[Depends(verifica_api_key)])
def get_vault(client_id: str, file: str | None = None) -> dict:
    """Contenuto del vault, da cui n8n costruisce il prompt.

    `file` e' una lista separata da virgole; di default quelli che servono a rispondere.
    `obiettivi` non e' incluso di default: e' una nota interna, non deve finire nel prompt.
    """
    cliente = risolvi_cliente(client_id)
    richiesti = (
        [f.strip() for f in file.split(",") if f.strip()]
        if file
        else ["brand-voice", "orari", "servizi", "faq", "vincoli"]
    )

    sconosciuti = [f for f in richiesti if f not in FILE_VAULT_AMMESSI]
    if sconosciuti:
        # Lista bianca, non concatenazione libera: `file=../../.env` non deve leggere nulla.
        raise HTTPException(status_code=400, detail=f"file non ammessi: {sconosciuti}")

    base = (Path(__file__).resolve().parent.parent / cliente.vault_path).resolve()
    contenuti: dict[str, str] = {}
    mancanti: list[str] = []
    for nome in richiesti:
        percorso = base / f"{nome}.md"
        if percorso.exists():
            contenuti[nome] = percorso.read_text(encoding="utf-8")
        else:
            mancanti.append(nome)

    if mancanti:
        log.warning("vault incompleto client=%s mancanti=%s", client_id, mancanti)

    return {"ok": True, "client_id": client_id, "file": contenuti, "mancanti": mancanti}


@app.get("/{client_id}/conversazione/{telefono}", dependencies=[Depends(verifica_api_key)])
def get_conversazione(client_id: str, telefono: str) -> dict:
    risolvi_cliente(client_id)
    return {"ok": True, "conversazione": storage.leggi_conversazione(client_id, telefono).to_dict()}


@app.post("/{client_id}/conversazione/{telefono}", dependencies=[Depends(verifica_api_key)])
def post_conversazione(client_id: str, telefono: str, req: RichiestaConversazione) -> dict:
    risolvi_cliente(client_id)
    attuale = storage.leggi_conversazione(client_id, telefono)
    salvata = storage.salva_conversazione(
        Conversazione(
            client_id=client_id,
            telefono=telefono,
            stato=req.stato,
            bot_in_pausa=attuale.bot_in_pausa,  # salvare lo stato non riattiva un bot in pausa
            motivo_pausa=attuale.motivo_pausa,
        )
    )
    return {"ok": True, "conversazione": salvata.to_dict()}


@app.post("/{client_id}/pausa-bot/{telefono}", dependencies=[Depends(verifica_api_key)])
def post_pausa_bot(client_id: str, telefono: str, req: RichiestaPausaBot) -> dict:
    """Dopo un'escalation il bot DEVE smettere di rispondere a quell'utente.

    Senza questo, la AI continuerebbe a chiacchierare mentre il titolare sta gia' gestendo
    il caso a mano: e' il modo piu' rapido per far arrabbiare un cliente.
    """
    risolvi_cliente(client_id)
    attuale = storage.leggi_conversazione(client_id, telefono)
    salvata = storage.salva_conversazione(
        Conversazione(
            client_id=client_id, telefono=telefono, stato=attuale.stato,
            bot_in_pausa=True, motivo_pausa=req.motivo,
        )
    )
    storage.registra_evento(client_id, "escalation", telefono, {"motivo": req.motivo})
    log.info("PAUSA BOT client=%s tel=%s motivo=%s", client_id, telefono, req.motivo)
    return {"ok": True, "conversazione": salvata.to_dict()}


@app.post("/{client_id}/riattiva-bot/{telefono}", dependencies=[Depends(verifica_api_key)])
def post_riattiva_bot(client_id: str, telefono: str) -> dict:
    risolvi_cliente(client_id)
    salvata = storage.salva_conversazione(
        Conversazione(client_id=client_id, telefono=telefono, stato={}, bot_in_pausa=False)
    )
    storage.registra_evento(client_id, "bot_riattivato", telefono, {})
    return {"ok": True, "conversazione": salvata.to_dict()}


@app.post("/{client_id}/eventi", dependencies=[Depends(verifica_api_key)])
def post_evento(client_id: str, req: RichiestaEvento) -> dict:
    risolvi_cliente(client_id)
    evento = storage.registra_evento(client_id, req.tipo, req.telefono, req.dati)
    return {"ok": True, "evento": evento}


@app.get("/{client_id}/eventi", dependencies=[Depends(verifica_api_key)])
def get_eventi(client_id: str, limite: int = 100) -> dict:
    risolvi_cliente(client_id)
    eventi = storage.elenca_eventi(client_id, min(limite, 1000))
    return {"ok": True, "client_id": client_id, "totale": len(eventi), "eventi": eventi}


# --- calendario ---------------------------------------------------------------

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


# --- agenda per il titolare ----------------------------------------------------
# Aperta dal link nell'avviso WhatsApp di escalation. Il titolare non ha l'API key e non
# deve averla: il cancello e' un token per cliente (escalation.agenda_token in config).
# Sola lettura, per design: da qui non si prenota, non si sposta, non si cancella.

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def _data_it(giorno: date) -> str:
    return f"{GIORNI_IT[giorno.weekday()]} {giorno.day} {MESI_IT[giorno.month - 1]}"


@app.get("/{client_id}/agenda", response_class=HTMLResponse)
def get_agenda(client_id: str, token: str = "") -> HTMLResponse:
    cliente = risolvi_cliente(client_id)
    atteso = cliente.escalation.agenda_token
    if not atteso:
        raise HTTPException(status_code=404, detail="agenda non abilitata per questo cliente")
    if not token or not secrets.compare_digest(token, atteso):
        raise HTTPException(status_code=401, detail="token mancante o errato")

    tz = cliente.calendario.timezone
    oggi = adesso(tz).date()
    totale = 0
    sezioni: list[str] = []
    etichette = {0: "Oggi", 1: "Domani"}
    for offset in range(7):
        giorno = oggi + timedelta(days=offset)
        prenotazioni = storage.elenca(
            client_id,
            da=datetime.combine(giorno, datetime.min.time(), tzinfo=tz),
            a=datetime.combine(giorno + timedelta(days=1), datetime.min.time(), tzinfo=tz),
        )
        ordinate = sorted(prenotazioni, key=lambda x: x.inizio)
        # i giorni oltre domani si mostrano solo se hanno appuntamenti (niente muro di vuoti)
        if offset > 1 and not ordinate:
            continue
        totale += len(ordinate)
        righe = []
        for p in ordinate:
            tel = html_mod.escape(p.telefono)
            tel_puro = "".join(ch for ch in p.telefono if ch.isdigit())
            nota = ""
            if p.note:
                nota_txt = html_mod.escape(p.note)
                nota = f'<div class="nota">{nota_txt}</div>'
            righe.append(
                '<div class="card">'
                f'<div class="ora">{p.inizio.astimezone(tz).strftime("%H:%M")}</div>'
                '<div class="info">'
                f"<div class=\"nome\">{html_mod.escape(p.nome_cliente)}</div>"
                f'<div class="servizio">{html_mod.escape(p.servizio)}</div>'
                f"{nota}"
                "</div>"
                '<div class="azioni">'
                f'<a class="btn tel" href="tel:+{tel_puro}" title="Chiama">&#128222;</a>'
                f'<a class="btn wa" href="https://wa.me/{tel_puro}" title="WhatsApp">&#128172;</a>'
                "</div>"
                "</div>"
            )
        etichetta = etichette.get(offset)
        titolo = f"{etichetta} · {_data_it(giorno)}" if etichetta else _data_it(giorno)
        badge = f'<span class="badge">{len(ordinate)}</span>' if ordinate else ""
        corpo = "\n".join(righe) if righe else '<div class="vuoto">Nessuna call in programma &#127749;</div>'
        sezioni.append(f'<section><h2>{titolo}{badge}</h2>\n{corpo}</section>')

    vista_insight = _vista_insight(client_id, token)

    pagina = f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<meta name="robots" content="noindex">
<title>{html_mod.escape(cliente.nome)}</title>
<style>
  :root {{ --ink:#0f172a; --muted:#64748b; --brand:#4f46e5; --brand2:#7c3aed; --bg:#f1f5f9; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif; margin: 0;
         background: var(--bg); color: var(--ink); }}
  header {{ background: linear-gradient(120deg, var(--brand), var(--brand2));
            color: #fff; padding: 20px 18px 14px; }}
  header h1 {{ margin: 0; font-size: 1.2rem; letter-spacing: .2px; }}
  header .sub {{ margin-top: 3px; font-size: .82rem; opacity: .85; }}
  nav {{ display: flex; gap: 6px; margin-top: 14px; }}
  nav button {{ flex: 1; border: 0; padding: 10px; border-radius: 12px 12px 0 0; font-weight: 700;
                font-size: .95rem; cursor: pointer; background: rgba(255,255,255,.18); color: #fff; }}
  nav button.attiva {{ background: var(--bg); color: var(--brand); }}
  main {{ padding: 14px 14px 8px; max-width: 720px; margin: 0 auto; }}
  h2 {{ font-size: .95rem; margin: 18px 4px 10px; color: var(--muted);
        text-transform: capitalize; display: flex; align-items: center; gap: 8px; }}
  .badge {{ background: var(--brand); color: #fff; font-size: .75rem; font-weight: 700;
            border-radius: 999px; padding: 1px 9px; }}
  .card {{ display: flex; align-items: center; gap: 14px; background: #fff;
           border-radius: 16px; padding: 14px; margin-bottom: 10px;
           box-shadow: 0 4px 14px rgba(15,23,42,.07); }}
  .ora {{ font-weight: 800; font-size: 1.05rem; color: var(--brand);
          background: #eef2ff; border-radius: 12px; padding: 10px 10px; min-width: 62px;
          text-align: center; }}
  .info {{ flex: 1; min-width: 0; }}
  .nome {{ font-weight: 700; }}
  .servizio {{ font-size: .85rem; color: var(--muted); margin-top: 2px; }}
  .nota {{ font-size: .8rem; color: var(--muted); margin-top: 6px; background: #f8fafc;
           border-left: 3px solid var(--brand2); padding: 6px 8px; border-radius: 6px;
           overflow-wrap: anywhere; }}
  .nota a, td a {{ color: var(--brand); }}
  .azioni {{ display: flex; flex-direction: column; gap: 8px; }}
  .btn {{ text-decoration: none; font-size: 1.05rem; background: var(--bg);
          border-radius: 10px; padding: 7px 9px; line-height: 1; }}
  .vuoto {{ color: var(--muted); background: #fff; border-radius: 16px; padding: 18px;
            text-align: center; border: 1.5px dashed #cbd5e1; }}
  footer {{ margin: 22px 0 18px; font-size: .75rem; color: #94a3b8; text-align: center; }}
  /* --- insight --- */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
               gap: 10px; margin: 16px 0; }}
  .kpi {{ background: #fff; border-radius: 16px; padding: 14px; cursor: pointer;
          box-shadow: 0 4px 14px rgba(15,23,42,.07); transition: transform .1s; }}
  .kpi:hover {{ transform: translateY(-2px); }}
  .dett {{ display: none; background: #fff; border-radius: 16px; padding: 12px 14px;
           margin: -6px 0 12px; box-shadow: 0 4px 14px rgba(15,23,42,.07); }}
  .dett.aperto {{ display: block; }}
  .driga {{ padding: 7px 2px; border-bottom: 1px solid #f1f5f9; font-size: .88rem; }}
  .driga:last-child {{ border-bottom: 0; }}
  .mini {{ font-size: .78rem; color: var(--muted); }}
  .kpi .n {{ font-size: 1.7rem; font-weight: 800; color: var(--brand); }}
  .kpi .l {{ font-size: .78rem; color: var(--muted); margin-top: 2px; }}
  .tab-wrap {{ background: #fff; border-radius: 16px; padding: 6px;
               box-shadow: 0 4px 14px rgba(15,23,42,.07); overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .84rem; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #f1f5f9;
            white-space: nowrap; }}
  th {{ color: var(--muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .4px; }}
  .stato {{ font-size: .72rem; font-weight: 700; border-radius: 999px; padding: 2px 9px;
            background: #eef2ff; color: var(--brand); text-transform: capitalize; }}
  .stato.cliente {{ background: #dcfce7; color: #15803d; }}
  .stato.perso {{ background: #fee2e2; color: #b91c1c; }}
  .vista {{ display: none; }}
  .vista.attiva {{ display: block; }}
</style>
</head><body>
<header>
  <h1>&#128640; {html_mod.escape(cliente.nome)}</h1>
  <div class="sub">{totale} call in agenda nei prossimi 7 giorni</div>
  <nav>
    <button id="b-cal" class="attiva" onclick="mostra('cal')">&#128197; Calendario</button>
    <button id="b-ins" onclick="mostra('ins')">&#128202; Insight</button>
  </nav>
</header>
<main>
<div id="v-cal" class="vista attiva">
{chr(10).join(sezioni)}
</div>
<div id="v-ins" class="vista">
{vista_insight}
</div>
<footer>Condivisa Marco + Michele · si aggiorna da sola ogni 5 minuti</footer>
</main>
<script>
function mostra(v) {{
  for (const x of ['cal','ins']) {{
    document.getElementById('v-'+x).classList.toggle('attiva', x===v);
    document.getElementById('b-'+x).classList.toggle('attiva', x===v);
  }}
  try {{ localStorage.setItem('vista', v); }} catch(e) {{}}
}}
try {{ const v = localStorage.getItem('vista'); if (v) mostra(v); }} catch(e) {{}}
</script>
</body></html>"""
    return HTMLResponse(pagina)


INSIGHT_URL = os.getenv(
    "INSIGHT_URL", "https://scrapingnia-production.up.railway.app/api/funnel/insight"
)


def _vista_insight(client_id: str, token: str) -> str:
    """Vista Insight (solo tenant 'nia'): numeri e tabella lead dal CRM ScrapingNia."""
    if client_id != "nia":
        return '<p class="vuoto">Insight non disponibile per questo cliente.</p>'
    try:
        req = urllib.request.Request(f"{INSIGHT_URL}?token={urllib.parse.quote(token)}",
                                     headers={"User-Agent": "segretaria-agenda"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.load(r)
    except Exception as e:  # noqa: BLE001
        return f'<p class="vuoto">Insight non raggiungibile in questo momento ({html_mod.escape(str(e)[:80])}).</p>'

    per_stato = d.get("per_stato") or {}
    call_fissate = per_stato.get("interessato", 0) + per_stato.get("trattativa", 0)
    leads = d.get("leads", [])

    def _riga_persona(nome, tel, extra=""):
        tel_puro = "".join(ch for ch in (tel or "") if ch.isdigit())
        chi = html_mod.escape(nome or tel or "?")
        wa = (f' <a href="https://wa.me/{tel_puro}" target="_blank">&#128172;</a>'
              if tel_puro else "")
        return f'<div class="driga"><strong>{chi}</strong>{extra}{wa}</div>'

    # pannelli di dettaglio (uno per card)
    p_scritti = "".join(
        _riga_persona(s.get("nome"), s.get("telefono"),
                      f' <span class="mini">{s.get("messaggi", 0)} msg · {html_mod.escape((s.get("ultimo") or "")[5:16].replace("T", " "))}</span>')
        for s in d.get("scritti_dettaglio", [])
    ) or '<div class="mini">Nessuno ancora.</div>'
    p_siti = "".join(
        _riga_persona(l.get("nome"), l.get("telefono"),
                      f' <a href="{html_mod.escape(l["sito_url"])}" target="_blank">apri sito</a>')
        for l in leads if l.get("sito_url")
    ) or '<div class="mini">Nessun sito ancora.</div>'
    p_caldi = "".join(
        _riga_persona(l.get("nome"), l.get("telefono"),
                      f' <span class="mini">{html_mod.escape(l.get("stato") or "")}</span>')
        for l in leads if (l.get("stato") in ("interessato", "trattativa"))
    ) or '<div class="mini">Nessun lead caldo ancora.</div>'
    p_chiusi = "".join(
        _riga_persona(l.get("nome"), l.get("telefono"))
        for l in leads if l.get("stato") == "cliente"
    ) or '<div class="mini">Nessun cliente chiuso ancora.</div>'

    kpi = (
        '<div class="kpi-grid">'
        f'<div class="kpi" onclick="dett(\'scritti\')"><div class="n">{d.get("scritti", 0)}</div><div class="l">Ci hanno scritto</div></div>'
        f'<div class="kpi" onclick="dett(\'siti\')"><div class="n">{d.get("siti_generati", 0)}</div><div class="l">Siti generati</div></div>'
        f'<div class="kpi" onclick="dett(\'caldi\')"><div class="n">{call_fissate}</div><div class="l">Lead caldi (call/interessati)</div></div>'
        f'<div class="kpi" onclick="dett(\'chiusi\')"><div class="n">{per_stato.get("cliente", 0)}</div><div class="l">Clienti chiusi</div></div>'
        "</div>"
        f'<div id="d-scritti" class="dett">{p_scritti}</div>'
        f'<div id="d-siti" class="dett">{p_siti}</div>'
        f'<div id="d-caldi" class="dett">{p_caldi}</div>'
        f'<div id="d-chiusi" class="dett">{p_chiusi}</div>'
        "<script>function dett(q){for(const x of ['scritti','siti','caldi','chiusi']){"
        "document.getElementById('d-'+x).classList.toggle('aperto', x===q && "
        "!document.getElementById('d-'+q).classList.contains('aperto'));}}</script>"
    )
    righe = []
    for l in d.get("leads", []):
        sito = (f'<a href="{html_mod.escape(l["sito_url"])}" target="_blank">apri sito</a>'
                if l.get("sito_url") else "—")
        tel = html_mod.escape(l.get("telefono") or "—")
        stato = html_mod.escape(l.get("stato") or "n/d")
        agg = html_mod.escape((l.get("aggiornato") or "")[:10])
        righe.append(
            f"<tr><td><strong>{html_mod.escape(l.get('nome') or '?')}</strong></td>"
            f"<td>{html_mod.escape(l.get('citta') or '—')}</td>"
            f'<td><span class="stato {stato}">{stato}</span></td>'
            f"<td>{sito}</td><td>{tel}</td><td>{agg}</td></tr>"
        )
    tabella = (
        '<div class="tab-wrap"><table><thead><tr>'
        "<th>Attività</th><th>Città</th><th>Stato</th><th>Sito</th><th>Telefono</th><th>Agg.</th>"
        "</tr></thead><tbody>" + "".join(righe) + "</tbody></table></div>"
        if righe else '<p class="vuoto">Nessun lead ancora.</p>'
    )
    return kpi + "<h2>Lead recenti</h2>" + tabella


def _con_fuso(dt: datetime, cfg) -> datetime:
    """Un orario senza fuso arriva da n8n/ElevenLabs come ora locale del cliente."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=cfg.timezone)
    return dt.astimezone(cfg.timezone)
