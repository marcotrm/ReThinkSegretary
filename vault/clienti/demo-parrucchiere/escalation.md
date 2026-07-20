---
client_id: demo-parrucchiere
file: escalation
aggiornato_il: 2026-07-14
consumato_da: [workflow-n8n, prompt-agent]
---

# Escalation — Salone Bellezza

Quando la AI si ferma e passa la palla a un umano.

## Trigger di escalation

La AI **deve** escalare quando:

- Confidenza sull'intento **< 0.6** (soglia di sistema)
- Il cliente chiede esplicitamente di parlare con una persona
- La domanda rientra nelle "domande a cui non rispondere" di `faq.md`
- Si tocca un divieto assoluto di `vincoli.md`
- Il cliente è arrabbiato / lamentela / reclamo / minaccia di recensione negativa
- Richiesta di rimborso o contestazione di un pagamento
- Il servizio calendario non risponde o va in errore
- Sono stati scambiati più di **8** messaggi senza risolvere
- **Reclamo su un colore riuscito male → sempre umano, senza eccezioni.** La AI non si giustifica,
  non propone rimedi, non offre il rifacimento: passa e basta.
- Richiesta di un cambio colore importante o di una schiaritura su capelli già trattati
- Disdetta o spostamento sotto le 12 ore di preavviso

## Cosa dice la AI al cliente quando escala

> "Su questo ti faccio ricontattare direttamente da Marta, così ti diamo la risposta giusta. A presto."

Dopo l'escalation la AI **smette di rispondere a quell'utente** finché non viene riattivata
(pausa-bot). Non deve continuare la conversazione da sola.

## Chi viene avvisato

| Canale   | Destinatario          | Quando                                              |
|----------|-----------------------|-----------------------------------------------------|
| WhatsApp | +39 347 7654321       | sempre (Marta, la titolare) — anche fuori orario     |
| WhatsApp | NiaMarketing (numero in `NIAMARKETING_WHATSAPP`) | sempre, in copia            |
| Email    | —                     | non usato da questo cliente                          |

## Formato della notifica al titolare

```
🔔 ESCALATION — Salone Bellezza
Cliente: {{nome}} ({{numero}})
Motivo: {{motivo_escalation}}
Ultimo messaggio: "{{testo}}"
Conversazione: {{link}}
```

## Riattivazione del bot

- Chi può riattivare: Marta (la titolare)
- Come: comando/pulsante — DA DEFINIRE nel workflow n8n
- Riattivazione automatica dopo: 24 ore, **tranne** nei casi di reclamo su un colore, dove la
  riattivazione è solo manuale.

## Urgenze fuori orario

- Definizione di "urgenza" per questo cliente: **non esistono urgenze reali.** Un parrucchiere non
  ha emergenze: al massimo c'è chi ha bisogno di un appuntamento per il giorno stesso.
- Cosa fa la AI: risponde comunque (h24), propone il primo slot utile e **non** dà numeri di
  reperibilità. Se il cliente insiste per essere richiamato subito, notifica Marta su WhatsApp e
  dice: "Ti faccio richiamare appena apriamo."
