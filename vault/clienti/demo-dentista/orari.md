---
client_id: demo-dentista
file: orari
aggiornato_il: 2026-07-14
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Orari — Studio Dentistico Sorriso

## Orari di apertura

| Giorno    | Apertura | Chiusura | Pausa           | Chiuso |
|-----------|----------|----------|-----------------|--------|
| Lunedì    | 09:00    | 19:00    | 13:00-14:00     | no     |
| Martedì   | 09:00    | 19:00    | 13:00-14:00     | no     |
| Mercoledì | 09:00    | 19:00    | 13:00-14:00     | no     |
| Giovedì   | 09:00    | 19:00    | 13:00-14:00     | no     |
| Venerdì   | 09:00    | 19:00    | 13:00-14:00     | no     |
| Sabato    | 09:00    | 13:00    | —               | no     |
| Domenica  | —        | —        | —               | sì     |

> Questa tabella è la fonte per `orari_apertura` nella config calendario. Se cambia qui, va
> rigenerata la config del cliente.

## Chiusure straordinarie

Elenca date singole o intervalli. Formato `AAAA-MM-GG` o `AAAA-MM-GG → AAAA-MM-GG`.

- 2026-08-10 → 2026-08-24 — chiusura estiva
- 2026-12-24 → 2027-01-06 — festività natalizie

## Festività osservate

- Tutte le festività nazionali italiane
- Santo patrono (Sant'Ambrogio, Milano): 07/12

## Reperibilità fuori orario

- La segretaria AI **risponde h24** su WhatsApp, ma **non può confermare** appuntamenti fuori
  dagli orari sopra.
- Messaggi ricevuti fuori orario: rispondi comunque e proponi il primo slot utile del giorno
  lavorativo successivo.
- Emergenze fuori orario: vedi `escalation.md` (dolore acuto, trauma, gonfiore → escalation
  immediata al titolare).

## Note

- Il sabato lo studio è aperto solo per igiene dentale e controlli: niente otturazioni né
  sbiancamenti.
- L'ultimo appuntamento del mattino si accetta entro le 12:30; quello del pomeriggio entro le 18:00.
