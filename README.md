# ReThinkSegretary — Segretaria AaaS (NiaMarketing)

Servizio "Segretaria AI" multi-tenant: risponde ai clienti finali su WhatsApp e al telefono h24,
prende appuntamenti, passa all'umano i casi che non sa gestire.

**Leggi [CLAUDE.md](CLAUDE.md) prima di toccare qualsiasi cosa.** Contiene architettura, regole di
lavoro e procedure ricorrenti.

## Principio non negoziabile

**Un solo template, tanti clienti.** Un unico workflow n8n serve tutti i tenant; il `client_id`,
ricavato dal numero in arrivo, decide quale vault e quale config caricare a runtime.
Se stai per creare un workflow (o un servizio) dedicato a un singolo cliente, ti stai sbagliando.

## Struttura

```
vault/
  _TEMPLATE/        8 file .md — base per ogni nuovo cliente
  clienti/<id>/     knowledge base compilata (FONTE DI VERITÀ)
n8n/
  workflow-segretaria.json    IL workflow multi-tenant (uno solo)   [DA FARE]
calendar/
  calendar_service.py         microservizio FastAPI /{client_id}/   [DA FARE]
config/
  clienti.json      mapping numero → client_id, vault, calendario, escalation
```

## Stato

| Componente | Stato |
|---|---|
| Vault `_TEMPLATE` (8 file) | ✅ pronto |
| `config/clienti.json` + schema | ✅ pronto (solo tenant `demo`, disattivo) |
| Calendar service (FastAPI) | ⬜ da scrivere |
| Workflow n8n | ⬜ da scrivere |
| Escalation reale + logging | ⬜ da scrivere |

Deploy previsto su Railway, come ScrapingNIA e GiassAI.

## Sicurezza

Nessun segreto nel repo. Token Evolution / Twilio / ElevenLabs / Deepgram e stringa Postgres vanno
in variabili d'ambiente su Railway.
