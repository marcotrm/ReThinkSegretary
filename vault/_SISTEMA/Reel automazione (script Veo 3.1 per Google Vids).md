# REEL "Si può automatizzare tutto?" — script di produzione Veo 3.1 su Google Vids

Fonte: idea video di Marco (27/07/2026). Durata finale ~45s, 9:16 verticale.

## Vincoli tecnici da sapere PRIMA

1. **Veo 3.1 genera clip di max 8 secondi** → il reel è spezzato in 6 clip da montare
   in sequenza dentro Google Vids (o CapCut). L'audio/dialogo lo genera Veo stesso.
2. **Coerenza del personaggio**: Veo non "ricorda" tra una clip e l'altra. Ogni prompt
   ripete PAROLA PER PAROLA lo stesso blocco descrittivo dei personaggi e del set
   (blocco CONSISTENCY qui sotto). In Google Vids, se disponibile, usa la stessa
   immagine di riferimento ("ingredients"/first frame) per tutte le clip.
3. **Non si può usare la faccia del vero Michele**: Veo blocca la generazione di
   persone reali riconoscibili. Due strade:
   - **A (tutto AI)**: un "consulente" attore sintetico — è quello di questi prompt.
   - **B (ibrida, consigliata per autenticità)**: girate voi Michele col telefono
     (le battute sono semplici) e usate Veo solo per gli inserti/ologrammi/B-roll.
4. I **testi a schermo NON vanno chiesti a Veo** (sbaglia l'ortografia): si
   aggiungono dopo in Google Vids come overlay, in magenta #E6027E.
5. Genera **2-3 take per clip** e tieni la migliore: il dialogo in italiano a volte
   esce con accento strano, riprova finché è pulito.

## Blocco CONSISTENCY (da incollare identico in testa a ogni prompt)

```
A vertical 9:16 video. Setting: a modern, elegant, minimalist marketing agency
office in Italy — white walls, warm wood desk, soft daylight from a large window
on the left, a subtle magenta (#E6027E) LED strip glowing on a shelf in the
background. Two people at the desk: MICHELE, an Italian marketing consultant in
his early 30s, short dark hair, light stubble, wearing a plain black crew-neck
sweater, calm confident demeanor, facing the camera. THE CLIENT, a man in his
40s with brown hair, grey blazer, seen only from behind, slightly out of focus
in the foreground. Cinematic look, shallow depth of field, 35mm lens feel,
professional color grade. All spoken dialogue is in ITALIAN with natural Italian
accent. No background music. No on-screen text, no captions, no subtitles.
```

## Le 6 clip (prompt = CONSISTENCY + il testo della clip)

### CLIP 1 — Hook (8s)
```
Close-up on Michele, the client's shoulder in the blurred foreground. The client
asks in Italian, curious tone: "Posso collegare il mio sito direttamente a
WhatsApp?" Michele answers immediately, relaxed and sure: "Sì, certo." A tiny
confident nod. Static camera, subtle slow push-in.
```
Overlay in Vids (0.5s dopo il "Sì, certo"): `IL TUO SITO PUÒ FARE **MOLTO PIÙ** DI QUANTO PENSI` — "MOLTO PIÙ" in #E6027E, resto bianco.

### CLIP 2 — Le possibilità, parte 1 (8s)
```
Rhythmic shot-reverse-shot between the client (from behind) and Michele. The
client asks in Italian: "Posso collegarlo anche al mio gestionale?" Michele:
"Sì, certo." Client: "Può inviare automaticamente messaggi ai clienti?"
Michele: "Sì, certo." Each answer is quick, the pace slightly accelerating.
As Michele answers, small elegant magenta holographic UI panels appear floating
beside him — a chat bubble icon, a database icon — premium translucent digital
interfaces, subtle, small, not cartoonish.
```
Overlay: nessuno (gli ologrammi bastano).

### CLIP 3 — Le possibilità, parte 2 (8s)
```
Same rhythm, energy rising. The client asks in Italian: "Può acquisire i
contatti e dividerli in base alle richieste?" Michele: "Sì, certo." Client:
"Può capire quando devo riordinare i prodotti?" Michele: "Sì, certo." More
small magenta holographic panels accumulate around Michele — a contacts list,
a rising chart — floating softly like premium AR interfaces.
```
Overlay a comparsa rapida (uno per risposta): `CRM` · `AUTOMAZIONI` in #E6027E, font pulito, piccoli, angolo alto.

### CLIP 4 — Il livello sale (8s)
```
The client leans forward, genuinely interested now. He asks in Italian: "Può
prevedere quando finiranno le scorte?" Michele: "Sì, certo." Client: "E può
mostrarmi quali prodotti venderò di più il mese prossimo?" Michele allows a
small confident smile and says: "Anche questo." Slow push-in on Michele on the
last line. The magenta holograms glow slightly brighter.
```
Overlay in sequenza: `RIASSORTIMENTO AUTOMATICO` → `PREVISIONE DELLE SCORTE` → `ANALISI DELLE VENDITE`.

### CLIP 5 — Svolta comica (8s)
```
The pace suddenly stops. A beat of silence. The client lowers his voice, dead
serious, and asks in Italian: "Ma... può anche ascoltare gli audio di mia
moglie al posto mio?" One full second of silence. Michele looks at him, then
turns his eyes straight into the camera, deadpan, and says: "Sì, certo..."
short pause "...ma non so se ti conviene." The client stays perfectly still.
Michele holds back a smile. Comic timing, dry humor.
```
Overlay: nessuno — la comicità va lasciata pulita.

### CLIP 6 — Messaggio finale + CTA (8s)
```
Michele turns fully toward the camera, tone now authoritative and warm. He
says in Italian: "Ci sono cose che non possiamo delegare. Per tutto il resto,
non chiederti se si può fare. Chiediti quanto ti sta costando non averlo
ancora fatto." Slow steady push-in, the office softly blurring behind him,
the magenta LED glow visible. He holds eye contact with the camera at the end.
```
Overlay finale (ultimi 2s + coda di 3s con fermo immagine o sfondo nero in Vids):
`VUOI UN SISTEMA CHE LAVORI PER TE?`
`SCRIVI "AUTOMAZIONE" NEI COMMENTI` (in #E6027E)
Logo NIA piccolo in basso + `NEVER INVISIBLE AGAIN`.

> Nota: ho usato direttamente la chiusura "versione incisiva" di Marco — è più forte
> e trasforma lo sketch in lead generation. La CTA parlata ("Seguici per scoprire...")
> è stata tolta per stare negli 8s: la CTA scritta lavora meglio con l'audio finale.

## Montaggio in Google Vids (10 minuti)

1. Nuovo video → formato verticale → **Genera con Veo**: incolla CONSISTENCY + Clip 1;
   rigenera finché il labiale/accento è pulito; ripeti per le 6 clip.
2. Trascina le clip in sequenza sulla timeline, taglia le code morte (ogni clip
   Veo ha spesso 0.5-1s di aria all'inizio/fine): il totale deve stare sui 40-45s.
3. Aggiungi gli overlay di testo indicati sopra: font sans pulito (Inter/Poppins),
   bianco + magenta #E6027E, animazione "fade" veloce, MAI più di 2 righe.
4. Coda finale: 3s con sfondo scuro, CTA + logo + NEVER INVISIBLE AGAIN.
5. Niente musica di libreria sopra i dialoghi (Veo genera già l'ambiente sonoro);
   eventualmente un sottofondo molto basso solo su clip 6 + coda.
6. Esporta 1080x1920 → i sottotitoli falli mettere a Instagram (o CapCut auto-caption
   in italiano): aumentano la retention e la puntualità del timing comico.

## Se il risultato AI non convince (piano B ibrido)

Girate Michele davvero (2 minuti di riprese, telefono su treppiede, stessa posizione):
le domande del cliente possono restare generate da Veo (è di spalle: nessun problema
di coerenza volto) oppure essere solo voce fuori campo. Gli ologrammi magenta si
aggiungono in Vids con stickers/overlay. Autenticità > perfezione per un profilo
che deve vendere fiducia locale.
