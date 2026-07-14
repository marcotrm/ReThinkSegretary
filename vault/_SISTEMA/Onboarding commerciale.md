---
tipo: procedura
aggiornato_il: 2026-07-14
---

# Onboarding commerciale — dalla mail all'attivazione

Il percorso completo con un cliente nuovo. La parte tecnica è in [[Checklist onboarding]]:
qui c'è quello che dici **tu** al cliente, in che ordine, e cosa devi ottenere da lui.

Regola generale: **ogni passo ha un obiettivo unico.** La mail non deve vendere, deve
ottenere la call. La call non deve chiudere, deve capire. Non accorpare.

---

## Fase 1 — La mail

**Obiettivo: ottenere 20 minuti di call. Nient'altro.**

Non spiegare come funziona, non mandare listini, non allegare PDF. Il cliente non compra
un'AI, compra il non perdere più chiamate.

> **Oggetto:** Le chiamate che perdete mentre siete in poltrona
>
> Buongiorno [Nome],
>
> mi sono accorto di una cosa guardando la vostra pagina Google: avete parecchie recensioni
> che vi descrivono come difficili da raggiungere per telefono. Immagino non sia una novità.
>
> Lavoro con attività come la vostra su un servizio che risponde a WhatsApp e al telefono
> quando voi non potete: prende gli appuntamenti, risponde alle domande di sempre (orari,
> prezzi, dove siete) e vi passa solo i casi che contano davvero.
>
> Non è un centralino automatico e non è un chatbot che fa perdere tempo alla gente: risponde
> come rispondereste voi, perché gli insegniamo noi come parlate.
>
> Ha 20 minuti questa settimana per capire se ha senso nel vostro caso? Se non ce l'ha,
> glielo dico io.
>
> [Firma]

**Perché funziona:** parte da un problema che *lui* ha già (non da quello che vendi tu), cita
una prova concreta (le recensioni: guardale prima davvero), e l'ultima riga toglie pressione —
è quella che fa rispondere.

**Se non risponde:** un solo follow-up dopo 4-5 giorni, corto. Poi basta.

---

## Fase 2 — Portarlo su WhatsApp

Se risponde alla mail, **spostati subito su WhatsApp**. Le mail muoiono, WhatsApp no — e per
un dentista o un parrucchiere è il canale naturale.

> Perfetto. Le scrivo su WhatsApp così ci mettiamo d'accordo sull'orario, è più comodo. Il suo
> numero è quello sul sito?

Su WhatsApp fissa la call. Chiedi **30 minuti**, non 20: durante la call devi anche vedere
delle cose insieme a lui.

---

## Fase 3 — La call (30 minuti)

**Obiettivo: capire come lavora e raccogliere il materiale. Non vendere.**

Registrala (chiedi il permesso). Da qui esce il vault, e la qualità del vault decide se il
servizio funziona.

### Cosa chiedere, in quest'ordine

**Il problema (5 min) — fallo parlare, tu stai zitto**
- Quante chiamate perdete in una settimana, secondo lei? E quanti messaggi WhatsApp?
- Chi risponde oggi? E quando è in poltrona / sotto il casco / con un cliente?
- La sera e nel weekend chi guarda WhatsApp?
- Cosa succede a chi non riesce a prenotare? (Risposta vera: va dal concorrente.)

**Le domande dei clienti (10 min) — è il cuore di tutto**
- Quali sono le 10 domande che le fanno sempre?
- Cosa chiedono prima di prenotare?
- **Mi apre WhatsApp e mi fa vedere le ultime 20 conversazioni?** ← la domanda più importante
  della call. Lì dentro c'è la brand voice, ci sono le FAQ vere e il modo in cui parla ai
  clienti. Chiedi l'export della chat.

**Gli appuntamenti (5 min)**
- Quanto dura ogni servizio? Quanti clienti in parallelo (poltrone, postazioni)?
- Con quanto anticipo si prenota? Quanto preavviso serve per disdire?
- Quando siete chiusi? Ferie già fissate?
- Che agenda usate oggi? (Carta, Google Calendar, gestionale?)

**Le linee rosse (5 min) — quello che la AI non deve fare MAI**
- C'è qualcosa che non deve assolutamente dire o promettere?
- Cosa vuole gestire sempre di persona? (dolore, reclami, preventivi, minori…)
- Quali servizi NON fate, anche se ve li chiedono?

**Il numero (5 min) — vedi Fase 4**

### Cosa ti porti a casa dalla call

- [ ] Export delle vecchie chat WhatsApp ← **se non lo ottieni, il vault sarà mediocre**
- [ ] Listino con durate
- [ ] Orari veri (non quelli sul sito, che sono sempre sbagliati)
- [ ] Chiusure e ferie
- [ ] Le linee rosse
- [ ] Chi è il referente e a chi vanno le escalation

Tutto dentro `vault/clienti/<client_id>/_materiale/`.

---

## Fase 4 — Il numero: la conversazione difficile

Durante il pilota rispondiamo **dal numero storico** del cliente via Evolution, mentre si
prepara 360dialog (il canale ufficiale Meta, che richiede tempo e la firma del cliente).

**Questo va detto al cliente, chiaramente, e va messo per iscritto.** Non è burocrazia: se il
numero viene bloccato e lui non lo sapeva, il problema non è il numero, è che ha perso fiducia.

> Le spiego una cosa in trasparenza. Nella prima fase colleghiamo il servizio direttamente al
> vostro numero WhatsApp, così i vostri clienti continuano a scrivere dove hanno sempre scritto
> e voi non dovete comunicare nessun numero nuovo.
>
> Questo funziona molto bene, ma non è il canale ufficiale di Meta: c'è una possibilità — bassa,
> perché noi rispondiamo solo a chi vi scrive per primo e mai in massa — che WhatsApp blocchi il
> numero. In parallelo attiviamo il canale ufficiale (360dialog), che elimina del tutto questo
> rischio, ma richiede qualche settimana e una verifica di Meta.
>
> Se preferisce zero rischi fin da subito, partiamo con un numero nuovo dedicato e passiamo al
> suo quando il canale ufficiale è pronto. Decide lei: le va bene così?

Fatti rispondere **su WhatsApp**, per iscritto. Quel messaggio è la tua tutela.

### I paletti tecnici (non negoziabili)

Se si usa il numero storico su Evolution, questi riducono davvero il rischio:

1. **Solo risposte.** Mai un messaggio a freddo, mai invii massivi, mai promo. Il workflow già
   risponde solo a chi scrive per primo: non aggiungerci campagne.
2. **Ritardo 5–15 min** già attivo. Non abbassarlo per "sembrare più reattivi": la reattività
   istantanea h24 è esattamente ciò che fa scattare i controlli.
3. **Backup delle chat prima di collegare.** Impostazioni → Chat → Backup. Se il numero viene
   bloccato, lo storico non è perso.
4. **Il telefono del cliente resta acceso e col numero attivo.** Evolution si collega come
   dispositivo aggiuntivo, non sostituisce la sua app.
5. **Partenza morbida:** i primi giorni tienilo d'occhio. Se WhatsApp manda avvisi, si stacca
   subito e si passa al numero nuovo.
6. **360dialog si avvia SUBITO**, in parallelo, non "quando avremo tempo". Il numero storico su
   Evolution è una soluzione ponte, e più corto è il ponte meglio è.

---

## Fase 5 — Dopo la call: passare il materiale a Claude

**Entro 24h manda al cliente il riepilogo** di quello che hai capito. Non un preventivo — un
riepilogo. Se hai capito bene il suo problema, si vende da solo.

Poi si compila il vault. Ecco **come passare il materiale a Claude**, in modo che il vault esca
buono al primo colpo.

### 1. Metti tutto in una cartella

```
vault/clienti/<client_id>/_materiale/
    chat-export.txt        ← l'export WhatsApp (il pezzo più importante)
    call-appunti.md        ← o la registrazione/trascrizione
    listino.pdf
    recensioni.txt         ← copia-incolla le recensioni Google, anche le brutte
    sito.md                ← copia-incolla le pagine utili del sito
```

Il `client_id` è uno slug minuscolo: `studio-rossi`, `bar-centrale`. Diventa il nome della cartella,
il segmento URL del calendario e il nome dell'istanza Evolution: **una volta scelto non si cambia.**

**L'export delle chat WhatsApp:** sul telefono del cliente → apri una chat → ⋮ → Altro → *Esporta
chat* → *Senza file*. Fanne 15-20, quelle con clienti diversi. È da lì che escono le FAQ vere e il
tono: senza, il vault sarà mediocre e il bot suonerà come un chatbot qualunque.

### 2. Scrivimi in chat

Non serve che riassuma tu: il lavoro di leggere il materiale è mio. Basta un messaggio così:

> Nuovo cliente: `studio-rossi`, Studio Dentistico Rossi, Verona.
> Materiale in `vault/clienti/studio-rossi/_materiale/`.
> Canali: WhatsApp (numero storico +39...) e voce.
> Compila il vault e la config, poi dimmi cosa devo fare io a mano.

### 3. Cosa faccio io, cosa fai tu

| Io (Claude) | Tu (Marco) |
|---|---|
| Leggo il materiale e compilo gli 8 file del vault | Fai la call e raccogli il materiale |
| Genero il prompt dell'Agent ElevenLabs dal vault | Lo incolli nella dashboard |
| Aggiungo il cliente in `config/clienti.json` (`attivo: false`) | Colleghi Evolution, Twilio, la deviazione |
| Ti mostro il DIFF prima di applicare qualsiasi cosa | Approvi, testi, e accendi (`attivo: true`) |

**Prima di scrivere qualsiasi file ti mostro il piano.** Se qualcosa nel materiale è ambiguo (orari
contraddittori tra sito e call, prezzi che ballano) **te lo chiedo, non lo invento**: un dato
inventato nel vault diventa una risposta sbagliata a un cliente vero.

### 4. Poi

- Setup tecnico: [[Checklist onboarding]]
- WhatsApp e workflow: [[Setup n8n e LLM]]
- Canale voce: [[Setup canale voce]]

## Fase 6 — Test prima di accendere

Mai accendere su clienti veri senza aver testato. Manda tu 8-10 messaggi al bot:
orari, prezzo di un servizio, prenotazione, disdetta, una domanda che deve rifiutare, un finto
reclamo (deve escalare), un servizio che non fanno (deve dire **no**, non "vediamo").

Poi falli mandare **anche a lui**: è il momento in cui capisce cosa ha comprato.

## Fase 7 — Consegna

- Spiega cosa fa e cosa **non** fa. Le aspettative gonfiate sono l'unico modo di perdere un
  cliente che funziona.
- Digli come funziona l'escalation e come si riattiva il bot.
- **Fissa la revisione a 2 settimane.** Da lì in poi la curatela del vault è il servizio: ogni
  escalation è una domanda che il vault non copriva e che diventa una FAQ nuova. È questo che
  giustifica i 400€/mese, non "l'AI che gira".

## Fase 8 — Migrazione a 360dialog

Appena il canale ufficiale è pronto:

1. Il cliente fa l'Embedded Signup di Meta (solo lui può, serve il suo Business Manager)
2. Si cambia `"provider": "360dialog"` in `config/clienti.json`
3. **Il workflow n8n non si tocca.** Nessun downtime per gli altri clienti.
4. Si stacca Evolution dal numero storico.

Da quel momento il rischio ban non esiste più.
