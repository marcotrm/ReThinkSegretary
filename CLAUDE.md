# CLAUDE.md — Sistema Segretaria AaaS (NiaMarketing)

Questo file è il contesto che leggi a ogni sessione. Leggilo per intero prima di fare qualsiasi cosa.
Se qualcosa qui è in conflitto con una richiesta in chat, chiedi conferma prima di procedere.

## COS'È QUESTO SISTEMA

Servizio "Segretaria AI" venduto ai clienti di NiaMarketing (~400€/mese). Risponde ai clienti finali
su WhatsApp e al telefono h24, prende appuntamenti, e passa all'umano i casi che non sa gestire.

**Modello di business: AaaS (Agent as a Service).** Il valore ricorrente è la curatela continua della
conoscenza del cliente (vault), non "l'AI che gira".

## ARCHITETTURA

**Principio guida: MULTI-TENANT.** Un solo template, tanti clienti. Non si duplica il workflow per
cliente. Un unico workflow n8n serve tutti; il `client_id` (ricavato dal numero in arrivo) decide
quale vault/config caricare a runtime.
**Se ti trovi a creare un workflow per singolo cliente, FERMATI: è un errore.**

### Canali e componenti

- **WhatsApp (risposte)** → Evolution API (fase pilota) / 360dialog (quando pronto). Evolution
  risponde con un timer 5–15 min per sembrare umano.

  **Numero: decisione di Marco (14/07/2026), cambia la regola precedente.** Durante il pilota si
  usa il **numero storico del cliente** su Evolution, come ponte, mentre 360dialog viene attivato
  in parallelo. Il rischio ban Meta esiste e resta reale: è accettato consapevolmente perché
  rispondiamo **solo a chi scrive per primo** (mai messaggi a freddo o massivi), che è il profilo
  di rischio più basso per Evolution. Paletti obbligatori — backup delle chat prima di collegare,
  consenso scritto del cliente, 360dialog avviato subito, stacco immediato al primo avviso di
  WhatsApp: vedi `vault/_SISTEMA/Onboarding commerciale.md`, Fase 4.
  Se il cliente preferisce zero rischi, si parte con un numero nuovo dedicato.
- **Template risposte + calendario** → n8n (workflow multi-tenant).
- **Voce** → Deepgram (speech-to-text) + ElevenLabs (text-to-speech) + Twilio (numero). Chiamate
  deviate dal numero del cliente (es. TIM) al numero Twilio.
- **Calendario** → microservizio FastAPI (`calendar_service.py`), multi-tenant via `/{client_id}/`.
  Endpoint: `disponibilita`, `prenota`, `sposta`, `cancella`, `prenotazioni`.
- **Knowledge base** → vault Obsidian, una cartella `.md` per cliente. È la **FONTE DI VERITÀ**.
- **Cervello classificazione intento WhatsApp** → Llama (economico, temperature 0, JSON mode, solo
  classificazione). Soglia confidenza < 0.6 → escalation umana.

**Deploy:** Railway (stesso pattern di ScrapingNIA / GiassAI).

## STRUTTURA CARTELLA

```
/vault/                      # knowledge base
  _TEMPLATE/                 # 8 file .md da copiare per ogni cliente
  clienti/<client_id>/       # vault compilato per cliente
/n8n/
  workflow-segretaria.json   # IL workflow multi-tenant (uno solo)
/calendar/
  calendar_service.py        # microservizio calendario
/config/
  clienti.json               # mapping: phone_id → client_id, vault, calendar_url, agent_id
CLAUDE.md                    # questo file
```

## FILE DEL VAULT PER CLIENTE (8)

`orari.md`, `servizi.md`, `faq.md`, `brand-voice.md`, `vincoli.md`, `prenotazioni.md`,
`escalation.md`, `obiettivi.md`.

## REGOLE DI LAVORO (importanti)

1. **PLAN-FIRST.** Prima di scrivere/modificare file, presenta il piano e aspetta approvazione.
   Metodo "SvaPro" già collaudato. Vale DOPPIO per il workflow n8n in produzione: una modifica
   sbagliata rompe le risposte ai clienti veri.
2. **NON toccare la produzione da solo.** Prepara la modifica, testala se possibile, mostrala.
   L'applicazione su sistema live la decide/fa Marco.
3. **Config, non codice.** Per aggiungere/aggiornare un cliente, modifica il VAULT e la CONFIG di
   mapping. NON modificare il workflow n8n per un singolo cliente.
4. **Il vault è la fonte di verità.** Prompt Agent ElevenLabs, config calendario e risposte derivano
   dal vault. Se aggiorni un comportamento, parti dal vault.
5. **Azioni che NON puoi fare** (le fa Marco): login/acquisti su 360dialog, Twilio, ElevenLabs;
   Embedded Signup Meta (deve farlo il cliente); invio di messaggi reali; modifiche a impostazioni
   account. Prepara tutto il contorno, il tasto finale lo preme lui.
6. **Test prima di consegnare.** Se scrivi codice (calendar service, script, workflow), fallo girare
   e verificane il funzionamento prima di dire "fatto".

## OPERAZIONI RICORRENTI

### Onboarding nuovo cliente

1. Copia `/vault/_TEMPLATE/` in `/vault/clienti/<client_id>/`
2. Compila gli 8 `.md` col materiale fornito (call, sito, vecchie chat, recensioni)
3. Genera il prompt Agent ElevenLabs da: `brand-voice` + `orari` + `faq` + `vincoli`
4. Imposta la config calendario (orari, giorni chiusura, capienza_per_slot, durata_slot_min)
5. Aggiungi la riga di mapping in `/config/clienti.json`
6. Consegna la checklist di cosa deve fare Marco a mano (numeri, account, deviazione chiamate)

### Aggiornare un cliente esistente

1. Leggi il vault attuale del cliente
2. Confronta con quello che è cambiato
3. Presenta il DIFF ragionato: cosa cambia, cosa impatta (prompt? config? calendario?)
4. Aspetta ok, poi applica

### Debug

Leggi il componente coinvolto (workflow/calendar/config), individua la causa, proponi il fix,
testalo, poi mostralo.

## STATO ATTUALE / TODO

Backend live su Railway: `https://web-production-63865.up.railway.app` (Postgres agganciato).

- [x] ~~Storage calendario: da stub in memoria a Postgres~~ → fatto, `PostgresStorage`.
      L'in-memory resta solo per i test.
- [x] ~~Logging eventi strutturato~~ → tabella `eventi` + `GET/POST /{client_id}/eventi`.
- [x] ~~Pausa-bot per utente dopo un'escalation~~ → `POST /{client_id}/pausa-bot/{telefono}`.
- [x] ~~Escalation: invio dell'avviso al titolare~~ → **WhatsApp** (deciso da Marco, 20/07/2026:
      niente Slack né Telegram). Doppio invio dall'istanza Evolution del cliente: titolare
      (`escalation.whatsapp` in config) **e** NiaMarketing (`NIAMARKETING_WHATSAPP` in env n8n).
      L'avviso include il link all'agenda del giorno. Il bot va in pausa PRIMA dell'avviso.
      ⚠️ `escalation.whatsapp` deve essere diverso dal numero dell'istanza (altrimenti `da_me`).
- [x] ~~Riattivazione del bot~~ → il titolare risponde `RIATTIVA <numero>` nella chat della
      propria attività; solo i numeri di escalation sono autorizzati.
- [x] ~~Agenda giornaliera per il titolare~~ → `GET /{client_id}/agenda?token=…` (HTML mobile,
      sola lettura, token per cliente in `escalation.agenda_token`).
- [x] ~~Fallback LLM~~ → se il primario fallisce (es. Groq in quota), i nodi classificazione e
      risposta ritentano su `LLM_FALLBACK_*` (es. OpenRouter) prima di escalare.
- [ ] **Lato Marco (per attivare il tutto):** chiave Groq **dedicata** al progetto col piano Dev
      (quella gratis è condivisa con Nico/SvaPro e muore ogni giorno), variabili n8n
      `NIAMARKETING_WHATSAPP` + `LLM_FALLBACK_URL/KEY/MODEL`, poi 15 minuti di test sul suo
      numero prima del primo cliente vero (il percorso "risposta dal vault" su WhatsApp non è
      ancora mai stato esercitato).
- [ ] Migrazione Evolution → 360dialog. Il workflow è già pronto per entrambi: si cambia
      `canali.whatsapp.provider` in config, non si tocca n8n.
- [ ] Tool dell'Agent ElevenLabs → vedi `vault/_SISTEMA/Setup canale voce.md`.
- [ ] **Da decidere:** Deepgram serve davvero? ElevenLabs Conversational AI fa già lo
      speech-to-text al suo interno. Verificare prima di pagarlo due volte.
- [ ] Spostamento appuntamento da WhatsApp: oggi va in escalation.

## COMANDI UTILI

```bash
python scripts/verifica_coerenza.py     # vault e config allineati? wikilink rotti?
cd calendar && python -m pytest -q      # 47 test del backend
node n8n/test_workflow.mjs              # workflow importabile + logica di decisione
```

## CONTESTO NIAMARKETING

Agenzia italiana. Stack esistente: ScrapingNIA (CRM/scraping), GiassAI (SaaS landing AI),
Evolution API + n8n (WhatsApp), tutto su Railway. Preferenza forte: Claude Code per tutte le
modifiche al codice, plan-first con approvazione prima di scrivere file.
**Lingua di lavoro: italiano.**
