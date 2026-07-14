---
client_id: <<client_id>>
file: escalation
aggiornato_il: <<AAAA-MM-GG>>
consumato_da: [workflow-n8n, prompt-agent]
---

# Escalation — <<Nome Attività>>

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
- Sono stati scambiati più di <<8>> messaggi senza risolvere
- <<trigger specifico del cliente>>

## Cosa dice la AI al cliente quando escala

> <<"Su questo la faccio ricontattare direttamente da un collega, così le diamo la risposta giusta.
> A presto.">>

Dopo l'escalation la AI **smette di rispondere a quell'utente** finché non viene riattivata
(pausa-bot). Non deve continuare la conversazione da sola.

## Chi viene avvisato

| Canale   | Destinatario         | Quando                          |
|----------|----------------------|---------------------------------|
| WhatsApp | <<+39 3XX XXXXXXX>>  | <<sempre, in orario di lavoro>>  |
| Slack    | <<#segretaria-alert>>| <<sempre>>                       |
| Email    | <<titolare@...>>     | <<solo urgenze>>                 |

## Formato della notifica al titolare

```
🔔 ESCALATION — <<Nome Attività>>
Cliente: {{nome}} ({{numero}})
Motivo: {{motivo_escalation}}
Ultimo messaggio: "{{testo}}"
Conversazione: {{link}}
```

## Riattivazione del bot

- Chi può riattivare: <<il titolare>>
- Come: <<comando/pulsante — DA DEFINIRE nel workflow n8n>>
- Riattivazione automatica dopo: <<24 ore | mai>>

## Urgenze fuori orario

- Definizione di "urgenza" per questo cliente: <<...>>
- Cosa fa la AI: <<manda il numero di emergenza: +39 ... e avvisa il titolare>>
