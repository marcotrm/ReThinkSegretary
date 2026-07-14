---
client_id: demo-dentista
file: obiettivi
aggiornato_il: 2026-07-14
consumato_da: [report-settimanale, curatela-vault]
---

# Obiettivi — Studio Dentistico Sorriso

Perché questo cliente ci paga. Serve a noi (NiaMarketing) per dimostrare il valore e per sapere
cosa curare nel vault. **Non finisce nel prompt dell'agent.**

## Perché ci ha preso

Perde chiamate perché è sempre in poltrona e nessuno risponde al telefono durante i trattamenti.
Stima circa 12 chiamate perse a settimana, quasi tutte richieste di primo appuntamento: sono
pazienti nuovi che, non ottenendo risposta, chiamano lo studio successivo. La sera si ritrova a
richiamare i numeri persi e spesso non li recupera.

## Cosa considera un successo

- Nessuna chiamata o messaggio senza risposta (target: 0 contatti persi a settimana)
- Almeno 8 appuntamenti a settimana presi in autonomia dalla AI
- Non doversi più occupare di WhatsApp la sera e nel weekend
- Nessun paziente con dolore acuto lasciato senza risposta

## Metriche da tracciare

| Metrica                          | Baseline (pre-AI) | Target    |
|----------------------------------|-------------------|-----------|
| Messaggi gestiti/settimana       | 0 (gestiti a mano, ~25) | 40+ |
| Appuntamenti presi dalla AI      | 0                 | 8/settimana |
| Escalation/settimana             | —                 | < 15%     |
| Tempo medio di risposta          | ore (spesso a fine giornata) | minuti (< 2 min) |
| Chiamate risposte h24            | ~12 perse/settimana | 100% (0 perse) |

## Da tenere d'occhio (curatela)

Cose che sappiamo essere deboli nel vault e vanno migliorate nelle prossime settimane.

- Le FAQ sui prezzi coprono solo igiene, prima visita e sbiancamento: manca tutta la parte di preventivi e piani di cura (per ora → escalation).
- Non sappiamo ancora come il titolare vuole gestire davvero le disdette last-minute: per ora escalation, ma servirà una regola.
- La lista d'attesa è dichiarata in `prenotazioni.md` ma non è ancora implementata nel workflow n8n.
- Da capire se il sabato mattina va davvero limitato a igiene e controlli o se è una regola informale.
- I sinonimi dei pazienti in `servizi.md` vanno arricchiti dopo le prime 2 settimane di chat reali.

## Storico interventi

| Data           | Cosa è cambiato          | Perché                    |
|----------------|--------------------------|---------------------------|
| 2026-07-14     | onboarding iniziale — creazione vault demo-dentista | tenant di TEST, dati inventati |

## Contatti

- Referente: Dott. Marco Bellini, titolare dello studio
- Telefono/WhatsApp: +39 333 1234567
- Numero storico dell'attività (collegato a Evolution nel pilota — vedi [[Onboarding commerciale]]): +39 02 12345678
- Numero nuovo dedicato al bot: +39 351 9876543
