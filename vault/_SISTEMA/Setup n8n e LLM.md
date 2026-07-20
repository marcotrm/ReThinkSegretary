---
tipo: procedura
aggiornato_il: 2026-07-14
---

# Setup n8n + LLM (Together) — si fa UNA volta sola

Da [[🏠 HOME]]. Questa procedura **non si ripete per ogni cliente**: il workflow è uno solo e serve
tutti. Per aggiungere un cliente si tocca solo `config/clienti.json` e il suo vault.

Ordine: **LLM → n8n Variables → import workflow → Evolution → test → accensione.**

---

## 1. LLM — Together (il "cervello" della classificazione)

Serve a due cose: capire **cosa vuole** chi scrive (classificazione, temperature 0, JSON) e
**scrivere la risposta** partendo dal vault. Costa pochissimo: sono messaggi corti, poche migliaia
di token l'uno.

1. Crea l'account su **together.ai** e genera una **API key**.
2. Carica un minimo di credito (bastano pochi euro per il pilota).
3. Prendi nota di tre valori:

| Cosa | Valore |
|---|---|
| Endpoint | `https://api.together.xyz/v1/chat/completions` |
| Modello | un Llama 3.3 70B Instruct (nome esatto **da copiare dalla dashboard**, es. `meta-llama/Llama-3.3-70B-Instruct-Turbo`) |
| API key | quella generata al punto 1 |

> [!warning] Verifica il JSON mode
> Il nodo di classificazione usa `response_format: {type: "json_object"}`. **Non tutti i modelli su
> Together lo supportano.** Fai una prova con `curl` (sotto): se il modello risponde con del testo
> invece che con JSON puro, cambia modello — non aggirare il problema.

Prova che la chiave e il modello funzionino, **prima** di toccare n8n:

```bash
curl https://api.together.xyz/v1/chat/completions \
  -H "Authorization: Bearer LA_TUA_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "IL_MODELLO",
    "temperature": 0,
    "response_format": {"type": "json_object"},
    "messages": [
      {"role":"system","content":"Rispondi SOLO con JSON: {\"intento\":\"...\",\"confidenza\":0.0}"},
      {"role":"user","content":"buongiorno avete posto giovedì?"}
    ]
  }'
```

Deve tornare qualcosa come `{"intento":"prenota","confidenza":0.9}`. Se torna una frase, il modello
non va bene per questo uso.

**Alternativa:** Groq (`https://api.groq.com/openai/v1/chat/completions`) è più veloce e ha un piano
gratuito generoso. L'API è identica (OpenAI-compatibile): cambia solo `LLM_URL`, `LLM_API_KEY` e
`LLM_MODEL`. Il workflow non si tocca.

---

## 2. n8n — le variabili d'ambiente (NON le "Variables")

> [!warning] Le Variables di n8n non funzionano sulla nostra istanza
> `Settings → Variables` è una funzionalità **a licenza**: su questa istanza `$vars` è sempre
> vuoto, senza dare errore. Il workflow usa quindi `$env`, cioè le **variabili d'ambiente del
> servizio n8n su Railway**.

Vai su **Railway → servizio n8n → Variables** e aggiungi:

| Variabile | Valore |
|---|---|
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` ← **senza questa, n8n nega l'accesso alle env dai nodi Code e non funziona niente** |
| `BACKEND_URL` | `https://web-production-63865.up.railway.app` |
| `BACKEND_API_KEY` | la `API_KEY` del backend (quella su Railway) |
| `LLM_URL` | `https://api.together.xyz/v1/chat/completions` |
| `LLM_API_KEY` | la key Together |
| `LLM_MODEL` | il modello copiato dalla dashboard |
| `EVOLUTION_URL` | l'URL della tua Evolution API (es. `https://evolution.xxx.up.railway.app`) |
| `EVOLUTION_API_KEY` | la chiave di Evolution |
| `NIAMARKETING_WHATSAPP` | il numero WhatsApp di NiaMarketing: riceve TUTTI gli avvisi di escalation, in copia al titolare |
| `LLM_FALLBACK_URL` | endpoint del provider di riserva (es. OpenRouter: `https://openrouter.ai/api/v1/chat/completions`) |
| `LLM_FALLBACK_KEY` | la key del provider di riserva |
| `LLM_FALLBACK_MODEL` | modello di riserva (es. `meta-llama/llama-3.3-70b-instruct`); se vuoto usa `LLM_MODEL` |

**Verifica subito che il backend risponda:**

```bash
curl -H "X-API-Key: LA_API_KEY" \
  "https://web-production-63865.up.railway.app/health"
```

---

## 3. Escalation su WhatsApp

Niente Slack: l'avviso di escalation parte **dall'istanza Evolution del cliente stesso** verso
due numeri WhatsApp — il **titolare** (`escalation.whatsapp` in `config/clienti.json`) e
**NiaMarketing** (`NIAMARKETING_WHATSAPP` nelle variabili n8n). Zero servizi in più.

L'avviso contiene motivo, messaggio originale del cliente, il **link all'agenda del giorno**
(`/{client_id}/agenda?token=…`, token in `escalation.agenda_token`) e l'istruzione pronta:
il titolare risponde **`RIATTIVA <numero>`** nella stessa chat e il bot riparte per quel cliente.

> [!warning] Il numero del titolare NON può essere quello dell'istanza
> Se `escalation.whatsapp` è lo stesso numero collegato all'istanza Evolution, i suoi messaggi
> risultano `da_me` e il filtro li scarta: né avvisi letti come comandi, né RIATTIVA. Serve il
> numero **personale** del titolare, diverso da quello dell'attività.

Se un invio fallisce, il workflow logga l'evento `avviso_non_inviato` (con il destinatario) —
controllalo con `GET /{client_id}/eventi`. Il bot va in pausa comunque, PRIMA dell'invio.

---

## 4. Importare il workflow

1. n8n → Workflows → **Import from File** → `n8n/workflow-segretaria.json`
2. **NON attivarlo.** Prima si testa a mano (punto 6).
3. Apri il nodo **Messaggio in arrivo** e copia l'**URL del webhook di test** (in alto, tab *Test*).

---

## 5. Evolution API — collegare il numero del cliente

1. Crea un'**istanza** su Evolution. Chiamala **come il `client_id`** (es. `studio-rossi`): è il
   nome che va anche in `config/clienti.json` → `canali.whatsapp.instance`.
2. Genera il **QR code** e fallo scansionare **dal telefono del cliente**
   (WhatsApp → Dispositivi collegati → Collega dispositivo).
   ⚠️ Prima: **backup delle chat** e **consenso scritto** — vedi [[Onboarding commerciale]] Fase 4.
3. Configura il **webhook** dell'istanza verso l'URL n8n del punto 4, evento **`messages.upsert`**.
4. In `config/clienti.json` il `phone_id` del cliente è il suo numero in formato `39...`
   (senza `+`, senza spazi).

---

## 6. Test — prima di attivare

**Test 1: il workflow gira a vuoto.** In n8n premi *Test workflow*, poi manda un messaggio WhatsApp
vero al numero del cliente. Deve passare per tutti i nodi. Guarda cosa esce da ogni nodo:

- `Risolvi cliente dal numero` → deve tornare il `client_id` giusto. Se dà **404**, il numero in
  `config/clienti.json` non corrisponde a quello su cui è arrivato il messaggio.
- `Classifica intento` → deve tornare JSON, non una frase.
- `Prepara invio` → guarda il testo che sta per mandare. **È qui che vedi se il vault è buono.**

**Test 2: i casi che devono fallire.** Manda, uno alla volta:

| Messaggio | Cosa deve succedere |
|---|---|
| "a che ora aprite?" | risponde con gli orari del vault |
| "quanto costa [servizio]?" | risponde col prezzo del vault |
| "vorrei un appuntamento giovedì" | propone slot **veri** dal calendario |
| "mi fate schifo, voglio i soldi indietro" | **escalation** + avviso WhatsApp (titolare + NiaMarketing) + bot in pausa |
| "ho un dolore fortissimo" (dentista) | **escalation**, mai un consiglio medico |
| "fate [servizio che non offrono]?" | dice **no**, non "vediamo cosa possiamo fare" |

**Test 3: la prenotazione esiste davvero.**

```bash
curl -H "X-API-Key: LA_API_KEY" \
  "https://web-production-63865.up.railway.app/CLIENT_ID/prenotazioni"
```

Se il bot ha *detto* di aver prenotato ma qui non c'è niente, **fermati**: è il bug peggiore
possibile — il cliente si presenta e non è in agenda.

**Test 4: la riattivazione del bot.** Dopo l'escalation il bot tace. Riattivalo:

```bash
curl -X POST -H "X-API-Key: LA_API_KEY" \
  "https://web-production-63865.up.railway.app/CLIENT_ID/riattiva-bot/NUMERO"
```

---

## 7. Accensione

- [ ] Tutti i test sopra passati
- [ ] Prenotazioni di test **cancellate** dal calendario
- [ ] `attivo: true` in `config/clienti.json` → push (Railway ridepoloya da solo)
- [ ] Workflow n8n **Active**
- [ ] Primi due giorni: guarda gli eventi ogni sera
      (`GET /{client_id}/eventi`) e gli avvisi di escalation su WhatsApp

## 8. I primi giorni

Ogni escalation è una **domanda che il vault non copriva**. Prendila, scrivi la risposta giusta in
`faq.md`, e la volta dopo il bot la gestisce da solo. Questa è la curatela: è il servizio che vendi,
non "l'AI che gira". Vedi [[Come si compila un vault]].
