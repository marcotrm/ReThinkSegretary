---
client_id: quisvapo
file: escalation
aggiornato_il: 2026-07-20
consumato_da: [workflow-n8n, prompt-agent]
---

# Escalation — Quisvapo

Quando la AI si ferma e passa la palla. Per Quisvapo l'escalation standard NON è
"ti faccio richiamare": è **indirizzare il cliente su WhatsApp**, dove risponde il
sistema WhatsApp di Quisvapo (gestito a parte, fuori da questa segretaria).

## Trigger di escalation

La AI **deve** passare la palla quando:

- Lo strumento `cerca` non trova il prodotto o non risponde
- La domanda è tecnica o specifica: problemi al dispositivo, resi, garanzie, ordini,
  spedizioni, fatture, reclami
- Il cliente chiede il saldo punti Fidelity o dati personali
- Il cliente è arrabbiato / lamentela / minaccia di recensione negativa
- Richiesta di rimborso o contestazione di un pagamento
- Il cliente chiede esplicitamente di parlare con una persona
- Non è sicura della risposta, o si tocca un divieto di `vincoli.md`
- Più di 8 scambi senza risolvere

## Cosa dice la AI al cliente quando escala

> "Per questa richiesta le rispondiamo con piacere su WhatsApp al 351 708 9407, così le
> diamo tutti i dettagli."

Se il cliente insiste per una persona al telefono: prendere nome e motivo, avvisare il
titolare (vedi sotto) e dire che verrà ricontattato.

## Chi viene avvisato

| Canale   | Destinatario         | Quando                          |
|----------|----------------------|---------------------------------|
| WhatsApp (titolare)     | +39 331 282 7949 (Marco) | reclami, clienti arrabbiati, richieste di richiamata |
| WhatsApp (NiaMarketing) | numero in `NIAMARKETING_WHATSAPP` (n8n) | sempre, in copia      |
| Email    | —                    | non usato da questo cliente      |

## Formato della notifica al titolare

```
🔔 ESCALATION — Quisvapo
Cliente: {{nome}} ({{numero}})
Motivo: {{motivo_escalation}}
Ultimo messaggio: "{{testo}}"
Conversazione: {{link}}
```

## Riattivazione del bot

- Chi può riattivare: il titolare (dal suo numero personale) o NiaMarketing
- Come: rispondendo **`RIATTIVA <numero del cliente>`** nella chat WhatsApp dell'attività
  (il numero è già scritto nell'avviso di escalation, basta copiare)
- Riattivazione automatica dopo: mai

## Urgenze fuori orario

- Definizione di "urgenza" per questo cliente: non ci sono urgenze telefoniche —
  qualunque cosa non gestibile va su WhatsApp 351 708 9407
- Cosa fa la AI: dà il riferimento WhatsApp e chiude con cortesia
