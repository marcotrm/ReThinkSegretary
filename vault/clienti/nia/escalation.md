---
client_id: nia
file: escalation
aggiornato_il: 2026-07-23
consumato_da: [workflow-n8n, prompt-agent]
---

# Escalation — Nia — Call con Michele

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
- Sono stati scambiati più di Titolare: Michele, +39 348 381 9851. Avvisi via WhatsApp. messaggi senza risolvere
- n/d (tenant interno Nia)

## Cosa dice la AI al cliente quando escala

> "Su questo la faccio ricontattare da Michele, cosi' le da' la risposta giusta."

Dopo l'escalation la AI **smette di rispondere a quell'utente** finché non viene riattivata
(pausa-bot). Non deve continuare la conversazione da sola.

## Chi viene avvisato

| Canale   | Destinatario         | Quando                          |
|----------|----------------------|---------------------------------|
| WhatsApp (titolare)     | +393483819851 | n/d (tenant interno Nia)          |
| WhatsApp (NiaMarketing) | numero in `NIAMARKETING_WHATSAPP` (n8n) | sempre, in copia      |
| Email    | n/d (tenant interno Nia)     | n/d (tenant interno Nia)                 |

## Formato della notifica al titolare

```
🔔 ESCALATION — Nia — Call con Michele
Cliente: {{nome}} ({{numero}})
Motivo: {{motivo_escalation}}
Ultimo messaggio: "{{testo}}"
Conversazione: {{link}}
```

## Riattivazione del bot

- Chi può riattivare: il titolare (dal suo numero personale) o NiaMarketing
- Come: rispondendo **`RIATTIVA <numero del cliente>`** nella chat WhatsApp dell'attività
  (il numero è già scritto nell'avviso di escalation, basta copiare)
- Riattivazione automatica dopo: n/d (tenant interno Nia)

## Urgenze fuori orario

- Definizione di "urgenza" per questo cliente: n/d (tenant interno Nia)
- Cosa fa la AI: n/d (tenant interno Nia)
