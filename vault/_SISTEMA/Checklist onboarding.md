---
tipo: procedura
aggiornato_il: 2026-07-14
---

# Checklist onboarding — nuovo cliente

Da `[[🏠 HOME]]`. Tempo realistico: mezza giornata di curatela + le azioni manuali di Marco.

## 1. Raccogli il materiale (prima di scrivere una riga)

- [ ] Call di onboarding registrata o appuntata
- [ ] Sito / pagina Google Business (orari, servizi, indirizzo)
- [ ] **Export delle vecchie chat WhatsApp** ← la miniera d'oro: sono le domande vere
- [ ] Recensioni Google (dicono cosa va storto e cosa la gente chiede)
- [ ] Listino prezzi

Metti tutto in `vault/clienti/<client_id>/_materiale/`.

## 2. Crea il vault

- [ ] Copia `vault/_TEMPLATE/` in `vault/clienti/<client_id>/`
- [ ] Compila gli 8 file — vedi [[Come si compila un vault]]
- [ ] Crea la scheda `📍 <Nome Cliente>.md` (copiane una esistente)
- [ ] Zero segnaposto `<<...>>` rimasti

## 3. Config

- [ ] Aggiungi il cliente in `config/clienti.json`
- [ ] I parametri calendario devono **coincidere** con `prenotazioni.md`
- [ ] Gira `python scripts/verifica_coerenza.py` → deve dire `[OK]`
- [ ] `attivo: false` finché non hai finito di testare

## 4. Agent vocale ElevenLabs

- [ ] Genera il prompt da: `brand-voice` + `orari` + `faq` + `vincoli`
- [ ] Collega i tool agli endpoint del calendario (`/{client_id}/disponibilita`, `prenota`, …)
- [ ] Metti l'`agent_id` in `config/clienti.json`

## 5. Aggiungi la riga in HOME

- [ ] Nuova riga nella tabella clienti di [[🏠 HOME]]

## 6. Azioni manuali — le fa MARCO, non Claude

- [ ] **Numero WhatsApp.** Nel pilota si collega il **numero storico** del cliente a Evolution
      (scelta consapevole, vedi [[Onboarding commerciale]] Fase 4). Prima di collegarlo:
      - [ ] consenso **scritto** del cliente, su WhatsApp
      - [ ] **backup delle chat** fatto dal cliente (Impostazioni → Chat → Backup)
      - [ ] pratica 360dialog **già avviata** (il ponte dev'essere corto)
      Se il cliente preferisce zero rischi: numero nuovo dedicato, e si migra dopo.
- [ ] Collegare il numero a Evolution API (QR dal telefono del cliente)
- [ ] Numero Twilio per la voce
- [ ] **Deviazione di chiamata** dal numero del cliente (es. TIM) al numero Twilio —
      la attiva il cliente col suo operatore
- [ ] Embedded Signup Meta — **lo deve fare il cliente**, non noi

## 7. Test prima di accendere

- [ ] Manda 5-10 messaggi veri al numero del bot: orari, prezzo, prenotazione, disdetta,
      una domanda a cui NON deve rispondere
- [ ] Verifica che l'escalation arrivi davvero al titolare
- [ ] Prenota e controlla che l'appuntamento compaia sul calendario
- [ ] Solo ora: `attivo: true`

## 8. Consegna

- [ ] Spiega al cliente cosa fa e cosa NON fa
- [ ] Digli come riattivare il bot dopo un'escalation
- [ ] Fissa la prima revisione della curatela (2 settimane)
