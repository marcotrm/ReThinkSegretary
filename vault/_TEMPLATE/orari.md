---
client_id: <<client_id>>
file: orari
aggiornato_il: <<AAAA-MM-GG>>
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Orari — <<Nome Attività>>

## Orari di apertura

| Giorno    | Apertura | Chiusura | Pausa           | Chiuso |
|-----------|----------|----------|-----------------|--------|
| Lunedì    | <<09:00>> | <<19:00>> | <<13:00-14:00>> | no     |
| Martedì   | <<09:00>> | <<19:00>> | <<13:00-14:00>> | no     |
| Mercoledì | <<09:00>> | <<19:00>> | <<13:00-14:00>> | no     |
| Giovedì   | <<09:00>> | <<19:00>> | <<13:00-14:00>> | no     |
| Venerdì   | <<09:00>> | <<19:00>> | <<13:00-14:00>> | no     |
| Sabato    | <<09:00>> | <<13:00>> | —               | no     |
| Domenica  | —        | —        | —               | sì     |

> Questa tabella è la fonte per `orari_apertura` nella config calendario. Se cambia qui, va
> rigenerata la config del cliente.

## Chiusure straordinarie

Elenca date singole o intervalli. Formato `AAAA-MM-GG` o `AAAA-MM-GG → AAAA-MM-GG`.

- <<2026-08-10 → 2026-08-24>> — <<chiusura estiva>>
- <<2026-12-24 → 2026-01-06>> — <<festività>>

## Festività osservate

- <<Tutte le festività nazionali italiane>>
- <<Santo patrono: GG/MM>>

## Reperibilità fuori orario

- La segretaria AI **risponde h24** su WhatsApp, ma **non può confermare** appuntamenti fuori
  dagli orari sopra.
- Messaggi ricevuti fuori orario: <<rispondi comunque e proponi il primo slot utile>>
- Emergenze fuori orario: <<vedi escalation.md>>

## Note

<<Qualsiasi eccezione ricorrente: es. "il primo lunedì del mese apriamo alle 11".>>
