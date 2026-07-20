"""Wizard "nuovo cliente" — l'onboarding in un comando.

    python scripts/nuovo_cliente.py --client-id studio-rossi --nome "Studio Rossi" \
        --whatsapp 393331234567 --titolare 393339998877

Fa da solo tutto l'automatizzabile:
  1. copia vault/_TEMPLATE in vault/clienti/<client_id>/ e pre-compila i campi noti
     (nome, client_id, date, orari, parametri calendario, numero di escalation)
  2. aggiunge il blocco in config/clienti.json con `attivo: false` e agenda_token generato
  3. (con --evolution) crea l'istanza Evolution col nome = client_id, imposta il webhook
     verso n8n VERIFICANDO l'URL prima di fidarsene, e scarica il QR da far scansionare
  4. stampa la checklist dei passi che restano umani, nell'ordine giusto

Il go-live resta un gesto solo e resta di Marco: `attivo: true` + push.

Modalità utili:
    --solo-qr           rigenera solo il QR di un'istanza esistente (scade in fretta)
    --orari "..."       es. "lun-ven=09:00-13:00,14:00-19:00;sab=09:00-13:00"

Variabili d'ambiente per lo step Evolution: EVOLUTION_URL, EVOLUTION_API_KEY,
N8N_WEBHOOK_URL (default: l'n8n di produzione della Segretaria).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import secrets
import shutil
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
GIORNI_ESTESI = {
    "lun": "Lunedì", "mar": "Martedì", "mer": "Mercoledì", "gio": "Giovedì",
    "ven": "Venerdì", "sab": "Sabato", "dom": "Domenica",
}
ORARI_DEFAULT = "lun-ven=09:00-13:00,14:00-19:00;sab=09:00-13:00"
N8N_WEBHOOK_DEFAULT = "https://n8n-production-5db91.up.railway.app/webhook/segretaria"
BACKEND_URL_DEFAULT = "https://web-production-63865.up.railway.app"


class WizardError(Exception):
    pass


# --- parsing input --------------------------------------------------------------

def solo_cifre(numero: str) -> str:
    return re.sub(r"\D", "", numero or "").lstrip("0")


def _parse_ora(v: str, dove: str) -> str:
    if not re.fullmatch(r"\d{1,2}:\d{2}", v.strip()):
        raise WizardError(f"orario non valido '{v}' in '{dove}', atteso HH:MM")
    h, m = v.strip().split(":")
    return f"{int(h):02d}:{m}"


def parse_orari(testo: str) -> dict[str, list[list[str]]]:
    """'lun-ven=09:00-13:00,14:00-19:00;sab=09:00-13:00' -> orari_apertura per config.

    Giorni non citati = chiusi. Massimo 2 fasce per giorno (limite della tabella del vault).
    """
    orari: dict[str, list[list[str]]] = {g: [] for g in GIORNI}
    for blocco in [b.strip() for b in testo.split(";") if b.strip()]:
        if "=" not in blocco:
            raise WizardError(f"blocco orari senza '=': '{blocco}'")
        giorni_str, fasce_str = blocco.split("=", 1)

        giorni: list[str] = []
        for pezzo in giorni_str.split(","):
            pezzo = pezzo.strip().lower()
            if "-" in pezzo:
                da, a = [p.strip() for p in pezzo.split("-", 1)]
                if da not in GIORNI or a not in GIORNI:
                    raise WizardError(f"giorno sconosciuto in '{pezzo}', attesi: {GIORNI}")
                i, j = GIORNI.index(da), GIORNI.index(a)
                if i > j:
                    raise WizardError(f"intervallo giorni invertito: '{pezzo}'")
                giorni.extend(GIORNI[i : j + 1])
            else:
                if pezzo not in GIORNI:
                    raise WizardError(f"giorno sconosciuto '{pezzo}', attesi: {GIORNI}")
                giorni.append(pezzo)

        fasce: list[list[str]] = []
        for fascia in [f.strip() for f in fasce_str.split(",") if f.strip()]:
            if "-" not in fascia:
                raise WizardError(f"fascia senza '-': '{fascia}'")
            inizio, fine = [p.strip() for p in fascia.split("-", 1)]
            inizio, fine = _parse_ora(inizio, blocco), _parse_ora(fine, blocco)
            if inizio >= fine:
                raise WizardError(f"fascia invertita: '{fascia}'")
            fasce.append([inizio, fine])
        if not 1 <= len(fasce) <= 2:
            raise WizardError(f"servono 1 o 2 fasce per giorno, trovate {len(fasce)} in '{blocco}'")

        for g in giorni:
            orari[g] = sorted(fasce)
    return orari


# --- vault ----------------------------------------------------------------------

def _riga_orari(giorno: str, fasce: list[list[str]]) -> str:
    nome = GIORNI_ESTESI[giorno]
    if not fasce:
        return f"| {nome} | — | — | — | sì |"
    if len(fasce) == 1:
        return f"| {nome} | {fasce[0][0]} | {fasce[0][1]} | — | no |"
    return f"| {nome} | {fasce[0][0]} | {fasce[1][1]} | {fasce[0][1]}-{fasce[1][0]} | no |"


def crea_vault(root: Path, dati: dict) -> Path:
    """Copia il template e pre-compila quello che il wizard sa già.

    I segnaposto che richiedono il materiale del cliente (faq, servizi, brand-voice)
    restano volutamente lì: verifica_coerenza impedisce il go-live finché ci sono.
    """
    template = root / "vault" / "_TEMPLATE"
    dest = root / "vault" / "clienti" / dati["client_id"]
    if dest.exists():
        raise WizardError(f"il vault {dest} esiste già")
    if not template.is_dir():
        raise WizardError(f"template non trovato: {template}")
    shutil.copytree(template, dest)

    oggi = date.today().isoformat()
    for md in dest.glob("*.md"):
        testo = md.read_text(encoding="utf-8")
        testo = testo.replace("<<client_id>>", dati["client_id"])
        testo = testo.replace("<<Nome Attività>>", dati["nome"])
        testo = testo.replace("<<AAAA-MM-GG>>", oggi)
        md.write_text(testo, encoding="utf-8")

    # prenotazioni.md: la tabella parametri DEVE combaciare con la config
    # (verifica_coerenza lo controlla riga per riga).
    pren = dest / "prenotazioni.md"
    testo = pren.read_text(encoding="utf-8")
    for nome_param, valore in [
        ("durata_slot_min", dati["durata_slot_min"]),
        ("capienza_per_slot", dati["capienza_per_slot"]),
        ("anticipo_min_ore", dati["anticipo_min_ore"]),
        ("anticipo_max_giorni", dati["anticipo_max_giorni"]),
        ("buffer_min", dati["buffer_min"]),
    ]:
        testo, n = re.subn(
            rf"(\|\s*`{nome_param}`\s*\|\s*)<<\d+>>",
            rf"\g<1>{valore}",
            testo,
        )
        if n != 1:
            raise WizardError(f"prenotazioni.md: non trovo la riga `{nome_param}` nel template")
    pren.write_text(testo, encoding="utf-8")

    # orari.md: la tabella si rigenera dalle fasce vere.
    orari_md = dest / "orari.md"
    testo = orari_md.read_text(encoding="utf-8")
    for giorno in GIORNI:
        testo, n = re.subn(
            rf"^\|\s*{GIORNI_ESTESI[giorno]}\s*\|.*$",
            _riga_orari(giorno, dati["orari_apertura"][giorno]),
            testo,
            flags=re.MULTILINE,
        )
        if n != 1:
            raise WizardError(f"orari.md: non trovo la riga di {GIORNI_ESTESI[giorno]} nel template")
    orari_md.write_text(testo, encoding="utf-8")

    # escalation.md: il numero personale del titolare.
    esc = dest / "escalation.md"
    testo = esc.read_text(encoding="utf-8")
    testo = testo.replace("<<+39 3XX XXXXXXX>>", f"+{dati['titolare']}")
    esc.write_text(testo, encoding="utf-8")

    return dest


# --- config ---------------------------------------------------------------------

def aggiungi_config(root: Path, dati: dict) -> str:
    """Aggiunge il blocco cliente a clienti.json. Torna l'agenda_token generato."""
    percorso = root / "config" / "clienti.json"
    config = json.loads(percorso.read_text(encoding="utf-8"))

    if any(c["client_id"] == dati["client_id"] for c in config["clienti"]):
        raise WizardError(f"client_id '{dati['client_id']}' già presente in config")

    token = secrets.token_hex(16)
    config["clienti"].append({
        "client_id": dati["client_id"],
        "nome": dati["nome"],
        # SEMPRE spento alla nascita: il go-live è una decisione, non un default.
        "attivo": False,
        "conferma_esplicita": True,
        "canali": {
            "whatsapp": {
                "provider": "evolution",
                "phone_id": dati["whatsapp"],
                # nome istanza = client_id, la convenzione che tiene in piedi il multi-tenant
                "instance": dati["client_id"],
                "delay_risposta_sec": {"min": 300, "max": 900},
            },
            "voce": {
                "provider": "twilio",
                "numero": None,
                "elevenlabs_agent_id": None,
            },
        },
        "vault_path": f"vault/clienti/{dati['client_id']}",
        "calendar_url": f"{dati['backend_url']}/{dati['client_id']}",
        "calendario": {
            "timezone": "Europe/Rome",
            "durata_slot_min": dati["durata_slot_min"],
            "capienza_per_slot": dati["capienza_per_slot"],
            "anticipo_min_ore": dati["anticipo_min_ore"],
            "anticipo_max_giorni": dati["anticipo_max_giorni"],
            "buffer_min": dati["buffer_min"],
            "orari_apertura": dati["orari_apertura"],
            "chiusure": [],
        },
        "escalation": {
            "soglia_confidenza": 0.6,
            "whatsapp": f"+{dati['titolare']}",
            "agenda_token": token,
            "email": None,
        },
    })

    percorso.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return token


def verifica_config_caricabile(root: Path) -> None:
    """La config nuova deve essere digeribile dal calendar service, non solo JSON valido."""
    sys.path.insert(0, str(root / "calendar"))
    from config_loader import carica_clienti  # noqa: PLC0415

    carica_clienti(root / "config" / "clienti.json")


# --- Evolution ------------------------------------------------------------------

def _http(metodo: str, url: str, corpo: dict | None = None, headers: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, method=metodo)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    dati = None
    if corpo is not None:
        req.add_header("Content-Type", "application/json")
        dati = json.dumps(corpo).encode("utf-8")
    try:
        with urllib.request.urlopen(req, dati, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def verifica_webhook_n8n(url: str) -> str:
    """L'URL giusto risponde alla GET con 'not registered for GET requests'.

    Quello col webhookId dentro (che l'API di n8n riporta ma che NON esiste) risponde
    'is not registered'. Con l'URL sbagliato Evolution consegna a un 404 in silenzio:
    e' il bug che ci e' gia' costato mezza giornata, quindi qui e' un check bloccante.
    """
    _, corpo = _http("GET", url)
    if "GET requests" in corpo:
        return "ok"
    if "not registered" in corpo:
        return "inattivo"  # esiste ma il workflow è spento: va bene, si attiva dopo
    raise WizardError(f"l'URL webhook n8n non risponde come atteso: {url} -> {corpo[:120]}")


def setup_evolution(dati: dict, evo_url: str, evo_key: str, n8n_url: str, qr_path: Path) -> list[str]:
    """Istanza + webhook + QR. Torna note da mostrare nella checklist."""
    note: list[str] = []
    cid = dati["client_id"]
    headers = {"apikey": evo_key}
    base = evo_url.rstrip("/")

    esito = verifica_webhook_n8n(n8n_url)
    if esito == "inattivo":
        note.append("Il workflow n8n risulta NON attivo: il webhook è giusto ma va attivato prima del go-live.")

    status, corpo = _http("POST", f"{base}/instance/create", {
        "instanceName": cid,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
    }, headers)
    if status not in (200, 201):
        if "already" in corpo.lower() or status == 403:
            note.append(f"Istanza '{cid}' già esistente su Evolution: riuso quella.")
        else:
            raise WizardError(f"creazione istanza fallita ({status}): {corpo[:200]}")

    status, corpo = _http("POST", f"{base}/webhook/set/{cid}", {
        "webhook": {"enabled": True, "url": n8n_url, "events": ["MESSAGES_UPSERT"]},
    }, headers)
    if status not in (200, 201):
        # alcune versioni di Evolution vogliono il corpo piatto
        status, corpo = _http("POST", f"{base}/webhook/set/{cid}", {
            "enabled": True, "url": n8n_url, "events": ["MESSAGES_UPSERT"],
        }, headers)
        if status not in (200, 201):
            raise WizardError(f"webhook non impostato ({status}): {corpo[:200]}")

    salva_qr(base, evo_key, cid, qr_path, note)
    return note


def salva_qr(base: str, evo_key: str, cid: str, qr_path: Path, note: list[str]) -> None:
    status, corpo = _http("GET", f"{base}/instance/connect/{cid}", None, {"apikey": evo_key})
    try:
        b64 = json.loads(corpo).get("base64") or ""
    except json.JSONDecodeError:
        b64 = ""
    if status == 200 and b64.startswith("data:image"):
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        qr_path.write_bytes(base64.b64decode(b64.split(",", 1)[1]))
        note.append(f"QR salvato in {qr_path} — SCADE IN <1 MINUTO: rigenera con --solo-qr quando serve.")
    else:
        note.append("QR non disponibile ora (istanza forse già connessa). Rigenera con --solo-qr.")


# --- checklist ------------------------------------------------------------------

def stampa_checklist(dati: dict, token: str, note_evolution: list[str]) -> None:
    cid = dati["client_id"]
    print(f"""
{'=' * 72}
CLIENTE '{cid}' CREATO — attivo: false, il bot NON risponde ancora.
{'=' * 72}

Fatto in automatico:
  - vault/clienti/{cid}/ (orari, parametri calendario ed escalation già compilati)
  - blocco in config/clienti.json (agenda token: {token})
  - agenda titolare: {dati['backend_url']}/{cid}/agenda?token={token}""")
    for n in note_evolution:
        print(f"  - {n}")
    print(f"""
DA FARE A MANO, in quest'ordine:

 1. Compila col materiale del cliente i file del vault rimasti col segnaposto <<...>>:
    servizi.md, faq.md, brand-voice.md, vincoli.md, obiettivi.md
    (verifica_coerenza BLOCCA il go-live finché ce ne sono)
 2. Backup delle chat WhatsApp del cliente + consenso scritto
    (vault/_SISTEMA/Onboarding commerciale.md, Fase 4 — rischio ban accettato SOLO così)
 3. Fai scansionare il QR dal telefono del cliente
    (WhatsApp -> Dispositivi collegati; rigenera al momento: --solo-qr --client-id {cid})
 4. Canale voce: numero Twilio + bundle di registrazione + deviazione di chiamata
    dal numero del cliente (vault/_SISTEMA/Setup canale voce.md)
 5. Avvia la richiesta 360dialog in parallelo (uscita dal rischio Evolution)
 6. Sito/landing con GiassAI (per ora manuale, si automatizza in Fase 2)
 7. Test in bianco: attiva il workflow n8n, scrivi tu dal tuo numero, verifica
    risposta dal vault + prenotazione + escalation, poi disattiva
 8. GO-LIVE: metti "attivo": true in config/clienti.json e pusha (Railway rideploya)
 9. Primi 2 giorni: guarda gli eventi ogni sera
    GET {dati['backend_url']}/{cid}/eventi (con X-API-Key)
""")


# --- main -----------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Onboarding nuovo cliente Segretaria AaaS")
    p.add_argument("--client-id", required=True, help="kebab-case, es. studio-rossi")
    p.add_argument("--nome", help="nome dell'attività, es. 'Studio Dentistico Rossi'")
    p.add_argument("--whatsapp", help="numero WhatsApp dell'ATTIVITÀ (il numero del bot)")
    p.add_argument("--titolare", help="numero PERSONALE del titolare (riceve le escalation)")
    p.add_argument("--orari", default=ORARI_DEFAULT, help=f"default: {ORARI_DEFAULT}")
    p.add_argument("--durata-slot-min", type=int, default=30)
    p.add_argument("--capienza-per-slot", type=int, default=1)
    p.add_argument("--anticipo-min-ore", type=int, default=2)
    p.add_argument("--anticipo-max-giorni", type=int, default=90)
    p.add_argument("--buffer-min", type=int, default=0)
    p.add_argument("--backend-url", default=BACKEND_URL_DEFAULT)
    p.add_argument("--evolution", action="store_true",
                   help="crea anche istanza+webhook+QR (serve EVOLUTION_URL/EVOLUTION_API_KEY)")
    p.add_argument("--solo-qr", action="store_true", help="rigenera solo il QR e esci")
    args = p.parse_args()

    import os

    evo_url = os.getenv("EVOLUTION_URL", "")
    evo_key = os.getenv("EVOLUTION_API_KEY", "")
    n8n_url = os.getenv("N8N_WEBHOOK_URL", N8N_WEBHOOK_DEFAULT)
    qr_path = ROOT / "scripts" / "qr" / f"{args.client_id}.png"

    if args.solo_qr:
        if not (evo_url and evo_key):
            print("[X] --solo-qr richiede EVOLUTION_URL e EVOLUTION_API_KEY")
            return 1
        note: list[str] = []
        salva_qr(evo_url.rstrip("/"), evo_key, args.client_id, qr_path, note)
        for n in note:
            print(f"  - {n}")
        return 0

    # kebab-case obbligatorio solo alla CREAZIONE: --solo-qr deve funzionare anche con
    # le istanze legacy fuori convenzione (es. 'SegretariaOnline').
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.client_id):
        print(f"[X] client_id non valido: '{args.client_id}' (kebab-case, es. studio-rossi)")
        return 1

    if not (args.nome and args.whatsapp and args.titolare):
        print("[X] servono --nome, --whatsapp e --titolare")
        return 1

    dati = {
        "client_id": args.client_id,
        "nome": args.nome,
        "whatsapp": solo_cifre(args.whatsapp),
        "titolare": solo_cifre(args.titolare),
        "orari_apertura": parse_orari(args.orari),
        "durata_slot_min": args.durata_slot_min,
        "capienza_per_slot": args.capienza_per_slot,
        "anticipo_min_ore": args.anticipo_min_ore,
        "anticipo_max_giorni": args.anticipo_max_giorni,
        "buffer_min": args.buffer_min,
        "backend_url": args.backend_url.rstrip("/"),
    }
    if not dati["whatsapp"] or not dati["titolare"]:
        print("[X] numeri whatsapp/titolare non validi")
        return 1
    if dati["whatsapp"] == dati["titolare"]:
        # I messaggi dal numero dell'istanza risultano 'da_me' e vengono scartati:
        # il titolare non riceverebbe avvisi utilizzabili né potrebbe usare RIATTIVA.
        print("[X] il numero del titolare NON può essere lo stesso dell'attività")
        return 1

    try:
        crea_vault(ROOT, dati)
        token = aggiungi_config(ROOT, dati)
        verifica_config_caricabile(ROOT)

        note_evolution: list[str] = []
        if args.evolution:
            if not (evo_url and evo_key):
                raise WizardError("--evolution richiede EVOLUTION_URL e EVOLUTION_API_KEY")
            note_evolution = setup_evolution(dati, evo_url, evo_key, n8n_url, qr_path)
        else:
            note_evolution = ["Step Evolution SALTATO (rilancia con --evolution quando vuoi creare l'istanza)."]
    except WizardError as e:
        print(f"[X] {e}")
        return 1

    stampa_checklist(dati, token, note_evolution)
    return 0


if __name__ == "__main__":
    sys.exit(main())
