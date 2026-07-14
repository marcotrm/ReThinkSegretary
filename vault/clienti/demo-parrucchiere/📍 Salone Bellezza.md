---
tipo: scheda-cliente
client_id: demo-parrucchiere
stato: test
aggiornato_il: 2026-07-14
---

# 📍 Salone Bellezza

> [!warning] Tenant di TEST
> Dati inventati. Non è un cliente reale e non risponde a nessuno.

## A colpo d'occhio

| | |
|---|---|
| **client_id** | `demo-parrucchiere` |
| **Settore** | Parrucchiere — Torino |
| **Numero bot** | +39 000 0000002 |
| **Numero storico** (su Evolution nel pilota, poi 360dialog) | — |
| **Escalation a** | +39 347 7654321 (titolare, WhatsApp) |
| **Orari** | lun CHIUSO · mar-ven 9-18 continuato · sab 8:30-17 · dom chiuso |
| **Calendario** | **3 postazioni**, slot 30', buffer 10', anticipo 3h |
| **Chiusura estiva** | 8 → 23 agosto 2026 |

## Il vault

**Chi la legge:** 🤖 = prompt dell'agent e risposte WhatsApp · 📅 = config calendario ·
👤 = solo noi.

- 🤖📅 [[clienti/demo-parrucchiere/orari|Orari]] — apertura, chiusure, festività
- 🤖📅 [[clienti/demo-parrucchiere/servizi|Servizi]] — catalogo, prezzi, durate, cosa NON facciamo
- 🤖 [[clienti/demo-parrucchiere/faq|FAQ]] — risposte pronte da mandare
- 🤖 [[clienti/demo-parrucchiere/brand-voice|Brand voice]] — tono ed esempi ✅/❌
- 🤖 [[clienti/demo-parrucchiere/vincoli|Vincoli]] — le linee rosse
- 📅 [[clienti/demo-parrucchiere/prenotazioni|Prenotazioni]] — parametri calendario, disdette
- 🤖 [[clienti/demo-parrucchiere/escalation|Escalation]] — quando passa all'umano
- 👤 [[clienti/demo-parrucchiere/obiettivi|Obiettivi]] — perché ci paga, metriche, cosa curare

## Materiale grezzo

Da cui è stato ricavato il vault: [[clienti/demo-parrucchiere/_materiale/README|_materiale]]

## Attenzioni specifiche

- **3 postazioni = 3 clienti in parallelo.** È l'unico tenant con capienza > 1: se rompi
  la gestione della capienza, te ne accorgi qui.
- **Colore e schiariture → escalation.** Non si promette un risultato senza aver visto i
  capelli. È il reclamo tipico del settore, e nasce sempre da una promessa fatta in chat.
- Prezzi "a partire da": la AI non tratta e non sconta.

## Storico

| Data | Cosa | Chi |
|---|---|---|
| 2026-07-14 | Creazione vault di test | Claude |
