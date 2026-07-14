---
client_id: <<client_id>>
file: prenotazioni
aggiornato_il: <<AAAA-MM-GG>>
consumato_da: [config-calendario, prompt-agent, workflow-n8n]
---

# Prenotazioni — <<Nome Attività>>

Questo file è la fonte diretta della **config calendario** del cliente. I valori qui sotto vengono
copiati 1:1 in `/config/clienti.json → calendario`.

## Parametri calendario

| Parametro            | Valore        | Note                                              |
|----------------------|---------------|---------------------------------------------------|
| `durata_slot_min`    | <<30>>        | granularità della griglia, in minuti              |
| `capienza_per_slot`  | <<1>>         | quante prenotazioni in parallelo (poltrone/sale)  |
| `anticipo_min_ore`   | <<2>>         | non si prenota a meno di X ore                    |
| `anticipo_max_giorni`| <<90>>        | non si prenota oltre X giorni                     |
| `buffer_min`         | <<0>>         | pausa tra un appuntamento e il successivo         |
| `timezone`           | `Europe/Rome` |                                                   |

> Gli orari di apertura e le chiusure NON si duplicano qui: stanno in `orari.md`.

## Dati richiesti per prenotare

Ordine in cui la AI li chiede. Se ne manca uno, non prenota.

1. <<Servizio>>
2. <<Nome e cognome>>
3. <<Giorno/orario preferito>>
4. <<Numero di telefono>> (di solito già noto da WhatsApp)
5. <<Prima volta da noi? sì/no>>

## Flusso

1. Cliente chiede appuntamento
2. AI chiama `GET /{client_id}/disponibilita` con servizio e finestra temporale
3. AI propone **massimo <<3>> slot** alla volta
4. Cliente sceglie → AI chiama `POST /{client_id}/prenota`
5. **Solo dopo risposta OK del servizio** la AI conferma al cliente
6. AI manda il riepilogo: <<servizio, giorno, ora, indirizzo>>

## Disdette e spostamenti

- Preavviso minimo per disdire: <<24 ore>>
- Penale per mancata disdetta: <<nessuna | € XX>>
- La AI può cancellare in autonomia? <<sì>>
- La AI può spostare in autonomia? <<sì, se entro il preavviso>>
- Sotto il preavviso minimo: <<escalation all'umano>>

## Promemoria

- Promemoria automatico: <<sì>>, <<24>> ore prima
- Testo: <<"Le ricordo l'appuntamento di domani alle {{ora}} per {{servizio}}. Se non può venire mi
  scriva pure.">>

## Overbooking / lista d'attesa

- <<Se non c'è posto: proponi i 2 slot liberi più vicini>>
- Lista d'attesa: <<no | sì — come funziona>>
