---
client_id: demo-dentista
file: escalation
aggiornato_il: 2026-07-14
consumato_da: [workflow-n8n, prompt-agent]
---

# Escalation — Studio Dentistico Sorriso

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
- Sono stati scambiati più di 8 messaggi senza risolvere
- **Urgenza odontoiatrica**: dolore acuto, gonfiore, ascesso, trauma, dente rotto o sanguinamento in corso → escalation immediata, prima di qualsiasi altra risposta
- Richiesta di disdetta o spostamento sotto il preavviso di 24 ore (vedi `prenotazioni.md`)
- Richiesta di un servizio che non eroghiamo (vedi `servizi.md`) se il paziente insiste dopo il primo "no"

## Cosa dice la AI al cliente quando escala

> "Su questo la faccio ricontattare direttamente da un collega, così le diamo la risposta giusta.
> A presto."

Nel caso di urgenza/dolore il testo è invece:

> "Mi dispiace. Avviso subito il dottore e la facciamo richiamare a breve per trovarle un posto il
> prima possibile."

Dopo l'escalation la AI **smette di rispondere a quell'utente** finché non viene riattivata
(pausa-bot). Non deve continuare la conversazione da sola.

## Chi viene avvisato

| Canale   | Destinatario         | Quando                          |
|----------|----------------------|---------------------------------|
| WhatsApp | +39 333 1234567 (Dott. Marco Bellini, titolare) | sempre, entro 1 minuto dall'escalation |
| Slack    | #segretaria-alert    | sempre (canale interno NiaMarketing) |
| Email    | studio.sorriso.demo@example.com | solo urgenze e reclami |

## Formato della notifica al titolare

```
🔔 ESCALATION — Studio Dentistico Sorriso
Cliente: {{nome}} ({{numero}})
Motivo: {{motivo_escalation}}
Ultimo messaggio: "{{testo}}"
Conversazione: {{link}}
```

## Riattivazione del bot

- Chi può riattivare: il titolare (Dott. Marco Bellini)
- Come: comando/pulsante — DA DEFINIRE nel workflow n8n
- Riattivazione automatica dopo: 24 ore

## Urgenze fuori orario

- Definizione di "urgenza" per questo cliente: dolore acuto che non passa con antidolorifico, gonfiore del viso, ascesso, trauma con dente rotto o espulso, sanguinamento che non si arresta.
- Cosa fa la AI: non dà alcuna indicazione medica, avvisa immediatamente il titolare su WhatsApp e risponde al paziente che verrà richiamato al più presto. Se il paziente segnala gonfiore al viso o difficoltà a respirare/deglutire, aggiunge: "Se la situazione peggiora si rivolga al pronto soccorso."
