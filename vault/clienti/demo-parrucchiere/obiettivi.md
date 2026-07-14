---
client_id: demo-parrucchiere
file: obiettivi
aggiornato_il: 2026-07-14
consumato_da: [report-settimanale, curatela-vault]
---

# Obiettivi — Salone Bellezza

Perché questo cliente ci paga. Serve a noi (NiaMarketing) per dimostrare il valore e per sapere
cosa curare nel vault. **Non finisce nel prompt dell'agent.**

## Perché ci ha preso

Marta, la titolare, ha le mani nei capelli tutto il giorno e non può rispondere al telefono. I
messaggi WhatsApp si accumulano e finisce per rispondere la sera dopo la chiusura, sul divano,
spesso fino alle 22-23. Arriva a fine giornata esausta e i clienti nel frattempo vanno da qualcun
altro. Con 3 postazioni attive il salone gira parecchio, ma la gestione degli appuntamenti è tutta
sulle sue spalle.

## Cosa considera un successo

- **Non toccare più il telefono fuori dall'orario di lavoro.** È l'obiettivo numero uno, tutto il
  resto viene dopo.
- Nessun messaggio senza risposta la mattina dopo
- Almeno 15 appuntamenti a settimana presi dalla AI senza che lei intervenga
- Sabato pieno senza dover richiamare nessuno

## Metriche da tracciare

| Metrica                          | Baseline (pre-AI)      | Target              |
|----------------------------------|------------------------|---------------------|
| Messaggi gestiti/settimana       | ~70 (tutti a mano)     | ~70, 0 a mano       |
| Appuntamenti presi dalla AI      | 0                      | 15/settimana        |
| Escalation/settimana             | —                      | < 15%               |
| Tempo medio di risposta          | 4-6 ore (spesso la sera)| < 2 minuti         |
| Chiamate risposte h24            | ~40%                   | 100%                |
| Messaggi gestiti da Marta dopo le 19:00 | ~20/settimana   | **0**               |

## Da tenere d'occhio (curatela)

Cose che sappiamo essere deboli nel vault e vanno migliorate nelle prossime settimane.

- I prezzi "a partire da" (colore, colpi di sole) sono la zona più a rischio: verificare che la AI
  non si lasci trascinare in stime esatte.
- Non sappiamo ancora quanti clienti chiedono lo shatush via foto: se sono tanti, serve una risposta
  standard più curata per rimandare in salone senza far scappare il cliente.
- La gestione della capienza multipla (3 postazioni) è da verificare sul campo: è il primo cliente
  con `capienza_per_slot > 1`.
- Da testare: cosa succede se un cliente chiede il lunedì (giorno di chiusura) con insistenza.
- Chiusura estiva 08-23 agosto: verificare che la AI non prenoti dentro quella finestra.

## Storico interventi

| Data           | Cosa è cambiato                          | Perché                          |
|----------------|------------------------------------------|---------------------------------|
| 2026-07-14     | onboarding iniziale — vault compilato    | tenant di test capienza multipla|

## Contatti

- Referente: Marta Bellone, titolare
- Telefono/WhatsApp: +39 347 7654321
- Numero storico dell'attività (collegato a Evolution nel pilota — vedi [[Onboarding commerciale]]): +39 011 4567890 (fisso del salone)
- Numero nuovo dedicato al bot: +39 351 1122334
