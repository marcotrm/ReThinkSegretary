#!/usr/bin/env python3
"""Assistente operativo di Marco su Telegram (@QuisvapoConsoleBot) — v2.

Fasi attive:
  1. Chat + info (vault digest, negozi/cerca dal gestionale, telefonate ElevenLabs)
  2. Autocritica VOCE con approvazione: "autocritica" -> propone lezioni -> "approva"
     -> le applica al prompt dell'agent ElevenLabs (sezione LEZIONI APPRESE).
  3. Comandi voce con conferma: cambia LLM, aggiungi keyterm, aggiungi regola al prompt.
  4. Monitor: ogni 5 min controlla gestionale/API; se un servizio cade (o torna su)
     avvisa Marco in privato.
  5. Auto-update: "/update <url> <sha256>" scarica il nuovo codice, verifica lo sha
     e si riavvia. Niente piu' terminale per gli aggiornamenti.

Sicurezza: risponde SOLO a ALLOWED_USERNAME. Ogni azione che modifica chiede conferma.
"""
import os
import sys
import json
import time
import hashlib
import threading
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
# --- per l'autocritica del bot WhatsApp (v3) ---
EVOLUTION_URL = os.environ.get("EVOLUTION_URL", "").rstrip("/")
EVOLUTION_APIKEY = os.environ.get("EVOLUTION_APIKEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "svapro")
LESSONS_DATABASE_URL = os.environ.get("LESSONS_DATABASE_URL", "")

TG = f"https://api.telegram.org/bot{TG_TOKEN}"
UA = "Mozilla/5.0 (assistente-quisvapo)"
SELF_PATH = os.path.abspath(__file__)


# ---------------------------------------------------------------- http helpers
def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get_raw(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post(url, payload, headers=None, timeout=90, method="POST"):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------------------------------------------------------------- contesto
DIGEST = (
    "Quisvapo = catena di negozi di sigarette elettroniche/svapo, cliente pilota della "
    "Segretaria AI di NiaMarketing. Due canali automatici: VOCE (telefono, agent ElevenLabs "
    "'Ester') e WHATSAPP (chatbot su n8n->container). Rete ~40 negozi: Campania (Napoli, "
    "Caserta, Marcianise, Maddaloni, Aversa, Caivano, Afragola, Giugliano, Portici, Acerra, "
    "Nola, Sorrento, Pontecagnano...), Roma e Formia, Puglia (Andria, Trani, Brindisi), "
    "Calabria (Maida), Nord (Milano, Torino, Affi/Verona, Montebello/Pavia, Casalecchio/"
    "Bologna, Savignano/Romagna). Orari lun-sab 9-18, dom chiuso. Shop online quisvapo.com. "
    "Regola d'oro: prezzi/disponibilita' SOLO dallo strumento 'cerca'. Escalation clienti su "
    "WhatsApp 351 708 9407. SVAPRO = gestionale/CRM della catena (stesso container), con "
    "autocritica /learn su voicebot_lessons."
)

SYSTEM = (
    "Sei l'assistente operativo personale di Marco (NiaMarketing) per Quisvapo e Svapro: il "
    "suo braccio destro quando non e' in ufficio. Parli italiano, diretto e concreto. Sai "
    "fare: report e consigli su voce/bot/business, controllare lo stato dei servizi, leggere "
    "le telefonate, cercare prodotti e negozi. Puoi anche MODIFICARE la voce (modello LLM, "
    "keyterm, regole del prompt) usando gli strumenti prepara_*: questi NON applicano subito, "
    "preparano l'azione e Marco deve scrivere APPROVA. Per le autocritiche digli di scrivere "
    "'autocritica' (voce+bot), 'autocritica voce' o 'autocritica bot'. Se un dato non lo "
    "sai, dillo. Non inventare mai numeri.\n\n"
    "=== CONTESTO ===\n" + DIGEST
)


# ---------------------------------------------------------------- strumenti read
def tool_negozi() -> str:
    try:
        d = _get(f"{BOT_API_URL}/negozi", headers={"X-API-Key": BOT_API_KEY})
        negs = d.get("negozi", d if isinstance(d, list) else [])
        return "Negozi attivi (%d): %s" % (len(negs), "; ".join(
            f"{x.get('nome')} ({x.get('citta')})" for x in negs))
    except Exception as e:  # noqa: BLE001
        return f"Errore elenco negozi: {e}"


def tool_cerca(nome: str, negozio: str = "") -> str:
    try:
        url = f"{BOT_API_URL}/cerca?nome={urllib.parse.quote(nome)}&limit=5"
        if negozio:
            url += f"&negozio={urllib.parse.quote(negozio)}"
        return json.dumps(_get(url, headers={"X-API-Key": BOT_API_KEY}),
                          ensure_ascii=False)[:1500]
    except Exception as e:  # noqa: BLE001
        return f"Errore ricerca: {e}"


def _transcript(cid: str, max_turns: int = 40) -> str:
    det = _get(f"https://api.elevenlabs.io/v1/convai/conversations/{cid}",
               headers={"xi-api-key": EL_KEY})
    turns = []
    for t in det.get("transcript", [])[:max_turns]:
        m = t.get("message")
        if m:
            turns.append(f"{t.get('role')}: {m}")
    return "\n".join(turns)


def tool_ultime_chiamate(n: int = 5) -> str:
    if not EL_KEY:
        return "Chiave ElevenLabs non configurata."
    try:
        d = _get(f"https://api.elevenlabs.io/v1/convai/conversations?agent_id={EL_AGENT}"
                 f"&page_size={min(n, 10)}", headers={"xi-api-key": EL_KEY})
        out = []
        for c in d.get("conversations", [])[:n]:
            out.append(f"[{c.get('call_duration_secs')}s, {c.get('message_count')} msg]\n"
                       + _transcript(c["conversation_id"], 14))
        return "\n\n".join(out) or "Nessuna telefonata recente."
    except Exception as e:  # noqa: BLE001
        return f"Errore leggendo le telefonate: {e}"


def tool_stato_servizi() -> str:
    return "\n".join(f"{'OK' if ok else 'GIU’'} - {nome}: {det}"
                     for nome, ok, det in _check_servizi())


def tool_config_voce() -> str:
    try:
        cc = _get(f"https://api.elevenlabs.io/v1/convai/agents/{EL_AGENT}",
                  headers={"xi-api-key": EL_KEY})["conversation_config"]
        p = cc["agent"]["prompt"]
        return (f"LLM: {p.get('llm')} | keyterms: {len(cc['asr'].get('keywords') or [])} | "
                f"turn_timeout: {cc['turn'].get('turn_timeout')} | prompt: "
                f"{len(p.get('prompt') or '')} caratteri")
    except Exception as e:  # noqa: BLE001
        return f"Errore lettura config voce: {e}"


# ---------------------------------------------------------------- azioni con conferma
_PENDING = {}  # chat_id -> {"tipo":..., "dati":..., "descr":...}


def _prepara(chat_id, tipo, dati, descr):
    _PENDING[chat_id] = {"tipo": tipo, "dati": dati, "descr": descr}
    return f"AZIONE PREPARATA: {descr}\nRispondi APPROVA per eseguire, ANNULLA per lasciar perdere."


def _voce_get():
    return _get(f"https://api.elevenlabs.io/v1/convai/agents/{EL_AGENT}",
                headers={"xi-api-key": EL_KEY})["conversation_config"]


def _voce_patch(payload):
    _post(f"https://api.elevenlabs.io/v1/convai/agents/{EL_AGENT}",
          {"conversation_config": payload}, headers={"xi-api-key": EL_KEY}, method="PATCH")


def _esegui(chat_id) -> str:
    p = _PENDING.pop(chat_id, None)
    if not p:
        return "Non c'e' nessuna azione in attesa di approvazione."
    tipo, dati = p["tipo"], p["dati"]
    try:
        if tipo == "voce_llm":
            _voce_patch({"agent": {"prompt": {"llm": dati["llm"]}}})
            return f"Fatto: modello voce -> {dati['llm']}."
        if tipo == "voce_keyterm":
            kw = _voce_get()["asr"].get("keywords") or []
            nuovi = [k for k in dati["keyterms"] if k not in kw]
            if not nuovi:
                return "Quei keyterm ci sono gia', niente da fare."
            _voce_patch({"asr": {"keywords": kw + nuovi}})
            return f"Fatto: aggiunti keyterm {', '.join(nuovi)} (totale {len(kw) + len(nuovi)})."
        if tipo == "voce_regola":
            cc = _voce_get()
            prompt = cc["agent"]["prompt"].get("prompt") or ""
            blocco = "\n\nLEZIONI APPRESE (approvate da Marco):"
            if blocco not in prompt:
                prompt += blocco
            for r in dati["regole"]:
                prompt += f"\n- {r}"
            _voce_patch({"agent": {"prompt": {"prompt": prompt}}})
            return f"Fatto: {len(dati['regole'])} regola/e aggiunte al prompt della voce."
        if tipo == "wa_lezioni":
            with _lessons_conn() as lc:
                for les in dati["lezioni"]:
                    lc.execute("INSERT INTO voicebot_lessons (source, lesson) "
                               "VALUES ('console', %s)", (les,))
                lc.commit()
            return (f"Fatto: {len(dati['lezioni'])} lezione/i salvate per il bot WhatsApp. "
                    "il chatbot le usera' dalle prossime risposte (cache 5 min).")
        return f"Tipo azione sconosciuto: {tipo}"
    except Exception as e:  # noqa: BLE001
        return f"Errore eseguendo l'azione: {e}"


# ---------------------------------------------------------------- autocritica voce
_AUTOCRITICA_SYS = (
    "Sei il supervisore severo di un assistente telefonico (voce) di una catena di negozi di "
    "svapo. Ti do le trascrizioni delle ultime telefonate e le regole gia' attive. Trova gli "
    "ERRORI VERI dell'assistente (nomi capiti male senza conferma, negozi inesistenti non "
    "corretti, risposte sbagliate, loop, informazioni inventate) e proponi al massimo 3 "
    "LEZIONI nuove: regole brevi, operative, in italiano, che evitino il ripetersi "
    "dell'errore. Non ripetere regole gia' attive. Se non ci sono errori, lessons=[]. "
    'Rispondi SOLO JSON: {"lessons": ["..."], "report": "riassunto brevissimo degli errori"}'
)


def autocritica_voce(chat_id, n_chiamate: int = 8) -> str:
    try:
        d = _get(f"https://api.elevenlabs.io/v1/convai/conversations?agent_id={EL_AGENT}"
                 f"&page_size={n_chiamate}", headers={"xi-api-key": EL_KEY})
        convs = d.get("conversations", [])
        if not convs:
            return "Nessuna telefonata da analizzare."
        blocchi = []
        for c in convs:
            t = _transcript(c["conversation_id"], 20)
            if t:
                blocchi.append(f"--- CHIAMATA ({c.get('call_duration_secs')}s) ---\n{t}")
        prompt_v = _voce_get()["agent"]["prompt"].get("prompt") or ""
        attive = prompt_v.split("LEZIONI APPRESE")[-1][:1200] if "LEZIONI APPRESE" in prompt_v else "(nessuna)"
        user = ("TRASCRIZIONI:\n" + "\n\n".join(blocchi)[:9000]
                + "\n\nLEZIONI GIA' ATTIVE (non ripeterle):\n" + attive)
        j = json.loads(_groq([{"role": "system", "content": _AUTOCRITICA_SYS},
                              {"role": "user", "content": user}], json_mode=True))
        lessons = [str(x).strip()[:300] for x in (j.get("lessons") or []) if str(x).strip()][:3]
        report = str(j.get("report") or "").strip()[:1200]
        if not lessons:
            return f"[VOCE] Autocritica su {len(blocchi)} chiamate: nessun errore rilevante.\n{report}"
        msg = _prepara(chat_id, "voce_regola", {"regole": lessons},
                       "applicare al prompt della voce queste lezioni:\n"
                       + "\n".join("• " + les for les in lessons))
        return f"[VOCE] Autocritica su {len(blocchi)} chiamate.\nErrori: {report}\n\n{msg}"
    except Exception as e:  # noqa: BLE001
        return f"Autocritica fallita: {e}"


# ---------------------------------------------------------------- autocritica bot WhatsApp
def _lessons_conn():
    import psycopg  # installato nell'immagine (v3)
    return psycopg.connect(LESSONS_DATABASE_URL)


def _wa_chats_recenti(ore: int = 24, max_chat: int = 12):
    """Legge i messaggi recenti dall'API Evolution e li raggruppa per conversazione."""
    body = {"where": {}, "limit": 400}
    d = _post(f"{EVOLUTION_URL}/chat/findMessages/{EVOLUTION_INSTANCE}", body,
              headers={"apikey": EVOLUTION_APIKEY})
    records = d.get("messages", {}).get("records", d if isinstance(d, list) else [])
    limite = time.time() - ore * 3600
    convs = {}
    for m in records:
        try:
            ts = int(m.get("messageTimestamp") or 0)
            if ts < limite:
                continue
            key = m.get("key", {})
            jid = key.get("remoteJid", "")
            if not jid or jid.endswith("@g.us"):
                continue  # niente gruppi
            mm = m.get("message") or {}
            testo = mm.get("conversation") or (mm.get("extendedTextMessage") or {}).get("text")
            if not testo:
                continue
            ruolo = "BOT" if key.get("fromMe") else "CLIENTE"
            convs.setdefault(jid, []).append((ts, f"{ruolo}: {str(testo)[:300]}"))
        except Exception:  # noqa: BLE001
            continue
    out = {}
    for jid, msgs in list(convs.items())[:max_chat]:
        msgs.sort()
        out[jid] = [t for _, t in msgs][-25:]
    return out


_WA_SYS = (
    "Sei il supervisore severo di un bot WhatsApp di una catena di negozi di svapo"
    ". Ti do le conversazioni recenti e le lezioni gia' attive. Trova gli ERRORI del "
    "bot (risposte sbagliate, informazioni inventate, tono sbagliato, domande ignorate) e "
    "proponi al massimo 3 LEZIONI nuove: regole brevi e operative in italiano. Non ripetere "
    "lezioni gia' attive. Se il bot ha lavorato bene, lessons=[]. "
    'Rispondi SOLO JSON: {"lessons": ["..."], "report": "riassunto brevissimo"}'
)


def autocritica_whatsapp(chat_id, ore: int = 24) -> str:
    if not (EVOLUTION_URL and EVOLUTION_APIKEY and LESSONS_DATABASE_URL):
        return ("[BOT] Mi mancano le chiavi Evolution/lezioni nell'ambiente: "
                "chiedi a Claude di aggiungerle.")
    try:
        convs = _wa_chats_recenti(ore)
        if not convs:
            return f"[BOT] Nessuna conversazione WhatsApp nelle ultime {ore} ore."
        with _lessons_conn() as lc:
            attive = [r[0] for r in lc.execute(
                "SELECT lesson FROM voicebot_lessons WHERE active ORDER BY id DESC LIMIT 40"
            ).fetchall()]
        blocchi = [f"--- CHAT {j[-6:]} ---\n" + "\n".join(m) for j, m in convs.items()]
        user = ("CONVERSAZIONI:\n" + "\n\n".join(blocchi)[:9000]
                + "\n\nLEZIONI GIA' ATTIVE (non ripeterle):\n"
                + ("\n".join("- " + x for x in attive) or "(nessuna)"))
        j = json.loads(_groq([{"role": "system", "content": _WA_SYS},
                              {"role": "user", "content": user}], json_mode=True))
        lessons = [str(x).strip()[:300] for x in (j.get("lessons") or []) if str(x).strip()][:3]
        report = str(j.get("report") or "").strip()[:1200]
        if not lessons:
            return f"[BOT] Autocritica su {len(convs)} chat: nessun errore rilevante.\n{report}"
        msg = _prepara(chat_id, "wa_lezioni", {"lezioni": lessons},
                       "salvare queste lezioni per il chatbot WhatsApp:\n"
                       + "\n".join("• " + les for les in lessons))
        return f"[BOT] Autocritica su {len(convs)} chat.\nErrori: {report}\n\n{msg}"
    except Exception as e:  # noqa: BLE001
        return f"[BOT] Autocritica fallita: {e}"


# ---------------------------------------------------------------- groq
def _groq(messages, temperature=0.3, max_tokens=800, tools=None, json_mode=False):
    payload = {"model": GROQ_MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        payload["tools"] = tools
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    for tentativo in range(3):
        try:
            d = _post("https://api.groq.com/openai/v1/chat/completions", payload,
                      headers={"Authorization": f"Bearer {GROQ_KEY}"})
            m = d["choices"][0]["message"]
            return m if tools else (m.get("content") or "")
        except urllib.error.HTTPError as e:
            corpo = ""
            try:
                corpo = e.read().decode()[:300]
            except Exception:  # noqa: BLE001
                pass
            if e.code == 429 and tentativo < 2:
                time.sleep(12)
                continue
            raise RuntimeError(
                f"groq HTTP {e.code} (modello={GROQ_MODEL}, chiave=...{GROQ_KEY[-6:]}): {corpo}")
    raise RuntimeError("groq: tentativi esauriti (429, quota al minuto finita)")


TOOLS = [
    {"type": "function", "function": {"name": "negozi",
        "description": "Elenco aggiornato dei negozi con citta'. Usalo SEMPRE per domande su "
                       "negozi/citta', mai indovinare.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "cerca",
        "description": "Cerca un prodotto nel gestionale (prezzo/disponibilita').",
        "parameters": {"type": "object", "properties": {
            "nome": {"type": "string"}, "negozio": {"type": "string"}},
            "required": ["nome"]}}},
    {"type": "function", "function": {"name": "ultime_chiamate",
        "description": "Trascrizioni delle ultime telefonate della voce.",
        "parameters": {"type": "object", "properties": {
            "n": {"type": "integer", "description": "quante (default 5)"}}}}},
    {"type": "function", "function": {"name": "stato_servizi",
        "description": "Controlla ORA lo stato di gestionale/API/voce. Usalo quando Marco "
                       "dice che qualcosa non va o chiede come stanno i servizi.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "config_voce",
        "description": "Configurazione attuale della voce (LLM, keyterms, tempi).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "prepara_cambio_llm",
        "description": "PREPARA il cambio del modello LLM della voce (poi Marco approva). "
                       "Modelli utili: gemini-2.0-flash (veloce), claude-sonnet-5 (preciso), "
                       "gemini-2.5-flash.",
        "parameters": {"type": "object", "properties": {
            "llm": {"type": "string"}}, "required": ["llm"]}}},
    {"type": "function", "function": {"name": "prepara_keyterm",
        "description": "PREPARA l'aggiunta di keyterm ASR alla voce (marchi/gusti che capisce "
                       "male). Poi Marco approva.",
        "parameters": {"type": "object", "properties": {
            "keyterms": {"type": "array", "items": {"type": "string"}}},
            "required": ["keyterms"]}}},
    {"type": "function", "function": {"name": "prepara_regola_prompt",
        "description": "PREPARA l'aggiunta di una o piu' regole al prompt della voce. "
                       "Poi Marco approva.",
        "parameters": {"type": "object", "properties": {
            "regole": {"type": "array", "items": {"type": "string"}}},
            "required": ["regole"]}}},
]


def esegui_tool(chat_id, name, args):
    if name == "negozi":
        return tool_negozi()
    if name == "cerca":
        return tool_cerca(args.get("nome", ""), args.get("negozio", ""))
    if name == "ultime_chiamate":
        return tool_ultime_chiamate(int(args.get("n", 5)))
    if name == "stato_servizi":
        return tool_stato_servizi()
    if name == "config_voce":
        return tool_config_voce()
    if name == "prepara_cambio_llm":
        return _prepara(chat_id, "voce_llm", {"llm": args["llm"]},
                        f"cambiare il modello della voce in {args['llm']}")
    if name == "prepara_keyterm":
        return _prepara(chat_id, "voce_keyterm", {"keyterms": args.get("keyterms") or []},
                        f"aggiungere keyterm: {', '.join(args.get('keyterms') or [])}")
    if name == "prepara_regola_prompt":
        return _prepara(chat_id, "voce_regola", {"regole": args.get("regole") or []},
                        "aggiungere al prompt voce:\n"
                        + "\n".join("• " + r for r in (args.get("regole") or [])))
    return "strumento sconosciuto"


def rispondi(chat_id, storia, testo):
    messages = [{"role": "system", "content": SYSTEM}] + storia + \
               [{"role": "user", "content": testo}]
    for _ in range(4):
        msg = _groq(messages, tools=TOOLS)
        tcs = msg.get("tool_calls")
        if not tcs:
            return (msg.get("content") or "").strip() or "(nessuna risposta)"
        messages.append(msg)
        for tc in tcs:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:  # noqa: BLE001
                args = {}
            res = esegui_tool(chat_id, tc["function"]["name"], args)
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "name": tc["function"]["name"], "content": str(res)[:4000]})
    return "Troppi passaggi, riprova con una domanda piu' semplice."


# ---------------------------------------------------------------- monitor
_MON_STATO = {}
_MON_CHAT = {"id": None}  # popolato al primo messaggio di Marco


def _check_servizi():
    esiti = []
    try:
        d = _get(f"{BOT_API_URL}/negozi", headers={"X-API-Key": BOT_API_KEY}, timeout=15)
        n = len(d.get("negozi", []))
        esiti.append(("Gestionale/API prodotti", n > 0, f"{n} negozi"))
    except Exception as e:  # noqa: BLE001
        esiti.append(("Gestionale/API prodotti", False, str(e)[:120]))
    try:
        _get(f"https://api.elevenlabs.io/v1/convai/agents/{EL_AGENT}",
             headers={"xi-api-key": EL_KEY}, timeout=15)
        esiti.append(("Voce (agent ElevenLabs)", True, "raggiungibile"))
    except Exception as e:  # noqa: BLE001
        esiti.append(("Voce (agent ElevenLabs)", False, str(e)[:120]))
    try:
        r = _get_raw("https://n8n.quisvapo.app/healthz", timeout=15)
        esiti.append(("n8n (bot WhatsApp)", b"ok" in r.lower(), "healthz ok"))
    except Exception as e:  # noqa: BLE001
        esiti.append(("n8n (bot WhatsApp)", False, str(e)[:120]))
    return esiti


def monitor_loop():
    time.sleep(30)
    while True:
        try:
            for nome, ok, det in _check_servizi():
                prima = _MON_STATO.get(nome)
                _MON_STATO[nome] = ok
                if prima is None:
                    continue
                if prima and not ok and _MON_CHAT["id"]:
                    tg_send(_MON_CHAT["id"], f"🔴 [MONITOR] {nome} sembra GIU': {det}\n"
                                             "Scrivimi 'stato' per ricontrollare o 'indaga' per i dettagli.")
                if (not prima) and ok and _MON_CHAT["id"]:
                    tg_send(_MON_CHAT["id"], f"🟢 [MONITOR] {nome} e' tornato su ({det}).")
        except Exception as e:  # noqa: BLE001
            print(f"[monitor] {e}", flush=True)
        time.sleep(300)


# ---------------------------------------------------------------- auto-update
def cmd_update(chat_id, testo) -> str:
    parti = testo.split()
    if len(parti) != 3:
        return "Uso: /update <url> <sha256>"
    url, sha = parti[1], parti[2].lower()
    try:
        blob = _get_raw(url, timeout=60)
        if hashlib.sha256(blob).hexdigest() != sha:
            return "SHA non combacia: aggiornamento RIFIUTATO (file corrotto o manomesso)."
        with open(SELF_PATH, "wb") as f:
            f.write(blob)
        tg_send(chat_id, "Codice verificato. Mi riavvio con la nuova versione...")
        os.execv(sys.executable, [sys.executable, SELF_PATH])
    except Exception as e:  # noqa: BLE001
        return f"Aggiornamento fallito: {e}"
    return ""  # mai raggiunto


# ---------------------------------------------------------------- telegram
def tg_send(chat_id, text):
    try:
        for i in range(0, len(text), 3800):
            _post(f"{TG}/sendMessage", {"chat_id": chat_id, "text": text[i:i + 3800]})
    except Exception as e:  # noqa: BLE001
        print(f"[tg_send] {e}", flush=True)


_STORIA = {}


def gestisci(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or "text" not in msg:
        return
    username = (msg.get("from", {}).get("username") or "").lower()
    chat_id = msg["chat"]["id"]
    if username != ALLOWED:
        print(f"[skip] @{username} non autorizzato", flush=True)
        return
    _MON_CHAT["id"] = chat_id
    testo = msg["text"].strip()
    print(f"[msg] @{username}: {testo!r}", flush=True)
    t = testo.lower()

    if t.startswith("/update"):
        r = cmd_update(chat_id, testo)
        if r:
            tg_send(chat_id, r)
        return
    if t in ("approva", "conferma", "si applica", "sì applica", "vai", "ok applica"):
        tg_send(chat_id, _esegui(chat_id))
        return
    if t in ("annulla", "no", "lascia perdere"):
        _PENDING.pop(chat_id, None)
        tg_send(chat_id, "Ok, annullato.")
        return
    if t in ("autocritica voce",):
        tg_send(chat_id, "Analizzo le ultime telefonate, un minuto...")
        tg_send(chat_id, autocritica_voce(chat_id))
        return
    if t in ("autocritica bot", "autocritica whatsapp"):
        tg_send(chat_id, "Analizzo le chat WhatsApp recenti, un minuto...")
        tg_send(chat_id, autocritica_whatsapp(chat_id))
        return
    if t == "autocritica":
        tg_send(chat_id, "Faccio l'autocritica di VOCE e BOT WhatsApp, un paio di minuti...")
        tg_send(chat_id, autocritica_voce(chat_id))
        tg_send(chat_id, autocritica_whatsapp(chat_id))
        tg_send(chat_id, "NB: se ci sono proposte per entrambi, APPROVA vale per l'ultima "
                         "mostrata. Approva una alla volta.")
        return
    if t == "stato":
        tg_send(chat_id, tool_stato_servizi())
        return

    storia = _STORIA.setdefault(chat_id, [])
    try:
        r = rispondi(chat_id, storia[-6:], testo)
    except Exception as e:  # noqa: BLE001
        r = f"Errore interno: {e}"
        print(f"[err] {e}", flush=True)
    storia.append({"role": "user", "content": testo})
    storia.append({"role": "assistant", "content": r})
    tg_send(chat_id, r)


def main():
    print(f"[avvio] assistente v2. Autorizzato: @{ALLOWED}. Modello: {GROQ_MODEL}.", flush=True)
    threading.Thread(target=monitor_loop, daemon=True).start()
    print("[avvio] monitor servizi attivo (ogni 5 min).", flush=True)
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
            print(f"[http] {e.code}: {e.read().decode()[:150]}", flush=True)
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print(f"[loop] {e}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
