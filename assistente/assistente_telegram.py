#!/usr/bin/env python3
"""Assistente operativo di Marco su Telegram (@QuisvapoBot) — FASE 1: sola lettura.

Servizio SEPARATO dal bot principale (app.py): non lo tocca, non puo' rompere gli alert
del gruppo. Riceve i messaggi che Marco scrive in privato a @QuisvapoBot (long-polling),
risponde con Groq avendo in pasto TUTTO il contesto (vault Quisvapo + nota Svapro) e puo'
leggere lo stato (ultime telefonate della voce, ricerca prodotti). NON modifica niente:
i comandi che cambiano le cose arrivano nella Fase 3.

Sicurezza: risponde SOLO all'utente autorizzato (ALLOWED_USERNAME, default MannaccBudd).

Env richieste:
  TELEGRAM_BOT_TOKEN   token di @QuisvapoBot (gia' nel container principale)
  GROQ_API_KEY         chiave Groq
  GROQ_MODEL           modello Groq (default llama-3.3-70b-versatile)
  ELEVENLABS_API_KEY   per leggere le telefonate della voce
  ELEVEN_AGENT_ID      agent voce (default agent_2201ky21r7vqe329fd186nwmaees)
  BOT_API_URL          default https://bot-api.quisvapo.app
  BOT_API_KEY          X-API-Key dei tool (cerca/negozi)
  ALLOWED_USERNAME     default MannaccBudd
  VAULT_DIR            cartella col vault quisvapo (default ./vault_quisvapo)
"""
import os
import json
import glob
import time
import urllib.request
import urllib.error
import urllib.parse

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
EL_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
EL_AGENT = os.environ.get("ELEVEN_AGENT_ID", "agent_2201ky21r7vqe329fd186nwmaees")
BOT_API_URL = os.environ.get("BOT_API_URL", "https://bot-api.quisvapo.app").rstrip("/")
BOT_API_KEY = os.environ.get("BOT_API_KEY", "")
ALLOWED = os.environ.get("ALLOWED_USERNAME", "MannaccBudd").lstrip("@").lower()
VAULT_DIR = os.environ.get("VAULT_DIR", "./vault_quisvapo")

TG = f"https://api.telegram.org/bot{TG_TOKEN}"
UA = "Mozilla/5.0 (assistente-quisvapo)"


# ---------------------------------------------------------------- http helpers
def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _post(url, payload, headers=None, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------------------------------------------------------------- contesto
def file_vault_disponibili():
    return sorted(os.path.basename(f) for f in glob.glob(os.path.join(VAULT_DIR, "*.md")))


def leggi_file_vault(nome: str) -> str:
    nome = os.path.basename(nome)
    if not nome.endswith(".md"):
        nome += ".md"
    path = os.path.join(VAULT_DIR, nome)
    if not os.path.exists(path):
        return f"File non trovato. Disponibili: {', '.join(file_vault_disponibili())}"
    with open(path, encoding="utf-8") as fh:
        return fh.read()[:6000]


# Riassunto COMPATTO nel prompt (per non bruciare token ogni turno). I dettagli si
# leggono su richiesta con lo strumento leggi_vault.
DIGEST = (
    "Quisvapo = catena di negozi di sigarette elettroniche/svapo, cliente pilota della "
    "Segretaria AI di NiaMarketing. Due canali automatici: VOCE (telefono, agent ElevenLabs) "
    "e WHATSAPP (bot 'Nico'). Rete: ~40 negozi. Campania (Napoli, Caserta, Marcianise, "
    "Maddaloni, Aversa, Caivano, Afragola, Giugliano, Portici, Acerra, Nola, Sorrento, "
    "Pontecagnano...), Roma e Formia, Puglia (Andria, Trani, Brindisi), Calabria (Maida), "
    "Nord (Milano, Torino, Affi/Verona, Montebello/Pavia, Casalecchio/Bologna, Savignano/"
    "Romagna). Orari lun-sab 9-18, domenica chiuso. Shop online quisvapo.com (h24). "
    "Regola d'oro: prezzi/disponibilita' SOLO dallo strumento 'cerca'; niente ordini o "
    "pagamenti al telefono; escalation ai clienti su WhatsApp 351 708 9407. "
    "SVAPRO ('Nico') = assistente WhatsApp nello stesso container, con autocritica /learn "
    "che scrive lezioni in voicebot_lessons."
)

SYSTEM = (
    "Sei l'assistente operativo personale di Marco (NiaMarketing) per i progetti Quisvapo e "
    "Svapro. Parli in italiano, diretto e concreto, come un collega tecnico fidato. Aiuti "
    "Marco a capire come vanno la voce e il bot WhatsApp e rispondi a domande su negozi/"
    "prodotti/orari. Hai un riassunto qui sotto; per i DETTAGLI (faq, servizi, brand-voice, "
    "vincoli, escalation, orari, ecc.) usa lo strumento leggi_vault col nome del file. Per lo "
    "stato delle telefonate usa ultime_chiamate; per prezzi/disponibilita' usa cerca. "
    "IMPORTANTE (Fase 1): sei in SOLA LETTURA. NON puoi cambiare configurazioni, modelli, "
    "prompt o dati: se Marco chiede di modificare qualcosa, spiega cosa faresti e digli che "
    "l'esecuzione dei comandi arrivera' in una fase successiva. Se non sai un dato, dillo, "
    "non inventarlo.\n\n=== RIASSUNTO ===\n" + DIGEST +
    "\n\nFile di dettaglio consultabili con leggi_vault: " + ", ".join(file_vault_disponibili())
)


# ---------------------------------------------------------------- strumenti (read-only)
def tool_ultime_chiamate(n: int = 5) -> str:
    if not EL_KEY:
        return "Chiave ElevenLabs non configurata: non posso leggere le telefonate."
    try:
        d = _get(
            f"https://api.elevenlabs.io/v1/convai/conversations?agent_id={EL_AGENT}&page_size={n}",
            headers={"xi-api-key": EL_KEY},
        )
        out = []
        for c in d.get("conversations", [])[:n]:
            cid = c.get("conversation_id")
            dur = c.get("call_duration_secs")
            msgs = c.get("message_count")
            det = _get(
                f"https://api.elevenlabs.io/v1/convai/conversations/{cid}",
                headers={"xi-api-key": EL_KEY},
            )
            turns = []
            for t in det.get("transcript", [])[:12]:
                m = t.get("message")
                if m:
                    turns.append(f"{t.get('role')}: {m}")
            out.append(f"[chiamata {dur}s, {msgs} msg]\n" + "\n".join(turns))
        return "\n\n".join(out) if out else "Nessuna telefonata recente."
    except Exception as e:  # noqa: BLE001
        return f"Errore leggendo le telefonate: {e}"


def tool_negozi() -> str:
    try:
        d = _get(f"{BOT_API_URL}/negozi", headers={"X-API-Key": BOT_API_KEY})
        negs = d.get("negozi", d if isinstance(d, list) else [])
        righe = [f"{x.get('nome')} ({x.get('citta')})" for x in negs]
        return "Negozi attivi (" + str(len(righe)) + "): " + "; ".join(righe)
    except Exception as e:  # noqa: BLE001
        return f"Errore elenco negozi: {e}"


def tool_cerca(nome: str, negozio: str = "") -> str:
    try:
        url = f"{BOT_API_URL}/cerca?nome={urllib.parse.quote(nome)}&limit=5"
        if negozio:
            url += f"&negozio={urllib.parse.quote(negozio)}"
        d = _get(url, headers={"X-API-Key": BOT_API_KEY})
        return json.dumps(d, ensure_ascii=False)[:1500]
    except Exception as e:  # noqa: BLE001
        return f"Errore ricerca: {e}"


TOOLS = [
    {"type": "function", "function": {
        "name": "leggi_vault",
        "description": "Legge un file del vault Quisvapo per avere i dettagli (es. faq, servizi, "
                       "brand-voice, vincoli, escalation, orari, prenotazioni, obiettivi).",
        "parameters": {"type": "object", "properties": {
            "file": {"type": "string", "description": "nome del file, es. 'faq' o 'servizi.md'"}},
            "required": ["file"]},
    }},
    {"type": "function", "function": {
        "name": "ultime_chiamate",
        "description": "Legge le ultime telefonate ricevute dall'assistente vocale (transcript).",
        "parameters": {"type": "object", "properties": {
            "n": {"type": "integer", "description": "quante chiamate (default 5)"}}},
    }},
    {"type": "function", "function": {
        "name": "negozi",
        "description": "Elenco aggiornato dei negozi Quisvapo con citta'. Usalo SEMPRE quando "
                       "Marco chiede se c'e' un negozio in una citta', invece di indovinare.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "cerca",
        "description": "Cerca un prodotto nel gestionale Quisvapo (prezzo/disponibilita').",
        "parameters": {"type": "object", "properties": {
            "nome": {"type": "string"}, "negozio": {"type": "string"}},
            "required": ["nome"]},
    }},
]


def esegui_tool(name, args):
    if name == "leggi_vault":
        return leggi_file_vault(args.get("file", ""))
    if name == "negozi":
        return tool_negozi()
    if name == "ultime_chiamate":
        return tool_ultime_chiamate(int(args.get("n", 5)))
    if name == "cerca":
        return tool_cerca(args.get("nome", ""), args.get("negozio", ""))
    return "strumento sconosciuto"


# ---------------------------------------------------------------- groq
def groq_chat(messages):
    payload = {"model": GROQ_MODEL, "messages": messages, "tools": TOOLS,
               "temperature": 0.3, "max_tokens": 800}
    d = _post("https://api.groq.com/openai/v1/chat/completions", payload,
              headers={"Authorization": f"Bearer {GROQ_KEY}"})
    return d["choices"][0]["message"]


def rispondi(storia, testo_utente):
    messages = [{"role": "system", "content": SYSTEM}] + storia + \
               [{"role": "user", "content": testo_utente}]
    for _ in range(4):  # max 4 giri di tool
        msg = groq_chat(messages)
        tcs = msg.get("tool_calls")
        if not tcs:
            return msg.get("content", "").strip() or "(nessuna risposta)"
        messages.append(msg)
        for tc in tcs:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:  # noqa: BLE001
                args = {}
            res = esegui_tool(fn, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "name": fn, "content": res[:4000]})
    return "Ho fatto troppe ricerche di fila, riprova a chiedermelo piu' semplice."


# ---------------------------------------------------------------- telegram
def tg_send(chat_id, text):
    for i in range(0, len(text), 3800):  # Telegram limita a 4096
        _post(f"{TG}/sendMessage", {"chat_id": chat_id, "text": text[i:i + 3800]})


_STORIA = {}  # chat_id -> lista messaggi (ultimi turni)


def gestisci(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        return
    frm = msg.get("from", {})
    username = (frm.get("username") or "").lower()
    chat_id = msg["chat"]["id"]
    if username != ALLOWED:
        print(f"[skip] messaggio da @{username} (non autorizzato), chat_id={chat_id}", flush=True)
        return
    print(f"[msg] @{username} chat_id={chat_id}: {msg['text']!r}", flush=True)
    storia = _STORIA.setdefault(chat_id, [])
    try:
        risposta = rispondi(storia[-8:], msg["text"])
    except Exception as e:  # noqa: BLE001
        risposta = f"Errore interno: {e}"
        print(f"[err] {e}", flush=True)
    storia.append({"role": "user", "content": msg["text"]})
    storia.append({"role": "assistant", "content": risposta})
    tg_send(chat_id, risposta)


def main():
    print(f"[avvio] assistente Fase 1. Autorizzato: @{ALLOWED}. Modello: {GROQ_MODEL}.", flush=True)
    print(f"[avvio] system prompt: {len(SYSTEM)} caratteri, keyterms contesto pronti.", flush=True)
    offset = None
    while True:
        try:
            url = f"{TG}/getUpdates?timeout=50"
            if offset is not None:
                url += f"&offset={offset}"
            d = _get(url, timeout=60)
            for up in d.get("result", []):
                offset = up["update_id"] + 1
                gestisci(up)
        except urllib.error.HTTPError as e:
            print(f"[http] {e.code}: {e.read().decode()[:200]}", flush=True)
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print(f"[loop] {e}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
