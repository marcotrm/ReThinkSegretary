# Calendar service

Microservizio FastAPI multi-tenant. Un'istanza serve **tutti** i clienti: il tenant si risolve dal
path `/{client_id}/`, la sua configurazione da `config/clienti.json`. Nessun cliente è cablato nel
codice.

## Moduli

| File | Responsabilità |
|---|---|
| `calendar_service.py` | HTTP: endpoint, auth, validazione, risoluzione tenant |
| `slots.py` | Regole di disponibilità (orari, buffer, anticipo, capienza) |
| `storage.py` | Persistenza: `InMemoryStorage` (test) e `PostgresStorage` (Railway) |
| `config_loader.py` | Lettura e validazione di `config/clienti.json` |

La regola importante: **`prenota` riusa la stessa funzione di `disponibilita`** (`slot_prenotabile`).
Il servizio non può proporre un orario che poi rifiuterebbe — sarebbe il modo più veloce per far
fare a una segretaria AI una figuraccia con un cliente vero.

## Endpoint

Tutti richiedono l'header `X-API-Key` (tranne `/health`).

```
GET  /health
GET  /{client_id}/disponibilita?da=2026-09-07&a=2026-09-14&durata_min=45&limite=3
POST /{client_id}/prenota      {servizio, nome_cliente, telefono, inizio, durata_min?, note?}
POST /{client_id}/sposta       {prenotazione_id, nuovo_inizio}
POST /{client_id}/cancella     {prenotazione_id}
GET  /{client_id}/prenotazioni?da=&a=&includi_cancellate=false
```

Codici di risposta rilevanti:

- `404` cliente non configurato / prenotazione inesistente
- `403` cliente non `attivo` in config
- `409` slot occupato, fuori orario, giorno di chiusura, anticipo non rispettato
- `401` API key mancante o errata

Gli orari senza fuso vengono interpretati come **ora locale del cliente** (`Europe/Rome`); in
risposta sono sempre ISO-8601 con offset.

## Locale

```bash
pip install -r requirements.txt
python -m pytest -q                      # 26 test, nessun database richiesto
uvicorn calendar_service:app --reload    # http://127.0.0.1:8000/docs
```

Senza `DATABASE_URL` usa lo storage in memoria: comodo per provare, **inutilizzabile in
produzione** (le prenotazioni spariscono al riavvio).

## Railway

1. Nuovo servizio dal repo. **Root Directory: lascia la root**, non `/calendar` — il servizio deve
   poter leggere `config/clienti.json`, che sta un livello sopra. Il `Procfile` in root ci pensa.
2. Aggiungi il plugin **Postgres**.
3. Variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `API_KEY` = chiave generata (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
4. Deploy, poi verifica: `GET /health` deve rispondere `"storage": "PostgresStorage"`.
   Se dice `InMemoryStorage`, `DATABASE_URL` non è arrivata.

Lo schema Postgres viene creato al primo avvio (`CREATE TABLE IF NOT EXISTS`): nessuna migration
manuale.
