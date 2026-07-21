---
client_id: quisvapo
file: prenotazioni
aggiornato_il: 2026-07-20
consumato_da: [config-calendario, prompt-agent, workflow-n8n]
---

# Prenotazioni — Quisvapo

**Questo tenant NON gestisce prenotazioni.** Quisvapo è una catena di negozi: al telefono
si danno informazioni, non si prendono appuntamenti. I parametri qui sotto esistono solo
perché la config calendario è obbligatoria per ogni tenant — il calendario resta inutilizzato.

## Parametri calendario

| Parametro            | Valore        | Note                                              |
|----------------------|---------------|---------------------------------------------------|
| `durata_slot_min`    | 30        | granularità della griglia, in minuti              |
| `capienza_per_slot`  | 1         | quante prenotazioni in parallelo (poltrone/sale)  |
| `anticipo_min_ore`   | 2         | non si prenota a meno di X ore                    |
| `anticipo_max_giorni`| 90        | non si prenota oltre X giorni                     |
| `buffer_min`         | 0         | pausa tra un appuntamento e il successivo         |
| `timezone`           | `Europe/Rome` |                                                   |

> Gli orari di apertura e le chiusure NON si duplicano qui: stanno in `orari.md`.

## Dati richiesti per prenotare

Non applicabile: la AI non prenota nulla per questo tenant.

## Flusso

Se un cliente chiede di "prenotare" o mettere da parte un prodotto:

1. Spiegare che al telefono non si prendono ordini né prenotazioni
2. Indirizzare a: shop online quisvapo.com, oppure WhatsApp 351 708 9407

## Disdette e spostamenti

Non applicabile.

## Promemoria

Non applicabile.

## Overbooking / lista d'attesa

Non applicabile.
