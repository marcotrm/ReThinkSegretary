# config/clienti.json — mapping multi-tenant

Questo file è **l'unico punto** in cui si aggiunge o si modifica un cliente. Il workflow n8n e il
calendar service lo leggono a runtime: non si tocca il codice per un singolo cliente.

## Come funziona la risoluzione del tenant

1. Arriva un messaggio WhatsApp (o una chiamata) su un numero.
2. Il sistema cerca il numero in `canali.whatsapp.phone_id` (o `canali.voce.numero`).
3. Trova il `client_id` → carica `vault_path`, `calendar_url`, `calendario`, `escalation`.
4. Se **nessun cliente corrisponde** al numero: **non rispondere**, logga l'evento. Mai rispondere
   con un tenant di default — significherebbe dare a un cliente le informazioni di un altro.

## Campi

| Campo | Tipo | Note |
|---|---|---|
| `client_id` | string | Slug univoco, minuscolo, `[a-z0-9-]`. È anche il nome della cartella vault e il segmento URL del calendario. |
| `nome` | string | Ragione sociale, solo per noi. |
| `attivo` | bool | `false` = il sistema ignora i messaggi in arrivo. Usalo per pausa/sospensione. |
| `canali.whatsapp.provider` | enum | `evolution` (pilota) o `360dialog` (target). |
| `canali.whatsapp.phone_id` | string | **Numero NUOVO dedicato**, in E.164 senza `+`. **Mai il numero storico del cliente** (rischio ban Meta). |
| `canali.whatsapp.delay_risposta_sec` | obj | Ritardo casuale prima di rispondere, per sembrare umani. Default 300–900 (5–15 min). |
| `canali.voce.elevenlabs_agent_id` | string | ID dell'Agent generato dal vault. |
| `vault_path` | path | Cartella della knowledge base. Fonte di verità. |
| `calendar_url` | url | Base URL già comprensiva di `/{client_id}`. |
| `calendario.*` | obj | Copia 1:1 dai parametri di `vault/clienti/<id>/prenotazioni.md` e `orari.md`. |
| `escalation.soglia_confidenza` | float | Sotto questa soglia → umano. Default `0.6`. |

## Regole

- **Nessun segreto qui dentro.** API key, token Evolution/Twilio/ElevenLabs vanno in variabili
  d'ambiente su Railway. Questo file va su git.
- `calendario` e `orari_apertura` **derivano dal vault**. Se cambiano gli orari, si aggiorna prima
  `orari.md`, poi si rigenera questa sezione — mai il contrario.
- Prima di committare: `python -c "import json;json.load(open('config/clienti.json'))"`.

## Aggiungere un cliente

Vedi la procedura di onboarding in `CLAUDE.md`. In sintesi: copia `_TEMPLATE` → compila gli 8 `.md`
→ aggiungi la voce qui → consegna a Marco la checklist delle azioni manuali (numeri, account,
deviazione chiamate).
