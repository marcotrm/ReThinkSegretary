---
tipo: scheda-cliente
client_id: demo-dentista
stato: test
aggiornato_il: 2026-07-14
---

# 📍 Studio Dentistico Sorriso

> [!warning] Tenant di TEST
> Dati inventati. Non è un cliente reale e non risponde a nessuno.

## A colpo d'occhio

| | |
|---|---|
| **client_id** | `demo-dentista` |
| **Settore** | Studio dentistico — Milano |
| **Numero bot** (nuovo, dedicato) | +39 000 0000001 |
| **Numero storico** ⛔ **MAI collegare al bot** | — |
| **Escalation a** | +39 333 1234567 (titolare, WhatsApp) |
| **Orari** | lun-ven 9-13 / 14-19 · sab 9-13 · dom chiuso |
| **Calendario** | 1 poltrona, slot 30', anticipo 2h |
| **Chiusura estiva** | 10 → 24 agosto 2026 |

## Il vault

La knowledge base. **Chi la legge:** 🤖 = prompt dell'agent e risposte WhatsApp ·
📅 = config calendario · 👤 = solo noi.

- 🤖📅 [[clienti/demo-dentista/orari|Orari]] — apertura, chiusure, festività
- 🤖📅 [[clienti/demo-dentista/servizi|Servizi]] — catalogo, prezzi, durate, cosa NON facciamo
- 🤖 [[clienti/demo-dentista/faq|FAQ]] — risposte pronte da mandare
- 🤖 [[clienti/demo-dentista/brand-voice|Brand voice]] — tono ed esempi ✅/❌
- 🤖 [[clienti/demo-dentista/vincoli|Vincoli]] — le linee rosse
- 📅 [[clienti/demo-dentista/prenotazioni|Prenotazioni]] — parametri calendario, disdette
- 🤖 [[clienti/demo-dentista/escalation|Escalation]] — quando passa all'umano
- 👤 [[clienti/demo-dentista/obiettivi|Obiettivi]] — perché ci paga, metriche, cosa curare

## Materiale grezzo

Da cui è stato ricavato il vault: [[clienti/demo-dentista/_materiale/README|_materiale]]

## Attenzioni specifiche

- **Dolore acuto → escalation immediata.** Niente diagnosi, niente consigli su farmaci:
  è uno studio medico, il rischio non è la figuraccia, è il danno.
- Non fanno ortodonzia invisibile né chirurgia maxillo-facciale. La AI deve dire **no**,
  non "vediamo cosa possiamo fare".

## Storico

| Data | Cosa | Chi |
|---|---|---|
| 2026-07-14 | Creazione vault di test | Claude |
