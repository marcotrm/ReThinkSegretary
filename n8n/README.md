# Workflow n8n — Segretaria multi-tenant

**Un solo workflow per tutti i clienti.** Il `client_id` si ricava dal numero su cui arriva il
messaggio; vault, orari, soglie e provider si caricano a runtime dal backend.

> Se ti trovi a duplicare questo workflow per un cliente, o a scriverci dentro il nome di un
> cliente: **fermati, è un errore.** Il fix sta nel vault o in `config/clienti.json`.

## Il flusso

```
Webhook  →  Normalizza payload  →  Filtro  →  Risolvi cliente dal numero
                                                        │
                                          404/403 ──────┴──── STOP (non si risponde)
                                                        │
                            Carica vault + conversazione (dal backend)
                                                        │
                                   bot in pausa? ───────┴──── STOP (gestisce l'umano)
                                                        │
                                       Classifica intento (Llama, temp 0, JSON)
                                                        │
                                              Decidi cosa fare
                                    ┌───────────────────┼───────────────────┐
                              escalation            calendario           rispondi
                                    └───────────────────┼───────────────────┘
                                              Prepara invio (salva stato + logga)
                                                        │
                                          Attesa 5–15 min (sembrare umani)
                                                        │
                                          Quale provider? ──→ Evolution / 360dialog
```

## Le decisioni che contano

**Quando NON si risponde.** Numero di nessun cliente, cliente non attivo, bot in pausa dopo
un'escalation. In tutti e tre i casi il workflow tace. Rispondere "per sicurezza" con un tenant
di default significherebbe dare a un cliente la conoscenza di un altro.

**Quando si escala.** Confidenza sotto la soglia del cliente, reclamo, urgenza, LLM irraggiungibile,
LLM che risponde spazzatura, calendario in errore, più di 8 messaggi senza risolvere. La regola:
**nel dubbio non si improvvisa**. Dopo l'escalation il bot smette di rispondere a quell'utente
finché il titolare non lo riattiva.

**Non si conferma mai un appuntamento prima della risposta OK del backend.** Un appuntamento
confermato che non esiste è il danno peggiore che questo sistema possa fare a un cliente vero.

**Il provider è un ramo, non un cablaggio.** Evolution oggi, 360dialog domani: si cambia
`canali.whatsapp.provider` in `config/clienti.json` e il workflow non si tocca. Gli unici nodi che
conoscono i due provider sono `Normalizza payload` (in entrata) e `Quale provider?` (in uscita).

## Variabili d'ambiente (Railway → servizio n8n → Variables)

> Le "Variables" di n8n (`$vars`) sono a licenza e su questa istanza sono sempre vuote, senza
> dare errore. Si usano le **env del servizio n8n su Railway**, e serve
> `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` altrimenti i nodi Code non le vedono.

| Variabile | Valore |
|---|---|
| `BACKEND_URL` | `https://web-production-63865.up.railway.app` |
| `BACKEND_API_KEY` | la `API_KEY` del backend |
| `LLM_URL` | endpoint OpenAI-compatibile del provider Llama (es. Groq, Together) |
| `LLM_API_KEY` | chiave del provider |
| `LLM_MODEL` | es. `llama-3.3-70b-versatile` |
| `EVOLUTION_URL` | URL della tua Evolution API |
| `EVOLUTION_API_KEY` | chiave Evolution |
| `SLACK_BOT_TOKEN` | token `xoxb-…` dell'app Slack (scope `chat:write`) |
| `SLACK_CHANNEL_DEFAULT` | canale di riserva, es. `#segretaria-alert` |
| `D360_URL` | (solo alla migrazione) endpoint 360dialog |
| `D360_API_KEY` | (solo alla migrazione) chiave 360dialog |

**Nessun segreto sta nel JSON del workflow**: sono tutti riferimenti a `$env`.

## Escalation su Slack

Il canale è **per cliente**: `escalation.slack_channel` in `config/clienti.json`. Se manca, si usa
`SLACK_CHANNEL_DEFAULT` — un avviso non deve andare perso perché qualcuno ha scordato una riga
di config.

Ordine delle operazioni, e non è casuale: **prima si mette il bot in pausa, poi si avvisa.** Se
Slack fosse irraggiungibile, la AI deve smettere di rispondere lo stesso. Un avviso mancato è un
fastidio; una AI che continua a improvvisare su un reclamo è un cliente perso.

Se l'invio fallisce (anche nel modo subdolo in cui fallisce Slack: HTTP 200 con `ok: false`), viene
registrato un evento `avviso_non_inviato` — visibile su `GET /{client_id}/eventi`.

**Da fare su Slack** (lo fa Marco): crea un'app, scope `chat:write`, installala nel workspace,
invita il bot nel canale (`/invite @nome-bot`), copia il token `xoxb-…` nelle Variables di n8n.

## Import

1. n8n → Workflows → Import from File → `workflow-segretaria.json`
2. Imposta le Variables qui sopra
3. Configura il webhook su Evolution API (evento `messages.upsert`).

   > **Verifica l'URL prima di fidarti.** L'URL di produzione e' `/webhook/<path>` — NON quello
   > che include il `webhookId` (`/webhook/<webhookId>/<path>`), che l'API di n8n riporta ma che
   > non risponde. Con l'URL sbagliato Evolution consegna a un 404 e i messaggi spariscono senza
   > un errore da nessuna parte. Controlla cosi':
   >
   > ```bash
   > curl -s https://TUO-N8N/webhook/segretaria
   > # giusto  -> "not registered for GET requests. Did you mean to make a POST request?"
   > # sbagliato -> "The requested webhook ... is not registered"
   > ```
4. **Non attivarlo subito**: prima un test in esecuzione manuale con un messaggio finto

## Test

```bash
node n8n/test_workflow.mjs
```

Controlla che il JSON sia importabile (connessioni, nodi orfani), che nessun cliente sia cablato
dentro, ed esegue davvero la logica del nodo `Decidi cosa fare` contro i casi limite: LLM giù,
confidenza bassa, reclamo, urgenza, conversazione infinita.

## Cosa manca ancora

- **Invio dell'avviso di escalation al titolare.** Il testo è già pronto (`avviso_titolare`), manca
  il nodo che lo manda su WhatsApp o Slack — va collegato a un'istanza Evolution nostra, non del
  cliente.
- **Riattivazione del bot dopo un'escalation.** Oggi si fa chiamando
  `POST /{client_id}/riattiva-bot/{telefono}`. Serve un modo comodo per il titolare (es. un
  messaggio "riprendi" da un numero autorizzato).
- **Spostamento appuntamento**: per ora va in escalation invece di essere gestito.
- **Allegati** (audio, foto): ignorati.
