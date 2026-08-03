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
import scheda as sch
import abbonamenti as abb
import prenota as pre
import campagna as camp
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

@app.on_event("startup")
async def _avvia_guardia_abbonamenti() -> None:
    """Ogni 6 ore ricontrolla gli abbonamenti: la tolleranza scade col passare dei
    giorni, non all'arrivo di un evento Stripe."""
    import asyncio

    async def _giro():
        await asyncio.sleep(60)
        while True:
            for cid in elenco_clienti():
                try:
                    for c in abb.applica_regole_automatiche(storage, cid):
                        log.info("manutenzione AUTOMATICA %s per %s (%s, cliente %s)",
                                 "ON" if c["attiva"] else "OFF", c["chiave"], c["motivo"], cid)
                except Exception as e:  # noqa: BLE001
                    log.warning("guardia abbonamenti fallita per %s: %s", cid, e)
            await asyncio.sleep(6 * 3600)

    asyncio.create_task(_giro())


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
    liberi = disponibilita(cfg, prenotazioni, da, a, durata, ora, None)
    # Michele accetta call solo in certe fasce, una all'ora (30 min + 30 di cuscinetto)
    liberi = sch.filtra_per_finestre(liberi, _finestre_correnti(client_id))
    if limite:
        liberi = liberi[:limite]

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


def _console_cliente(client_id: str, token: str):
    """Cancello delle pagine della console: stesso token dell'agenda, niente API key."""
    cliente = risolvi_cliente(client_id)
    atteso = cliente.escalation.agenda_token
    if not atteso:
        raise HTTPException(status_code=404, detail="console non abilitata per questo cliente")
    if not token or not secrets.compare_digest(token, atteso):
        raise HTTPException(status_code=401, detail="token mancante o errato")
    return cliente


def _finestre_correnti(client_id: str) -> dict:
    """Ultime finestre salvate da Michele (evento piu' recente del tipo)."""
    try:
        for ev in storage.elenca_eventi(client_id, limite=200):
            if ev.get("tipo") == sch.TIPO_FINESTRE:
                return (ev.get("dati") or {}).get("finestre") or {}
    except Exception as e:  # noqa: BLE001
        log.warning("finestre non leggibili client=%s: %s", client_id, e)
    return {}


@app.get("/{client_id}/scheda", response_class=HTMLResponse)
def get_scheda(client_id: str, token: str = "") -> HTMLResponse:
    cliente = _console_cliente(client_id, token)
    return HTMLResponse(sch.pagina_scheda(client_id, token, cliente.nome))


@app.post("/{client_id}/scheda")
def post_scheda(client_id: str, req: dict, token: str = "") -> dict:
    _console_cliente(client_id, token)
    nome = str(req.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="manca il nome dell'attivita'")
    telefono = "".join(ch for ch in str(req.get("telefono") or "") if ch.isdigit())
    dati = {"cliente": {"nome": nome, "telefono": telefono},
            "risposte": req.get("risposte") or {}}
    storage.registra_evento(client_id, sch.TIPO_SCHEDA, telefono or None, dati)
    _salva_foto(client_id, abb.slug(nome), req.get("foto"))
    log.info("scheda salvata client=%s cliente=%s", client_id, nome)
    return {"ok": True}


@app.get("/{client_id}/scheda-vista/{etichetta}", response_class=HTMLResponse)
def get_scheda_vista(client_id: str, etichetta: str, token: str = "") -> HTMLResponse:
    """Apre una scheda compilata: tutte le risposte e le foto ricevute."""
    _console_cliente(client_id, token)
    eventi = storage.elenca_eventi(client_id, limite=500)
    scheda_trovata = None
    quando = ""
    for ev in eventi:                      # dal piu' recente: prendo l'ultima versione
        if ev.get("tipo") != sch.TIPO_SCHEDA:
            continue
        d = ev.get("dati") or {}
        cl = d.get("cliente") or {}
        if abb.slug(cl.get("nome") or "") == etichetta:
            scheda_trovata = d
            quando = ev.get("ts") or ""
            break
    if not scheda_trovata:
        raise HTTPException(status_code=404, detail="scheda non trovata")
    foto = []
    for ev in reversed(eventi):
        if ev.get("tipo") != sch.TIPO_FOTO:
            continue
        d = ev.get("dati") or {}
        if d.get("etichetta") == etichetta:
            foto.extend(d.get("foto") or [])
    log.info("scheda aperta: %s (%d foto)", etichetta, len(foto))
    return HTMLResponse(sch.pagina_scheda_vista(
        client_id, token, scheda_trovata.get("cliente") or {},
        scheda_trovata.get("risposte") or {}, foto, quando,
        bool(scheda_trovata.get("compilata_dal_cliente"))))


@app.get("/{client_id}/finestre", response_class=HTMLResponse)
def get_finestre(client_id: str, token: str = "") -> HTMLResponse:
    cliente = _console_cliente(client_id, token)
    return HTMLResponse(
        sch.pagina_finestre(client_id, token, cliente.nome, _finestre_correnti(client_id))
    )


@app.post("/{client_id}/finestre")
def post_finestre(client_id: str, req: dict, token: str = "") -> dict:
    _console_cliente(client_id, token)
    finestre = req.get("finestre")
    if not isinstance(finestre, dict):
        raise HTTPException(status_code=400, detail="finestre mancanti")
    storage.registra_evento(client_id, sch.TIPO_FINESTRE, None, {"finestre": finestre})
    log.info("finestre aggiornate client=%s", client_id)
    return {"ok": True}


def _salva_foto(client_id: str, etichetta: str, foto) -> int:
    """Le foto arrivano gia' rimpicciolite dal browser. Le tengo come evento a parte,
    cosi' la scheda resta leggera da leggere."""
    if not isinstance(foto, list) or not foto:
        return 0
    tenute = []
    for f in foto[:12]:
        if not isinstance(f, dict):
            continue
        dato = str(f.get("dato") or "")
        if dato.startswith("data:image/") and len(dato) < 1_200_000:
            tenute.append({"nome": str(f.get("nome") or "")[:80], "dato": dato})
    if not tenute:
        return 0
    storage.registra_evento(client_id, sch.TIPO_FOTO, None,
                            {"etichetta": etichetta, "quante": len(tenute), "foto": tenute})
    log.info("ricevute %d foto da %s (%s)", len(tenute), etichetta, client_id)
    return len(tenute)


@app.post("/{client_id}/invia")
def post_invia(client_id: str, req: dict, token: str = "") -> dict:
    """Manda al cliente il questionario o il link di pagamento, su WhatsApp,
    dal numero Nia. Il numero lo prende dalla scheda: niente copia-incolla."""
    _console_cliente(client_id, token)
    etichetta = str(req.get("etichetta") or "").strip()
    tipo = str(req.get("tipo") or "").strip()
    if tipo not in ("questionario", "attivazione"):
        raise HTTPException(status_code=400, detail="tipo non valido")
    if not etichetta:
        raise HTTPException(status_code=400, detail="manca il cliente")

    telefono = "".join(ch for ch in str(req.get("telefono") or "") if ch.isdigit())
    nome = etichetta.replace("-", " ").title()
    if not telefono:
        try:
            for ev in storage.elenca_eventi(client_id, limite=400):
                if ev.get("tipo") != sch.TIPO_SCHEDA:
                    continue
                cl = (ev.get("dati") or {}).get("cliente") or {}
                if abb.slug(cl.get("nome") or "") == etichetta:
                    telefono = "".join(c for c in str(cl.get("telefono") or "") if c.isdigit())
                    nome = cl.get("nome") or nome
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("invio: scheda non leggibile (%s)", e)
    if not telefono:
        raise HTTPException(status_code=400,
                            detail="questa scheda non ha un numero di telefono")

    base = str(req.get("base") or "").rstrip("/")
    percorso = "questionario" if tipo == "questionario" else "attiva"
    link = f"{base}/{client_id}/{percorso}/{etichetta}"
    ok, motivo = abb.invia_whatsapp(telefono, abb.testo_messaggio(tipo, nome, link))
    storage.registra_evento(client_id, "invio_cliente", telefono,
                            {"etichetta": etichetta, "tipo": tipo, "esito": ok,
                             "motivo": motivo, "link": link})
    if not ok:
        log.warning("invio %s a %s FALLITO: %s", tipo, etichetta, motivo)
        raise HTTPException(status_code=502, detail=f"non inviato: {motivo}")
    log.info("inviato %s a %s (%s)", tipo, nome, telefono)
    return {"ok": True, "telefono": telefono, "nome": nome}


@app.get("/{client_id}/questionario/{etichetta}", response_class=HTMLResponse)
def get_questionario(client_id: str, etichetta: str, corto: int = 0) -> HTMLResponse:
    """Questionario PUBBLICO: il cliente se lo compila da solo. Nessun token.
    Con ?corto=1 mostra le sette domande per chi arriva da una mail a freddo."""
    cliente = risolvi_cliente(client_id)
    nome = etichetta.replace("-", " ").title()
    precompilato = None
    try:
        for ev in storage.elenca_eventi(client_id, limite=400):
            if ev.get("tipo") != sch.TIPO_SCHEDA:
                continue
            cl = (ev.get("dati") or {}).get("cliente") or {}
            if abb.slug(cl.get("nome") or "") == etichetta:
                nome = cl.get("nome") or nome
                precompilato = ev.get("dati")
                break
    except Exception as e:  # noqa: BLE001
        log.warning("questionario: scheda non leggibile (%s)", e)
    log.info("questionario aperto: %s (%s)", etichetta, client_id)
    if corto:
        # l'apertura si misura qui, non con un pixel dentro la mail: ogni mail
        # porta un indirizzo diverso, quindi sappiamo gia' chi e'
        try:
            storage.registra_evento(client_id, camp.TIPO_APERTURA, None,
                                    {"etichetta": etichetta})
        except Exception as err:  # noqa: BLE001 - la pagina si apre lo stesso
            log.warning("apertura non registrata: %s", err)
    return HTMLResponse(sch.pagina_scheda(client_id, "", cliente.nome, precompilato,
                                          pubblico=True, etichetta=etichetta,
                                          nome_cliente=nome, corto=bool(corto)))


@app.post("/{client_id}/questionario/{etichetta}")
def post_questionario(client_id: str, etichetta: str, req: dict, corto: int = 0) -> dict:
    """Risposte del cliente: entrano in console come una scheda normale."""
    risolvi_cliente(client_id)
    nome = str(req.get("nome") or "").strip() or etichetta.replace("-", " ").title()
    telefono = "".join(ch for ch in str(req.get("telefono") or "") if ch.isdigit())
    dati = {"cliente": {"nome": nome, "telefono": telefono},
            "risposte": req.get("risposte") or {}, "compilata_dal_cliente": True,
            # da dove arriva: serve a leggere le conversioni della campagna
            "origine": "campagna" if corto else "questionario"}
    storage.registra_evento(client_id, sch.TIPO_SCHEDA, telefono or None, dati)
    n = _salva_foto(client_id, abb.slug(nome), req.get("foto"))
    log.info("questionario compilato dal cliente: %s (%d foto)", nome, n)
    return {"ok": True, "foto": n}


@app.get("/{client_id}/prenota-call", response_class=HTMLResponse)
def get_prenota_call(client_id: str, giorni: int = 10) -> HTMLResponse:
    """Pagina PUBBLICA da mandare al cliente: vede solo gli orari liberi e sceglie.
    Nessun token: il link e' pensato per finire in una mail o su WhatsApp."""
    cliente = risolvi_cliente(client_id)
    cfg = cliente.calendario
    ora = adesso(cfg.timezone)
    da = ora.date()
    a = da + timedelta(days=max(1, min(giorni, MAX_GIORNI_FINESTRA)))

    prenotazioni = storage.elenca(
        client_id,
        da=datetime.combine(da, datetime.min.time(), tzinfo=cfg.timezone),
        a=datetime.combine(a + timedelta(days=1), datetime.min.time(), tzinfo=cfg.timezone),
    )
    liberi = disponibilita(cfg, prenotazioni, da, a, cfg.durata_slot_min, ora, None)
    liberi = sch.filtra_per_finestre(liberi, _finestre_correnti(client_id))
    log.info("pagina prenotazione aperta: %s (%d slot)", client_id, len(liberi))
    return HTMLResponse(pre.pagina_prenota(client_id, cliente.nome, liberi,
                                           cfg.durata_slot_min))


@app.post("/{client_id}/prenota-call")
def post_prenota_call(client_id: str, req: dict) -> dict:
    """Prenotazione dalla pagina pubblica. Passa dagli stessi controlli di /prenota:
    non si fissa nulla che non avremmo proposto."""
    cliente = risolvi_cliente(client_id)
    cfg = cliente.calendario
    nome = str(req.get("nome") or "").strip()
    telefono = "".join(ch for ch in str(req.get("telefono") or "") if ch.isdigit())
    if not nome or not telefono:
        raise HTTPException(status_code=400, detail="servono nome e telefono")
    try:
        inizio = _con_fuso(datetime.fromisoformat(str(req.get("inizio"))), cfg)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="orario non valido")

    ora = adesso(cfg.timezone)
    prenotazioni = storage.elenca(
        client_id, da=inizio - timedelta(hours=12), a=inizio + timedelta(hours=12))
    ok, motivo = slot_prenotabile(inizio, cfg.durata_slot_min, cfg, prenotazioni, ora)
    if not ok:
        raise HTTPException(status_code=409, detail=motivo)
    if not sch.filtra_per_finestre([type("S", (), {"inizio": inizio})()],
                                   _finestre_correnti(client_id)):
        raise HTTPException(status_code=409, detail="orario non piu' disponibile")

    p = storage.crea(
        Prenotazione(
            id=nuova_prenotazione_id(), client_id=client_id, servizio="call conoscitiva",
            nome_cliente=nome, telefono=telefono, inizio=inizio,
            durata_min=cfg.durata_slot_min, note=str(req.get("note") or "") or None,
        ),
        capienza=cfg.capienza_per_slot,
    )
    log.info("call fissata dal cliente: %s %s (%s)", nome, inizio, client_id)
    return {"ok": True, "id": p.id,
            "quando": f"{pre._etichetta_giorno(inizio.date())} alle {inizio:%H:%M}"}


@app.get("/{client_id}/attiva/{etichetta}", response_class=HTMLResponse)
def get_attivazione(client_id: str, etichetta: str) -> HTMLResponse:
    """Pagina PUBBLICA che il cliente apre prima di pagare. Nessun token: e' pensata
    per essere mandata su WhatsApp al posto del link di pagamento nudo."""
    risolvi_cliente(client_id)
    nome = etichetta.replace("-", " ").title()
    anteprima = ""
    try:  # se c'e' una scheda con quel nome, uso il nome vero della scheda
        for ev in storage.elenca_eventi(client_id, limite=400):
            if ev.get("tipo") != sch.TIPO_SCHEDA:
                continue
            cl = (ev.get("dati") or {}).get("cliente") or {}
            if abb.slug(cl.get("nome") or "") == etichetta:
                nome = cl.get("nome") or nome
                break
    except Exception as e:  # noqa: BLE001
        log.warning("attivazione: scheda non leggibile (%s)", e)
    log.info("pagina attivazione aperta: %s (%s)", etichetta, client_id)
    return HTMLResponse(abb.pagina_attivazione(nome, etichetta, anteprima))


@app.post("/{client_id}/stripe")
async def post_stripe(client_id: str, request: Request) -> dict:
    """Webhook di Stripe: nessun token in chiaro, si verifica la FIRMA dell'evento."""
    risolvi_cliente(client_id)
    corpo = await request.body()
    segreto = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    ok, motivo = abb.verifica_firma(corpo, request.headers.get("stripe-signature"), segreto)
    if not ok:
        log.warning("stripe: evento RIFIUTATO client=%s (%s)", client_id, motivo)
        raise HTTPException(status_code=400, detail=f"firma non valida: {motivo}")
    try:
        evento = json.loads(corpo.decode("utf-8"))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="corpo non leggibile")
    dati = abb.estrai(evento)
    if not dati:
        return {"ok": True, "ignorato": evento.get("type")}
    storage.registra_evento(client_id, abb.TIPO_PAGAMENTO, dati.get("email") or None, dati)
    log.info("stripe: %s per %s (%s)", dati["esito"],
             dati.get("riferimento") or dati.get("email") or "?", client_id)
    for c in abb.applica_regole_automatiche(storage, client_id):
        log.info("manutenzione AUTOMATICA %s per %s (%s)",
                 "ON" if c["attiva"] else "OFF", c["chiave"], c["motivo"])
    return {"ok": True}


@app.post("/{client_id}/manutenzione")
def post_manutenzione(client_id: str, req: dict, token: str = "") -> dict:
    """Accende o spegne la manutenzione del sito di un cliente (dalla console)."""
    _console_cliente(client_id, token)
    chiave = str(req.get("chiave") or "").strip()
    if not chiave:
        raise HTTPException(status_code=400, detail="manca il cliente")
    attiva = bool(req.get("attiva"))
    storage.registra_evento(client_id, abb.TIPO_MANUTENZIONE, None,
                            {"chiave": chiave, "attiva": attiva})
    log.info("manutenzione %s per %s (%s)", "ON" if attiva else "OFF", chiave, client_id)
    return {"ok": True, "chiave": chiave, "attiva": attiva}


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
    try:
        _eventi = storage.elenca_eventi(client_id, limite=400)
        vista_schede = sch.riassunto_schede(_eventi, client_id=client_id, token=token)
        vista_abb = abb.vista_abbonamenti(abb.stato_abbonamenti(_eventi), client_id, token)
        vista_camp = camp.vista_campagna(_eventi, sch.TIPO_SCHEDA, totale)
    except Exception as e:  # noqa: BLE001
        log.warning("schede non leggibili: %s", e)
        vista_schede = '<div class="vuoto">Schede non disponibili adesso.</div>'
        vista_abb = '<div class="vuoto">Abbonamenti non disponibili adesso.</div>'
        vista_camp = '<div class="vuoto">Campagna non disponibile adesso.</div>'

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
  .azioni-console {{ display: grid; gap: 9px; margin: 4px 0 6px; }}
  .pill {{ border-radius: 999px; padding: 2px 9px; font-size: .74rem; font-weight: 700; }}
  .mini {{ border: 0; border-radius: 9px; padding: 9px 12px; font-weight: 700;
           font-size: .78rem; background: #1e293b; color: #fff; cursor: pointer; }}
  .mini.riattiva {{ background: #16a34a; }}
  .mini.paga {{ background: #16a34a; }}
  .mini.copia {{ background: #e2e8f0; color: #334155; }}
  .mini:disabled {{ opacity: .4; cursor: not-allowed; }}
  a.apri {{ color: inherit; text-decoration: none; }}
  a.apri:hover {{ color: var(--brand); }}
  .nota a.apri {{ color: var(--brand); font-weight: 600; }}
  .azioni {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
  .hint-abb {{ font-size: .8rem; color: var(--muted); margin: 10px 4px; line-height: 1.5; }}
  .azione {{ display: block; text-align: center; text-decoration: none; padding: 14px;
             border-radius: 12px; font-weight: 700; background: #fff; color: var(--brand);
             box-shadow: 0 1px 2px rgba(15,23,42,.06); }}
  .azione.primaria {{ background: var(--brand); color: #fff; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #f1f5f9;
            white-space: nowrap; }}
  th {{ color: var(--muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .4px; }}
  .stato {{ font-size: .72rem; font-weight: 700; border-radius: 999px; padding: 2px 9px;
            background: #eef2ff; color: var(--brand); text-transform: capitalize; }}
  .stato.cliente {{ background: #dcfce7; color: #15803d; }}
  .stato.perso {{ background: #fee2e2; color: #b91c1c; }}
  .riga-campagna {{ display: flex; gap: 8px; overflow-x: auto; margin: 6px 0 18px; }}
  .passo {{ flex: 1; min-width: 96px; background: #fff; border-radius: 14px;
            padding: 12px 10px; text-align: center;
            box-shadow: 0 4px 14px rgba(15,23,42,.07); }}
  .passo .n {{ font-size: 1.5rem; font-weight: 800; color: var(--brand); }}
  .passo .l {{ font-size: .74rem; color: var(--muted); margin-top: 2px; }}
  .passo .mini {{ font-size: .68rem; color: #b91c1c; margin-top: 3px; }}
  .vista {{ display: none; }}
  .vista.attiva {{ display: block; }}
  /* --- messaggini e domande, al posto degli avvisi del browser --- */
  #avviso {{ position: fixed; left: 50%; bottom: -80px; transform: translateX(-50%);
             background: #0f172a; color: #fff; padding: 12px 18px; border-radius: 12px;
             font-size: .86rem; font-weight: 600; max-width: 90vw; z-index: 60;
             box-shadow: 0 10px 30px rgba(15,23,42,.35); transition: bottom .22s ease;
             overflow-wrap: anywhere; }}
  #avviso.mostra {{ bottom: 20px; }}
  #avviso.ko {{ background: #b91c1c; }}
  #chiedi {{ position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 70;
             display: flex; align-items: center; justify-content: center; padding: 20px; }}
  #chiedi[hidden] {{ display: none; }}
  #chiedi .scatola {{ background: #fff; border-radius: 18px; padding: 20px; max-width: 420px;
                      box-shadow: 0 20px 60px rgba(15,23,42,.3); }}
  #chiedi p {{ margin: 0 0 16px; font-size: .92rem; line-height: 1.5; }}
  #chiedi .riga {{ display: flex; gap: 8px; justify-content: flex-end; }}
</style>
</head><body>
<header>
  <h1>&#128640; {html_mod.escape(cliente.nome)}</h1>
  <div class="sub">{totale} call in agenda nei prossimi 7 giorni</div>
  <nav>
    <button id="b-cal" class="attiva" onclick="mostra('cal')">&#128197; Calendario</button>
    <button id="b-ins" onclick="mostra('ins')">&#128202; Insight</button>
    <button id="b-sch" onclick="mostra('sch')">&#128203; Schede</button>
    <button id="b-abb" onclick="mostra('abb')">&#128179; Abbonamenti</button>
    <button id="b-cam" onclick="mostra('cam')">&#128232; Campagna</button>
  </nav>
</header>
<main>
<div id="v-cal" class="vista attiva">
  <div class="azioni-console">
    <a class="azione primaria" href="/{client_id}/prenota-call" target="_blank"
       rel="noopener">&#128198; Apri il calendario che vede il cliente</a>
    <button class="azione" type="button"
            onclick="copiaLink('/{client_id}/prenota-call')">&#128203; Copia il link da mandare</button>
  </div>
  <p class="hint-abb">Il cliente da quel link vede <b>solo gli orari liberi</b> e sceglie.
  Le call che fissa compaiono qui sotto.</p>
{chr(10).join(sezioni)}
</div>
<div id="v-ins" class="vista">
{vista_insight}
</div>
<div id="v-sch" class="vista">
  <div class="azioni-console">
    <a class="azione primaria" href="/{client_id}/scheda?token={token}">&#10133; Nuova scheda cliente</a>
    <a class="azione" href="/{client_id}/finestre?token={token}">&#128336; Le mie disponibilit&agrave;</a>
  </div>
  <h2>Schede compilate</h2>
{vista_schede}
</div>
<div id="v-abb" class="vista">
<h2>Chi paga</h2>
{vista_abb}
</div>
<div id="v-cam" class="vista">
<h2>Dalla mail al cliente</h2>
{vista_camp}
</div>
<footer>Condivisa Marco + Michele · si aggiorna da sola ogni 5 minuti</footer>
</main>
<div id="avviso"></div>
<div id="chiedi" hidden><div class="scatola">
  <p id="chiedi-testo"></p>
  <div class="riga">
    <button class="mini copia" onclick="rispondi(false)">Annulla</button>
    <button class="mini" id="chiedi-ok" onclick="rispondi(true)">Procedi</button>
  </div>
</div></div>
<script>
/* Niente finestre di sistema: un messaggino in pagina che sparisce da solo,
   e una domanda che sta dentro la console invece di bloccare il browser. */
function avvisa(testo, ko) {{
  var a = document.getElementById('avviso');
  a.textContent = testo;
  a.className = 'mostra' + (ko ? ' ko' : '');
  clearTimeout(avvisa._t);
  avvisa._t = setTimeout(function () {{ a.className = ''; }}, ko ? 6000 : 3500);
}}
var _rispostaA = null;
function chiedi(testo, testoOk) {{
  document.getElementById('chiedi-testo').innerHTML = testo;
  document.getElementById('chiedi-ok').textContent = testoOk || 'Procedi';
  document.getElementById('chiedi').hidden = false;
  return new Promise(function (ris) {{ _rispostaA = ris; }});
}}
function rispondi(s) {{
  document.getElementById('chiedi').hidden = true;
  if (_rispostaA) {{ _rispostaA(s); _rispostaA = null; }}
}}
async function copiaLink(percorso) {{
  var url = location.origin + percorso;
  try {{ await navigator.clipboard.writeText(url); avvisa('Link copiato: ' + url); }}
  catch (e) {{ avvisa(url, true); }}
}}
function mostra(v) {{
  for (const x of ['cal','ins','sch','abb','cam']) {{
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
