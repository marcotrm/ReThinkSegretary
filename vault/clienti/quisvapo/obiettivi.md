---
client_id: quisvapo
file: obiettivi
aggiornato_il: 2026-07-20
consumato_da: [report-settimanale, curatela-vault]
---

# Obiettivi — Quisvapo

Perché questo cliente ci paga. Serve a noi (NiaMarketing) per dimostrare il valore e per sapere
cosa curare nel vault. **Non finisce nel prompt dell'agent.**

## Perché ci ha preso

Quisvapo è l'azienda di famiglia: è il **tenant pilota** della Segretaria. Duplice scopo:
(1) togliere ai commessi le telefonate ripetitive su prezzi/disponibilità/orari, che
interrompono il lavoro al banco; (2) collaudare il prodotto su un cliente vero prima di
venderlo (prossimo: Danilo). Sostituisce il QuisvapoVoiceBot standalone, che viene ritirato.

## Cosa considera un successo

- Le chiamate su prezzi e disponibilità gestite senza passare dal banco
- Zero informazioni sbagliate su prezzi (regola d'oro: solo dallo strumento `cerca`)
- Le richieste complesse convogliate ordinatamente su WhatsApp 351 708 9407
- Il sistema regge la telefonata reale: capisce nomi di prodotto storpiati, conferma
  prima di rispondere

## Metriche da tracciare

| Metrica                              | Baseline (pre-AI) | Target       |
|--------------------------------------|-------------------|--------------|
| Chiamate risposte dall'assistente    | 0                 | 100% h24     |
| Risposte prezzo/disponibilità corrette | —               | 100% (via API) |
| Deviazioni su WhatsApp               | —                 | tracciate nei log |
| Escalation al titolare/settimana     | —                 | < 15%        |

## Da tenere d'occhio (curatela)

- L'elenco città in `faq.md`/`orari.md` è statico: i negozi veri arrivano dallo strumento
  `negozi` — verificare che l'agent lo usi invece di recitare l'elenco.
- Gli orari sono uniformi (lun-sab 9-18) per assunzione: verificare col gestionale se
  qualche punto vendita fa orari diversi.
- Capire dal traffico reale quali domande mancano nelle FAQ.

## Storico interventi

| Data           | Cosa è cambiato          | Perché                    |
|----------------|--------------------------|---------------------------|
| 2026-07-20 | onboarding iniziale — vault derivato dal system prompt del QuisvapoVoiceBot | tenant pilota voce |

## Contatti

- Referente: Marco (NiaMarketing / famiglia Quisvapo)
- Telefono/WhatsApp: +39 331 282 7949
- Numero storico dell'attività: WhatsApp clienti 351 708 9407 (gestito dal bot Nico su
  n8n.quisvapo.app — NON da questa segretaria)
- Numero dedicato al canale voce: Twilio, in arrivo (bundle in approvazione)
