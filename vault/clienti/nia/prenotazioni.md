---
client_id: nia
file: prenotazioni
aggiornato_il: 2026-07-23
consumato_da: [config-calendario, prompt-agent, workflow-n8n]
---

# Prenotazioni — Nia — Call con Michele

Questo file è la fonte diretta della **config calendario** del cliente. I valori qui sotto vengono
copiati 1:1 in `/config/clienti.json → calendario`.

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

Ordine in cui la AI li chiede. Se ne manca uno, non prenota.

1. n/d (tenant interno Nia)
2. n/d (tenant interno Nia)
3. n/d (tenant interno Nia)
4. n/d (tenant interno Nia) (di solito già noto da WhatsApp)
5. n/d (tenant interno Nia)

## Flusso

1. Cliente chiede appuntamento
2. AI chiama `GET /{client_id}/disponibilita` con servizio e finestra temporale
3. AI propone **massimo n/d (tenant interno Nia) slot** alla volta
4. Cliente sceglie → AI chiama `POST /{client_id}/prenota`
5. **Solo dopo risposta OK del servizio** la AI conferma al cliente
6. AI manda il riepilogo: n/d (tenant interno Nia)

## Disdette e spostamenti

- Preavviso minimo per disdire: n/d (tenant interno Nia)
- Penale per mancata disdetta: n/d (tenant interno Nia)
- La AI può cancellare in autonomia? n/d (tenant interno Nia)
- La AI può spostare in autonomia? n/d (tenant interno Nia)
- Sotto il preavviso minimo: n/d (tenant interno Nia)

## Promemoria

- Promemoria automatico: n/d (tenant interno Nia), n/d (tenant interno Nia) ore prima
- Testo: n/d (tenant interno Nia)

## Overbooking / lista d'attesa

- n/d (tenant interno Nia)
- Lista d'attesa: n/d (tenant interno Nia)
