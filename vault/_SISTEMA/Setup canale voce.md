---
tipo: procedura
aggiornato_il: 2026-07-14
---

# Setup canale voce — Twilio + ElevenLabs + Deepgram

Da `[[🏠 HOME]]`. È il pezzo di [[Checklist onboarding]] (punti 4 e 6) che **Claude non può fare**:
richiede login, acquisti e configurazioni su account esterni. **La esegue Marco a mano.**

Ordine di esecuzione: **prima Twilio** (serve il numero), **poi ElevenLabs** (l'agent che risponde),
**poi Deepgram** (la chiave è già condivisa: di solito non c'è niente da fare), **infine si annota
tutto** e si testa.

> [!warning] Prerequisito
> Il vault del cliente deve essere già compilato e il cliente deve esistere in `config/clienti.json`
> con `attivo: false`. Il prompt dell'agent si genera dal vault, non si scrive a mano qui.

---

## 1. Twilio — numero e deviazione di chiamata

### 1.1 Comprare/assegnare il numero

1. Entra nella console Twilio con l'account NiaMarketing.
2. Compra un **numero italiano** (voice-enabled) dedicato al cliente. Un numero per cliente: mai
   riusare lo stesso numero per due tenant, perché il numero è la chiave con cui il sistema risolve
   il `client_id`.
3. Segnati il numero in formato E.164 (`+39...`). Ti serve al punto 4.

> [!note] Numeri italiani e documenti
> Per i numeri geografici italiani Twilio chiede in genere una *regulatory bundle* (documento di
> identità / dati dell'intestatario, a volte un indirizzo locale). Preparala prima: l'approvazione
> non è istantanea. **Da verificare in console** quali documenti chiede il tipo di numero scelto.

### 1.2 Collegare il numero all'agent ElevenLabs

Il numero Twilio deve consegnare la chiamata in entrata all'agent vocale. ElevenLabs, nella sezione
dei numeri di telefono del Conversational AI, permette di collegare un numero Twilio fornendo
**Account SID** e **Auth Token** e poi associandolo a un agent; in alternativa si configura a mano
il webhook "A call comes in" del numero Twilio verso l'endpoint fornito da ElevenLabs.

- Fai **prima** il punto 2 (crea l'agent), poi torna qui e associa numero → agent.
- **Da verificare in dashboard:** il nome esatto della sezione ElevenLabs e se conviene la strada
  "importa numero Twilio" o quella "webhook manuale sul numero Twilio". Usa quella che la dashboard
  propone: non inventare URL di webhook a mano.

### 1.3 Deviazione di chiamata (la fa IL CLIENTE)

Questo è il punto che salta sempre. **La deviazione la attiva il cliente col proprio operatore
(TIM, Vodafone, WindTre, Iliad…), non noi.** Noi non abbiamo accesso alla sua linea e non possiamo
attivarla al posto suo. Noi gli diamo solo il numero Twilio e le istruzioni.

Il cliente devia il **numero storico** (quello stampato sui volantini e su Google, che i suoi
clienti chiamano già) verso il **numero Twilio**. Così non deve cambiare nulla di quello che ha
comunicato in giro.

Codici GSM tipici da digitare sul telefono:

| Cosa | Codice | Quando la chiamata arriva alla segretaria |
|---|---|---|
| Deviazione **incondizionata** | `**21*<numero Twilio>#` | Sempre. Il telefono del cliente non squilla proprio. |
| Deviazione **se non risponde** | `**61*<numero Twilio>#` | Solo dopo N squilli a vuoto. |
| Disattivare la deviazione | `##21#` / `##61#` | — |

> [!warning] Vanno confermati con l'operatore
> Questi codici sono lo standard GSM e **funzionano nella maggior parte dei casi, ma non sempre**:
> su linee fisse, VoIP e centralini aziendali la deviazione si attiva dall'area clienti o
> chiamando l'assistenza, e i codici possono cambiare. **Fai confermare al cliente col suo
> operatore** prima di dare per buono che sia attiva. Verifica sempre chiamando (punto 6).

Consiglio pratico: **parti dalla deviazione "se non risponde"** (`**61*`). Il cliente continua a
rispondere quando può, e la segretaria AI prende solo le chiamate perse. Si passa all'incondizionata
solo quando il cliente si fida.

---

## 2. ElevenLabs — Conversational AI Agent (uno per cliente)

Qui l'eccezione al principio multi-tenant è voluta: **il workflow n8n resta uno solo per tutti**, ma
su ElevenLabs serve **un agent per cliente**, perché prompt, voce e tool puntano a un `client_id`
diverso.

### 2.1 Creare l'agent

1. Crea un nuovo **Conversational AI Agent**, nome: `segretaria-<client_id>` (es.
   `segretaria-demo-dentista`). Ci si ritrova quando gli agent diventano dieci.
2. **Prompt di sistema:** incolla quello generato dal vault del cliente, ricavato da
   `brand-voice.md` + `orari.md` + `faq.md` + `vincoli.md`. Non scriverlo a mano nella dashboard:
   se lo scrivi lì, il vault smette di essere la fonte di verità.
3. **Lingua:** italiano.
4. **Voce:** scegli una voce italiana dalla libreria. Ascoltane almeno 2-3 e scegli quella coerente
   con la `brand-voice` del cliente (uno studio medico e un parrucchiere non hanno la stessa voce).
5. **Messaggio iniziale:** una frase sola, che dica chi sta rispondendo. Il cliente finale deve
   capire subito che parla con un assistente, non fingere il contrario.
6. Copia l'**agent_id** che ElevenLabs assegna: serve al punto 4.

### 2.2 I tool del calendario

L'agent deve poter interrogare il calendario. Base URL del servizio:

```
https://web-production-63865.up.railway.app
```

Ogni agent punta **al SUO `client_id`**: l'URL del tool è già completo di segmento cliente. Se
sbagli questo, l'agent di un cliente prenota nel calendario di un altro.

| Tool | Metodo e URL | A cosa serve |
|---|---|---|
| `disponibilita` | `GET /{client_id}/disponibilita?da=&a=&durata_min=&limite=` | Slot liberi da proporre |
| `prenota` | `POST /{client_id}/prenota` | Fissa l'appuntamento |
| `sposta` | `POST /{client_id}/sposta` | Sposta un appuntamento esistente |
| `cancella` | `POST /{client_id}/cancella` | Disdetta |

Body delle POST (i campi sono quelli che il calendar service si aspetta):

- **prenota** → `servizio`, `nome_cliente`, `telefono`, `inizio` (ISO 8601), `durata_min` (opzionale), `note` (opzionale)
- **sposta** → `prenotazione_id`, `nuovo_inizio`
- **cancella** → `prenotazione_id`

**Header obbligatorio su TUTTI i tool:**

```
X-API-Key: <la API key del calendar service>
```

Senza header la chiamata viene rifiutata (401). La key si incolla nella configurazione del tool
lato ElevenLabs, **non** nel prompt e **non** nel repo (vedi punto 5).

> [!note] Da verificare in dashboard
> Il nome esatto della funzionalità ElevenLabs per gli strumenti HTTP (tipo "Tools" / "Webhook
> tool" / "Server tool") e dove si incollano gli header custom. Cerca la sezione dell'agent in cui
> si definiscono strumenti che chiamano un'API esterna e imposta lì URL, metodo, header e schema
> dei parametri.

Descrivi ogni tool all'agent in italiano e in modo chiaro ("usa questo strumento per sapere quali
orari sono liberi prima di proporre un appuntamento"): la qualità della descrizione decide se
l'agent lo chiama al momento giusto o improvvisa.

### 2.3 Escalation

L'agent deve avere un modo esplicito per **passare all'umano** quando non sa gestire il caso (vedi
`escalation.md` del cliente). Finché il nodo di escalation reale non è pronto, il minimo accettabile
è che l'agent dica che farà richiamare un operatore e che la chiamata venga tracciata — non che
inventi una risposta.

---

## 3. Deepgram — speech-to-text

- **Una sola chiave per tutta NiaMarketing, condivisa tra i clienti.** ⛔ Non creare una chiave per
  cliente: non serve, e moltiplica i segreti da ruotare.
- Lingua: **`it`** (italiano).
- Su un cliente nuovo, di norma **qui non c'è niente da fare**: la chiave esiste già ed è nelle
  variabili d'ambiente. Verifica solo che il credito dell'account non sia esaurito.
- **Da verificare:** se lo speech-to-text viene gestito internamente da ElevenLabs
  Conversational AI, Deepgram potrebbe non essere richiesto per il canale voce. Controlla come è
  configurato l'agent prima di collegare Deepgram a mano.

---

## 4. Cosa va annotato, e dove

**Questo è il punto che si dimentica sempre.** Se non annoti, fra sei mesi non sai più quale numero
Twilio appartiene a chi, e quale numero storico è deviato dove.

Per ogni cliente vanno tracciati **quattro dati**:

1. **Numero Twilio** (quello che risponde davvero)
2. **elevenlabs_agent_id**
3. **Numero storico deviato** (quello del cliente, che punta al Twilio)
4. **Data di attivazione**

### Dove si scrivono

**`config/clienti.json`** — è la config che il sistema legge a runtime:

```json
"canali": {
  "voce": {
    "provider": "twilio",
    "numero": "+39...",
    "elevenlabs_agent_id": "agent_..."
  }
}
```

**Scheda cliente del vault** (`📍 <Nome>.md`, sezione *A colpo d'occhio*) — è il riassunto per gli
umani: numero bot, numero storico ⛔ mai collegato a WhatsApp, escalation. Aggiungi lì la riga del
numero voce e l'agent_id se non ci sono.

⛔ **Nessuna API key in questi file.** Vedi punto 5.

### Registro voce — tutti i clienti

| Cliente | client_id | Numero Twilio | Numero storico deviato | ElevenLabs agent_id | Attivato il | Stato |
|---|---|---|---|---|---|---|
| Studio Dentistico Sorriso | `demo-dentista` | +39 000 0000001 | — | — | — | 🟡 test |
| Salone Bellezza | `demo-parrucchiere` | +39 000 0000002 | — | — | — | 🟡 test |

Legenda stato: 🟢 in produzione · 🟡 test/pilota · 🔴 sospeso · ⚪ in onboarding

I due tenant qui sopra sono **di test**: numeri inventati, nessun agent creato, nessuna deviazione
attiva. Quando attivi un cliente vero, aggiungi la riga **qui** e aggiorna `config/clienti.json` e
la sua scheda: i tre posti devono dire la stessa cosa.

---

## 5. Segreti — dove NON vanno

⛔ **Nessuna API key finisce nel repo.** `config/clienti.json` va su git: dentro ci stanno numeri e
id, mai token. Stessa regola per le note del vault.

I segreti stanno **solo** in:

- **variabili d'ambiente su Railway** (per il calendar service e i servizi nostri);
- **credenziali n8n** (per i nodi che chiamano le API esterne);
- **la dashboard del fornitore** (la `X-API-Key` incollata nel tool ElevenLabs sta lì).

Nomi consigliati delle variabili:

| Variabile | Cosa contiene |
|---|---|
| `TWILIO_ACCOUNT_SID` | SID dell'account Twilio |
| `TWILIO_AUTH_TOKEN` | Auth token Twilio |
| `ELEVENLABS_API_KEY` | API key ElevenLabs |
| `DEEPGRAM_API_KEY` | API key Deepgram (una sola, condivisa) |
| `API_KEY` | Chiave del calendar service — è quella che i tool mandano in `X-API-Key` |

Se una chiave finisce per sbaglio in un commit: **va ruotata**, non basta cancellare il file.

---

## 6. Checklist di test — prima di accendere

Nell'ordine, e senza saltarne nessuno. Fino a qui il cliente resta `attivo: false`.

- [ ] **Chiama il numero Twilio.** Risponde l'agent? Con la voce e il tono giusti?
- [ ] **Chiama il numero storico del cliente.** La deviazione funziona davvero e la chiamata
      arriva all'agent? (È l'unico modo per sapere se l'operatore l'ha attivata sul serio.)
- [ ] **Fai prendere un appuntamento vero.** Chiedi un orario, fatti proporre le alternative,
      conferma.
- [ ] **Verifica che l'appuntamento esista davvero:**
      `GET /{client_id}/prenotazioni` con l'header `X-API-Key` → l'appuntamento deve comparire con
      data, ora e nome giusti. Se non c'è, l'agent ha *detto* di aver prenotato senza prenotare:
      è il bug peggiore possibile, si ferma tutto.
- [ ] **Prova a spostare e a disdire** l'appuntamento di test.
- [ ] **Prova l'escalation:** fai una domanda a cui l'agent NON deve rispondere (per il dentista:
      dolore acuto). Deve passare all'umano, non improvvisare.
- [ ] **Cancella gli appuntamenti di test** dal calendario.
- [ ] Solo ora: `attivo: true` in `config/clienti.json`, riga aggiornata nel registro qui sopra e
      nella scheda cliente.

---

## Riepilogo: chi fa cosa

| Passo | Chi |
|---|---|
| Compilare il vault, generare il prompt, aggiornare `config/clienti.json` | Claude |
| Comprare il numero Twilio, creare l'agent ElevenLabs, incollare le key | **Marco** |
| Attivare la deviazione di chiamata dal numero storico | **Il cliente**, col suo operatore |
| Test di chiamata e accensione (`attivo: true`) | **Marco** |
