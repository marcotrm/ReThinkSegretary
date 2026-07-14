---
client_id: demo-parrucchiere
file: orari
aggiornato_il: 2026-07-14
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Orari — Salone Bellezza

## Orari di apertura

| Giorno    | Apertura | Chiusura | Pausa           | Chiuso |
|-----------|----------|----------|-----------------|--------|
| Lunedì    | —        | —        | —               | sì     |
| Martedì   | 09:00    | 18:00    | — (continuato)  | no     |
| Mercoledì | 09:00    | 18:00    | — (continuato)  | no     |
| Giovedì   | 09:00    | 18:00    | — (continuato)  | no     |
| Venerdì   | 09:00    | 18:00    | — (continuato)  | no     |
| Sabato    | 08:30    | 17:00    | — (continuato)  | no     |
| Domenica  | —        | —        | —               | sì     |

> Questa tabella è la fonte per `orari_apertura` nella config calendario. Se cambia qui, va
> rigenerata la config del cliente.

## Chiusure straordinarie

Elenca date singole o intervalli. Formato `AAAA-MM-GG` o `AAAA-MM-GG → AAAA-MM-GG`.

- 2026-08-08 → 2026-08-23 — chiusura estiva
- 2026-12-25 → 2026-12-26 — Natale e Santo Stefano
- 2027-01-01 — Capodanno

## Festività osservate

- Tutte le festività nazionali italiane
- Santo patrono (San Giovanni, Torino): 24/06

## Reperibilità fuori orario

- La segretaria AI **risponde h24** su WhatsApp, ma **non può confermare** appuntamenti fuori
  dagli orari sopra.
- Messaggi ricevuti fuori orario: rispondi comunque e proponi il primo slot utile nei giorni
  di apertura (mai lunedì, mai domenica).
- Emergenze fuori orario: vedi `escalation.md`. Il salone non ha urgenze reali — nessun numero
  di reperibilità da dare.

## Note

- Il lunedì il salone è chiuso: è il giorno di riposo classico dei parrucchieri. Se un cliente
  chiede "lunedì", non proporre alternative lunedì, ma il martedì successivo.
- Il sabato si apre mezz'ora prima (08:30) ed è il giorno più pieno: proponi con anticipo.
- Ultimo appuntamento accettato: sempre in modo che il servizio finisca entro l'orario di
  chiusura (es. un colore da 90 min il venerdì non parte dopo le 16:30).
