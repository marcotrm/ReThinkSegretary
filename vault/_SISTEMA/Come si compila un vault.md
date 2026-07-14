---
tipo: guida
aggiornato_il: 2026-07-14
---

# Come si compila un vault

Gli 8 file non sono documentazione: sono **il cervello del sistema**. Quello che c'è scritto
qui è quello che il cliente finale si sente rispondere. Quello che manca, la AI lo inventa
o lo escala.

## Da dove viene il materiale

| Fonte | Cosa ne tiri fuori |
|---|---|
| **Vecchie chat WhatsApp** | Le FAQ vere e il tono vero. Vale più di tutto il resto messo insieme. |
| Call di onboarding | Vincoli, eccezioni, "ah, ma questo non ditelo mai" |
| Recensioni Google | Cosa va storto, cosa la gente chiede prima di venire |
| Sito / listino | Servizi, prezzi, durate |

Se hai le vecchie chat, **parti da lì**: apri 50 conversazioni, conta quali domande tornano.
Le prime dieci sono le tue FAQ. Il modo in cui il titolare risponde è la tua brand voice.

## I file, in ordine di importanza

**`brand-voice.md` è il più importante e quasi sempre il più trascurato.** Tre aggettivi non
insegnano niente a un modello. Gli esempi ✅/❌ sì. Scrivine almeno quattro, presi da chat
reali, e includi sempre:

- un caso in cui deve dire **no** (servizio non offerto)
- un caso delicato (dolore, reclamo, disdetta)
- un caso in cui **non deve confermare** perché il calendario non ha risposto

**`vincoli.md`** sono le linee rosse. Regola pratica: se una risposta sbagliata può creare un
danno (medico, legale, economico) o una promessa che il cliente dovrà mantenere, sta qui.

**`faq.md`** deve contenere la **risposta esatta da mandare**, non un riassunto. Se scrivi
"spiegare la politica di disdetta", la AI improvviserà.

**`servizi.md`**: metti i **sinonimi che usano i clienti**, non i nomi tecnici. La gente scrive
"pulizia dei denti", non "detartrasi"; "tinta", non "colorazione permanente".

**`orari.md`** e **`prenotazioni.md`** finiscono nella config del calendario. Devono essere
esatti al minuto: qui un errore diventa un appuntamento che non esiste.

**`obiettivi.md`** non finisce nel prompt. È per noi: perché ci paga, cosa considera un
successo, cosa nel vault è ancora debole. È la nota su cui si appoggia il rinnovo.

## Regole

1. **Niente duplicazione.** Gli orari stanno solo in `orari.md`, i parametri calendario solo
   in `prenotazioni.md`. Se ripeti un dato in due file, prima o poi diranno cose diverse — e
   scoprirai quale delle due il sistema legge solo quando un cliente si lamenta.
2. **Zero segnaposto.** Un `<<...>>` rimasto finisce nel prompt e la AI lo legge.
3. **Dopo ogni modifica:** `python scripts/verifica_coerenza.py`.
4. **Nel dubbio, escala.** Meglio un "la faccio richiamare" in più che una risposta inventata.

## La curatela (è questo che il cliente paga)

Il vault non si compila una volta. Ogni settimana:

- guarda le **escalation**: ogni escalation è una domanda che il vault non copriva → diventa
  una FAQ nuova
- guarda le conversazioni andate male: che regola mancava?
- aggiorna `obiettivi.md` con cosa hai sistemato

Questo è il lavoro ricorrente che giustifica i 400€/mese. Non "l'AI che gira".
