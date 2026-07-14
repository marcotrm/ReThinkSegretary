---
client_id: demo-parrucchiere
file: prenotazioni
aggiornato_il: 2026-07-14
consumato_da: [config-calendario, prompt-agent, workflow-n8n]
---

# Prenotazioni — Salone Bellezza

Questo file è la fonte diretta della **config calendario** del cliente. I valori qui sotto vengono
copiati 1:1 in `/config/clienti.json → calendario`.

## Parametri calendario

| Parametro            | Valore        | Note                                              |
|----------------------|---------------|---------------------------------------------------|
| `durata_slot_min`    | 30            | granularità della griglia, in minuti              |
| `capienza_per_slot`  | 3             | quante prenotazioni in parallelo (poltrone/sale)  |
| `anticipo_min_ore`   | 3             | non si prenota a meno di X ore                    |
| `anticipo_max_giorni`| 60            | non si prenota oltre X giorni                     |
| `buffer_min`         | 10            | pausa tra un appuntamento e il successivo         |
| `timezone`           | `Europe/Rome` |                                                   |

> Gli orari di apertura e le chiusure NON si duplicano qui: stanno in `orari.md`.

Nota su `capienza_per_slot: 3`: il salone ha **3 postazioni**, quindi fino a 3 clienti in parallelo
sullo stesso slot. Uno slot è "pieno" solo quando tutte e 3 le postazioni sono occupate. Il
`buffer_min: 10` serve alla pulizia e al riassetto della postazione tra un cliente e l'altro.

## Dati richiesti per prenotare

Ordine in cui la AI li chiede. Se ne manca uno, non prenota.

1. Servizio (uno tra quelli di `servizi.md`)
2. Nome e cognome
3. Giorno/orario preferito
4. Numero di telefono (di solito già noto da WhatsApp)
5. Prima volta da noi? sì/no

## Flusso

1. Cliente chiede appuntamento
2. AI chiama `GET /{client_id}/disponibilita` con servizio e finestra temporale
3. AI propone **massimo 3 slot** alla volta
4. Cliente sceglie → AI chiama `POST /{client_id}/prenota`
5. **Solo dopo risposta OK del servizio** la AI conferma al cliente
6. AI manda il riepilogo: servizio, giorno, ora, durata, indirizzo (Via Cibrario 24, Torino)

## Disdette e spostamenti

- Preavviso minimo per disdire: **12 ore**
- Penale per mancata disdetta: nessuna (ma la titolare vuole essere avvisata dei no-show ripetuti)
- La AI può cancellare in autonomia? sì, se il preavviso è rispettato
- La AI può spostare in autonomia? sì, se entro il preavviso
- Sotto il preavviso minimo: escalation all'umano (la AI non cancella e non giudica, avvisa la titolare)

## Promemoria

- Promemoria automatico: sì, 24 ore prima
- Testo: "Ciao {{nome}}! Ti ricordo l'appuntamento di domani alle {{ora}} per {{servizio}}. Se non
  riesci a venire scrivimi pure qui."

## Overbooking / lista d'attesa

- Se le 3 postazioni sono occupate: proponi i 2 slot liberi più vicini (stesso giorno se possibile,
  altrimenti il giorno successivo di apertura).
- Lista d'attesa: sì — se il cliente insiste su un giorno/orario pieno, la AI prende nome, servizio
  e finestra desiderata e li segnala alla titolare. Non promette nulla: "se si libera ti scrivo io".
