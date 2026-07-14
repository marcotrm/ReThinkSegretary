---
client_id: demo-dentista
file: servizi
aggiornato_il: 2026-07-14
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Servizi — Studio Dentistico Sorriso

## Catalogo

Un blocco per servizio. `durata_min` e `slot` alimentano direttamente il calendario: la durata
qui dichiarata è quella che il sistema prenota.

### Prima visita

- **Descrizione (come la spieghi al cliente):** Una prima visita di valutazione con il dentista, per capire lo stato di salute della bocca e cosa serve fare.
- **Prezzo:** gratuita — fisso
- **Durata:** 30 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** Dott. Marco Bellini
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "prima visita", "visita di controllo iniziale", "vorrei farmi vedere", "un preventivo"

### Igiene dentale

- **Descrizione:** La pulizia professionale dei denti, con rimozione di tartaro e macchie.
- **Prezzo:** € 80 — fisso
- **Durata:** 45 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** Dott.ssa Elena Rossi (igienista)
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "pulizia", "pulizia dei denti", "igiene", "detartrasi", "lo sbianchettamento del tartaro"

### Otturazione

- **Descrizione:** La cura di una carie, con ricostruzione del dente in composito dello stesso colore del dente.
- **Prezzo:** € 120 — a partire da (il prezzo finale dipende dall'estensione della carie, si definisce in visita)
- **Durata:** 60 min
- **Prenotabile dalla AI:** sì — solo se il paziente è già stato visitato in studio
- **Chi lo eroga:** Dott. Marco Bellini
- **Prerequisiti:** prima visita o controllo già effettuato
- **Sinonimi usati dai clienti:** "carie", "otturazione", "ho un buco", "piombatura", "devo curare un dente"

### Sbiancamento

- **Descrizione:** Il trattamento estetico per schiarire il colore dei denti, eseguito in studio in un'unica seduta.
- **Prezzo:** € 250 — fisso
- **Durata:** 60 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** Dott.ssa Elena Rossi
- **Prerequisiti:** igiene dentale effettuata negli ultimi 6 mesi
- **Sinonimi usati dai clienti:** "sbiancamento", "denti più bianchi", "schiarire i denti", "sbiancare"

### Controllo

- **Descrizione:** Il controllo periodico per verificare che sia tutto in ordine, di solito una volta l'anno.
- **Prezzo:** € 50 — fisso
- **Durata:** 30 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** Dott. Marco Bellini
- **Prerequisiti:** essere già paziente dello studio
- **Sinonimi usati dai clienti:** "controllo", "controllino", "check-up", "visita di controllo", "il richiamo"

## Cosa NON facciamo

Elenco esplicito. Serve a far dire alla AI "no, non lo facciamo" invece di inventare.

- Ortodonzia invisibile (allineatori trasparenti tipo Invisalign)
- Chirurgia maxillo-facciale

Se un paziente chiede uno di questi due: rispondi che lo studio non li esegue e non proporre
alternative né altri studi. Se insiste, escalation.

## Politica prezzi

- La AI può comunicare i prezzi: sì, ma **solo quelli fissi** presenti in questo file. Per
  l'otturazione dice solo "a partire da 120€, il prezzo esatto lo definisce il dentista in visita".
- Sconti e promo attive: nessuna. La AI non tratta sul prezzo e non applica sconti.
- Metodi di pagamento accettati: contanti, bancomat, carta di credito. Possibilità di pagamento
  rateale per preventivi sopra i 1.000€, ma se ne parla solo in studio (non via WhatsApp).
