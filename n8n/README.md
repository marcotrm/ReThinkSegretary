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
                                 Comando dal titolare (RIATTIVA)? ──── esegue e STOP
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
| `LLM_URL` | endpoint OpenAI-compatibile del provider Llama primario (es. Groq) |
| `LLM_API_KEY` | chiave del provider — **dedicata a questo progetto**, non condivisa con altri bot |
| `LLM_MODEL` | es. `llama-3.3-70b-versatile` |
| `LLM_FALLBACK_URL` | endpoint del provider di riserva (es. OpenRouter), usato se il primario fallisce |
| `LLM_FALLBACK_KEY` | chiave del provider di riserva |
| `LLM_FALLBACK_MODEL` | modello di riserva; se vuoto si riusa `LLM_MODEL` |
| `EVOLUTION_URL` | URL della tua Evolution API |
| `EVOLUTION_API_KEY` | chiave Evolution |
| `NIAMARKETING_WHATSAPP` | numero WhatsApp di NiaMarketing: riceve ogni avviso di escalation in copia |
| `D360_URL` | (solo alla migrazione) endpoint 360dialog |
| `D360_API_KEY` | (solo alla migrazione) chiave 360dialog |

**Nessun segreto sta nel JSON del workflow**: sono tutti riferimenti a `$env`.

## Escalation su WhatsApp

L'avviso parte **dall'istanza Evolution del cliente stesso** verso due numeri: il **titolare**
(`escalation.whatsapp` in `config/clienti.json`) e **NiaMarketing** (`NIAMARKETING_WHATSAPP`).
Contiene motivo, messaggio originale, il link all'**agenda del giorno**
(`GET /{client_id}/agenda?token=…`, token in `escalation.agenda_token`) e l'istruzione
`RIATTIVA <numero>` pronta da copiare.

**Riattivazione**: il titolare (o NiaMarketing) risponde `RIATTIVA <numero>` nella chat della
propria attività; il nodo `Comando dal titolare (RIATTIVA)` riconosce il mittente autorizzato,
chiama `riattiva-bot` e conferma — subito, senza il ritardo "umano". Un comando non arriva mai
al classificatore; da qualunque altro numero, "riattiva" è un messaggio come un altro.

⚠️ `escalation.whatsapp` deve essere un numero **diverso** da quello collegato all'istanza:
i messaggi dal numero dell'istanza risultano `da_me` e il filtro li scarta.

Ordine delle operazioni, e non è casuale: **prima si mette il bot in pausa, poi si avvisa.** Se
Evolution fosse irraggiungibile, la AI deve smettere di rispondere lo stesso. Un avviso mancato è
un fastidio; una AI che continua a improvvisare su un reclamo è un cliente perso.

Ogni invio fallito registra un evento `avviso_non_inviato` con il destinatario — visibile su
`GET /{client_id}/eventi`.

## Fallback LLM

I due nodi LLM (classificazione e generazione risposta) provano il primario e, se fallisce
(429 di quota, 5xx, rete), ritentano **una volta** sul provider di riserva `LLM_FALLBACK_*` con
lo stesso identico prompt. Solo se falliscono entrambi si escala. Senza variabili di riserva
configurate il comportamento resta quello di prima: primario giù → escalation.

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

- **Spostamento appuntamento**: per ora va in escalation invece di essere gestito.
- **Allegati** (audio, foto): ignorati.
- **Avviso di escalation per clienti 360dialog**: oggi l'avviso viaggia via Evolution
  (istanza del cliente); alla migrazione andrà aggiunto l'invio via 360dialog.
