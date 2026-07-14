---
client_id: demo-parrucchiere
file: servizi
aggiornato_il: 2026-07-14
consumato_da: [prompt-agent, config-calendario, risposte-whatsapp]
---

# Servizi — Salone Bellezza

## Catalogo

Un blocco per servizio. `durata_min` e `slot` alimentano direttamente il calendario: la durata
qui dichiarata è quella che il sistema prenota.

### Taglio donna

- **Descrizione (come la spieghi al cliente):** Taglio con lavaggio e asciugatura veloce.
- **Prezzo:** 35€ — fisso
- **Durata:** 45 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque (Marta, Silvia, Giada)
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "taglio", "spuntatina", "solo le punte", "accorciare"

### Taglio uomo

- **Descrizione:** Taglio uomo con lavaggio, forbice o macchinetta.
- **Prezzo:** 20€ — fisso
- **Durata:** 30 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "taglio maschile", "sfumatura", "rasatura", "taglio per mio figlio"

### Piega

- **Descrizione:** Lavaggio e piega con phon o spazzola, liscia o mossa.
- **Prezzo:** 25€ — fisso
- **Durata:** 30 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "messa in piega", "piastra", "solo phon", "mi sistemi i capelli"

### Colore

- **Descrizione:** Colore su tutta la testa o ritocco ricrescita, con piega inclusa.
- **Prezzo:** da 60€ — a partire da (dipende da lunghezza e quantità di prodotto)
- **Durata:** 90 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque
- **Prerequisiti:** nessuno per il ritocco. Se è un cambio colore importante o si parte da capelli
  già trattati, serve prima una valutazione in salone (vedi `vincoli.md`).
- **Sinonimi usati dai clienti:** "tinta", "ritocco", "ricrescita", "coprire i bianchi", "colorare"

### Colpi di sole / mèches

- **Descrizione:** Schiaritura a ciocche con tonalizzazione e piega finale.
- **Prezzo:** da 90€ — a partire da (dipende dal numero di ciocche e dalla lunghezza)
- **Durata:** 120 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque
- **Prerequisiti:** trattandosi di una schiaritura, il risultato si valuta solo dal vivo: la AI
  prenota ma **non promette il risultato** e passa al titolare le richieste di cambi drastici.
- **Sinonimi usati dai clienti:** "shatush", "balayage", "meches", "colpi di sole", "schiaritura",
  "degradé", "punte bionde"

### Trattamento ricostruttivo

- **Descrizione:** Trattamento in cabina per capelli sfibrati, con maschera e piega finale.
- **Prezzo:** 45€ — fisso
- **Durata:** 60 min
- **Prenotabile dalla AI:** sì
- **Chi lo eroga:** chiunque
- **Prerequisiti:** nessuno
- **Sinonimi usati dai clienti:** "ricostruzione", "botox capelli", "cheratina", "maschera",
  "trattamento per capelli rovinati"

## Cosa NON facciamo

Elenco esplicito. Serve a far dire alla AI "no, non lo facciamo" invece di inventare.

- Extension (di nessun tipo: cheratina, clip, adesive)
- Trucco sposa / make-up

## Politica prezzi

- La AI può comunicare i prezzi: sì, ma **solo così come sono scritti qui**. Sui servizi "a partire
  da" (colore, colpi di sole) dice la cifra di partenza e spiega che il prezzo finale si definisce
  in salone, in base a lunghezza e lavoro. Mai stimare un prezzo esatto.
- Sconti e promo attive: nessuna. La AI **non** fa sconti e non tratta sul prezzo (vedi `vincoli.md`).
- Metodi di pagamento accettati: contanti, bancomat, carte di credito. No assegni, no satispay.
