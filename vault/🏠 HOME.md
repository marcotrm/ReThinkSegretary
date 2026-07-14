---
tipo: dashboard
aggiornato_il: 2026-07-14
---

# 🏠 Segretaria AaaS — Home

La knowledge base dei clienti. **Questo vault è la fonte di verità del sistema**: i prompt
dell'agent vocale, le risposte su WhatsApp e la config del calendario derivano da qui.
Se cambi un comportamento, si parte sempre da una nota di questo vault — mai dal codice.

## Clienti

| Cliente | Stato | Settore | Ultima curatela | Scheda |
|---|---|---|---|---|
| Studio Dentistico Sorriso | 🟡 test | dentista | 2026-07-14 | [[📍 Studio Dentistico Sorriso]] |
| Salone Bellezza | 🟡 test | parrucchiere | 2026-07-14 | [[📍 Salone Bellezza]] |

Legenda stato: 🟢 in produzione · 🟡 test/pilota · 🔴 sospeso · ⚪ in onboarding

## Operazioni

- [[Checklist onboarding]] — i 6 passi per attivare un cliente nuovo
- [[Come si compila un vault]] — dove pescare il materiale e cosa scriverci
- Cartella `_TEMPLATE/` — gli 8 file da copiare per un cliente nuovo.
  ⚠️ Non modificarli per un singolo cliente: si modifica la copia, non l'originale.

## Le tre regole che non si rompono

1. **Il vault è la fonte di verità.** Il codice deriva da qui. Mai il contrario.
2. **Un solo workflow per tutti i clienti.** Il `client_id` decide cosa caricare a runtime.
   Se ti ritrovi a duplicare un workflow per un cliente, è un errore.
3. **Mai collegare il bot al numero storico del cliente.** Solo numeri nuovi dedicati
   (il numero storico su Evolution API rischia il ban da Meta, e ci si gioca il cliente).

## Dove stanno le altre cose

Il vault è dentro il repo `ReThinkSegretary`, accanto al codice:

- `config/clienti.json` — mapping numero → cliente, e la config calendario derivata dai vault
- `calendar/` — il microservizio che prende gli appuntamenti
- `n8n/` — il workflow multi-tenant di WhatsApp

Dopo aver modificato un vault, gira `python scripts/verifica_coerenza.py`: dice se la config
si è disallineata da quello che c'è scritto qui.
