# Assistente operativo Telegram (Fase 1) — servizio SEPARATO dal bot principale.
# Nessuna dipendenza esterna: solo standard library (urllib). Immagine minima.
FROM python:3.12-slim

WORKDIR /app
COPY assistente_telegram.py /app/
# il vault quisvapo viene copiato dentro l'immagine (contesto dell'assistente)
COPY vault_quisvapo/ /app/vault_quisvapo/

ENV VAULT_DIR=/app/vault_quisvapo
CMD ["python", "assistente_telegram.py"]
