# Assistente operativo Telegram — @QuisvapoBot (Fase 1)

Console personale di Marco su Telegram per Quisvapo e Svapro. Servizio **separato** dal bot
principale (`app.py`): gira in un proprio container, **non lo tocca** e non interferisce con
gli alert al gruppo. Riceve i messaggi che Marco scrive in privato a @QuisvapoBot
(long-polling `getUpdates`) e risponde con Groq, avendo in pasto il contesto (vault Quisvapo
+ nota Svapro) e strumenti di sola lettura.

## Fasi
- **Fase 1 (questa):** sola lettura — info/stato, consulta vault, ultime telefonate, ricerca
  prodotti, chiacchierata. Non modifica nulla.
- Fase 2: autocritica voce+bot + approvazione in chat.
- Fase 3: comandi che modificano (con conferma).

## Sicurezza
Risponde SOLO all'utente `ALLOWED_USERNAME` (default `MannaccBudd`). Gli altri vengono ignorati.

## Perche' non usa un webhook
@QuisvapoBot oggi **solo invia** (il bot principale non riceve nulla via Telegram). Questo
servizio usa il long-polling `getUpdates`, che NON entra in conflitto con i `sendMessage`
del bot principale ne' del watchdog. Niente webhook da configurare.
⚠️ Non avviare due processi che fanno `getUpdates` sullo stesso token: solo QUESTO servizio
deve fare polling.

## Deploy (sul server, accanto al bot principale)

```bash
# 1. porta i file sul server (repo o scp) in /opt/assistente-telegram/
#    servono: assistente_telegram.py, Dockerfile, e una copia del vault:
mkdir -p /opt/assistente-telegram/vault_quisvapo
cp <repo>/assistente/assistente_telegram.py /opt/assistente-telegram/
cp <repo>/assistente/Dockerfile /opt/assistente-telegram/
cp <repo>/vault/clienti/quisvapo/*.md /opt/assistente-telegram/vault_quisvapo/

# 2. crea prod.env dai valori (TELEGRAM_BOT_TOKEN e GROQ_API_KEY come nel bot principale)
cd /opt/assistente-telegram
cp <repo>/assistente/prod.env.example prod.env && nano prod.env

# 3. build + run (rete coolify per raggiungere gli stessi servizi; nessuna porta pubblica)
docker build -t assistente-telegram:1.0 .
docker run -d --name assistente-telegram --restart unless-stopped \
  --network coolify --env-file prod.env assistente-telegram:1.0

# 4. verifica: scrivi a @QuisvapoBot in privato e guarda i log
docker logs -f assistente-telegram
```

Per aggiornare il codice: ricostruire l'immagine e rifare `docker rm -f` + `docker run`.
Non serve toccare il container principale.
