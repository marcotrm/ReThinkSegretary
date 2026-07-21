---
client_id: quisvapo
file: orari
aggiornato_il: 2026-07-20
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Orari — Quisvapo

## Orari di apertura (tutti i punti vendita)

| Giorno | Apertura | Chiusura | Pausa | Chiuso |
|-----------|----------|----------|-----------------|--------|
| Lunedì | 09:00 | 18:00 | — | no |
| Martedì | 09:00 | 18:00 | — | no |
| Mercoledì | 09:00 | 18:00 | — | no |
| Giovedì | 09:00 | 18:00 | — | no |
| Venerdì | 09:00 | 18:00 | — | no |
| Sabato | 09:00 | 18:00 | — | no |
| Domenica | — | — | — | sì |

> Questa tabella è la fonte per `orari_apertura` nella config calendario. Se cambia qui, va
> rigenerata la config del cliente.

## Punti vendita (città)

Caserta, Napoli, Caivano, Aversa, Afragola, Acerra, Marcianise, Maddaloni, Capodrise,
Andria, Roma e altre. L'elenco aggiornato dei negozi attivi arriva dallo strumento
`negozi` (API prodotti): usare quello, non questo file, per dire al cliente il punto
vendita più vicino.

Lo **shop online** è quisvapo.com, attivo h24.

## Chiusure straordinarie

Nessuna programmata al momento.

## Festività osservate

- Tutte le festività nazionali italiane: negozi chiusi

## Reperibilità fuori orario

- L'assistente telefonico risponde h24, ma fuori orario può dare solo informazioni:
  per gli acquisti rimanda allo shop online quisvapo.com o al negozio dal giorno dopo.
- Per richieste che deve seguire una persona: WhatsApp 351 708 9407 (lì risponde il
  sistema WhatsApp di Quisvapo, gestito a parte).
