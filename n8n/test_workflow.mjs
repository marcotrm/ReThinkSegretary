/**
 * Test del workflow n8n. Gira senza n8n:
 *
 *     node n8n/test_workflow.mjs
 *
 * Verifica due cose diverse:
 *
 * 1. INTEGRITA' STRUTTURALE — che il JSON sia importabile: ogni connessione punta a un
 *    nodo che esiste, nessun nodo e' orfano, e (la piu' importante) NESSUN riferimento a
 *    un cliente specifico. Il workflow e' uno solo per tutti: se qualcuno ci scrive dentro
 *    "demo-dentista", il multi-tenant e' gia' rotto.
 *
 * 2. LOGICA DI DECISIONE — il codice del nodo "Decidi cosa fare" viene estratto dal JSON
 *    ed eseguito davvero contro casi limite: LLM giu', confidenza bassa, reclamo, urgenza,
 *    conversazione infinita. E' il nodo che decide se un cliente vero riceve una risposta
 *    inventata o una escalation.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const QUI = dirname(fileURLToPath(import.meta.url));
const wf = JSON.parse(readFileSync(join(QUI, "workflow-segretaria.json"), "utf8"));

let falliti = 0;
const ok = (nome) => console.log(`  [OK] ${nome}`);
const ko = (nome, dettaglio) => {
  console.log(`  [X]  ${nome}\n       ${dettaglio}`);
  falliti++;
};
const check = (nome, cond, dettaglio = "") => (cond ? ok(nome) : ko(nome, dettaglio));

console.log("\n=== 1. Integrita' strutturale ===");

const nomi = new Set(wf.nodes.map((n) => n.name));
check("nodi con nome univoco", nomi.size === wf.nodes.length);

const rotte = [];
for (const [da, conn] of Object.entries(wf.connections)) {
  if (!nomi.has(da)) rotte.push(`sorgente inesistente: '${da}'`);
  for (const uscita of conn.main ?? []) {
    for (const c of uscita ?? []) {
      if (!nomi.has(c.node)) rotte.push(`'${da}' punta a un nodo inesistente: '${c.node}'`);
    }
  }
}
check("tutte le connessioni puntano a nodi esistenti", rotte.length === 0, rotte.join("\n       "));

const raggiunti = new Set(["Messaggio in arrivo"]);
for (const conn of Object.values(wf.connections)) {
  for (const uscita of conn.main ?? []) for (const c of uscita ?? []) raggiunti.add(c.node);
}
const orfani = [...nomi].filter((n) => !raggiunti.has(n));
check("nessun nodo orfano", orfani.length === 0, `orfani: ${orfani.join(", ")}`);

// La regola non negoziabile del progetto.
const testo = JSON.stringify(wf);
const clienti = ["demo-dentista", "demo-parrucchiere", "Studio Dentistico", "Salone Bellezza"];
const trovati = clienti.filter((c) => testo.includes(c));
check(
  "NESSUN cliente cablato nel workflow (multi-tenant)",
  trovati.length === 0,
  `trovati: ${trovati.join(", ")} — il workflow deve essere identico per tutti i clienti`
);

const switchProvider = wf.nodes.find((n) => n.name === "Quale provider?");
check(
  "il provider WhatsApp e' un ramo, non un cablaggio",
  switchProvider?.parameters?.rules?.values?.length === 2,
  "servono i due rami evolution / 360dialog"
);

console.log("\n=== 2. Logica di decisione (nodo 'Decidi cosa fare') ===");

// Estraggo il codice vero dal JSON ed eseguo la funzione: se cambio il nodo e rompo la
// logica, questo test se ne accorge.
const codice = wf.nodes.find((n) => n.name === "Decidi cosa fare").parameters.jsCode;

function decidi({ contesto, rispostaLLM }) {
  const $ = () => ({ first: () => ({ json: contesto }) });
  const $input = { first: () => ({ json: rispostaLLM }) };
  const fn = new Function("$", "$input", codice);
  return fn($, $input)[0].json;
}

const contestoBase = (stato = {}) => ({
  tenant: { client_id: "x", nome: "X", soglia_confidenza: 0.6 },
  messaggio: { testo: "ciao" },
  telefono: "39333",
  vault: {},
  conversazione: { stato, bot_in_pausa: false },
});

const llm = (obj, statusCode = 200) => ({
  statusCode,
  body: { choices: [{ message: { content: JSON.stringify(obj) } }] },
});

let r;

r = decidi({ contesto: contestoBase(), rispostaLLM: llm({ intento: "info", confidenza: 0.9 }) });
check("domanda chiara -> risponde", r.azione === "rispondi", `azione=${r.azione}`);

r = decidi({ contesto: contestoBase(), rispostaLLM: llm({ intento: "prenota", confidenza: 0.9 }) });
check("prenotazione -> calendario", r.azione === "calendario", `azione=${r.azione}`);

r = decidi({ contesto: contestoBase(), rispostaLLM: llm({ intento: "info", confidenza: 0.4 }) });
check("confidenza sotto soglia -> escalation", r.azione === "escalation", `azione=${r.azione}`);

r = decidi({ contesto: contestoBase(), rispostaLLM: llm({ intento: "reclamo", confidenza: 0.99 }) });
check(
  "reclamo -> escalation ANCHE con confidenza alta",
  r.azione === "escalation",
  `azione=${r.azione} — un reclamo non lo gestisce mai la AI`
);

r = decidi({ contesto: contestoBase(), rispostaLLM: llm({ intento: "urgenza", confidenza: 0.99 }) });
check("urgenza -> escalation", r.azione === "escalation", `azione=${r.azione}`);

r = decidi({ contesto: contestoBase(), rispostaLLM: { statusCode: 500, body: {} } });
check(
  "LLM giu' -> escalation, non si improvvisa",
  r.azione === "escalation",
  `azione=${r.azione}`
);

r = decidi({
  contesto: contestoBase(),
  rispostaLLM: { statusCode: 200, body: { choices: [{ message: { content: "non sono JSON" } }] } },
});
check("LLM risponde spazzatura -> escalation", r.azione === "escalation", `azione=${r.azione}`);

r = decidi({
  contesto: contestoBase({ giri: 8 }),
  rispostaLLM: llm({ intento: "info", confidenza: 0.9 }),
});
check(
  "conversazione che non si sblocca (9 giri) -> escalation",
  r.azione === "escalation",
  `azione=${r.azione}`
);

r = decidi({
  contesto: contestoBase({ giri: 2 }),
  rispostaLLM: llm({ intento: "info", confidenza: 0.9 }),
});
check("conversazione breve -> continua a rispondere", r.azione === "rispondi", `azione=${r.azione}`);

// La soglia arriva dal tenant, non e' una costante nel codice.
const severo = contestoBase();
severo.tenant.soglia_confidenza = 0.95;
r = decidi({ contesto: severo, rispostaLLM: llm({ intento: "info", confidenza: 0.9 }) });
check(
  "la soglia di confidenza viene dal cliente, non e' cablata",
  r.azione === "escalation",
  `con soglia 0.95 e confidenza 0.9 doveva escalare, invece azione=${r.azione}`
);

console.log("\n=== 3. Risposta dell'LLM (nodo 'Risposta valida?') ===");

// Trovato in produzione: Groq ha risposto 429 (rate limit) e il workflow, invece di
// escalare, mandava al cliente "Le faccio sapere a breve." e poi piu' niente. Un
// vicolo cieco, senza che nessuno venisse avvisato.
const codiceRisposta = wf.nodes.find((n) => n.name === "Risposta valida?").parameters.jsCode;

function verificaRisposta(rispostaLLM) {
  const ctx = { tenant: { client_id: "x" }, telefono: "39333", azione: "rispondi" };
  const $ = () => ({ first: () => ({ json: ctx }) });
  const $input = { all: () => [{ json: rispostaLLM }] };
  return new Function("$", "$input", codiceRisposta)($, $input)[0].json;
}

let rr = verificaRisposta({
  statusCode: 200,
  body: { choices: [{ message: { content: "Buongiorno. Apriamo alle 9." } }] },
});
check("LLM risponde -> si manda la sua risposta", rr.risposta === "Buongiorno. Apriamo alle 9.");
check("LLM risponde -> nessuna escalation", rr.azione !== "escalation");

rr = verificaRisposta({
  statusCode: 429,
  body: { error: { message: "Rate limit reached for model llama-3.3-70b-versatile" } },
});
check(
  "LLM in rate limit (429) -> ESCALATION, non un messaggio a vuoto",
  rr.azione === "escalation",
  "il cliente riceverebbe 'le faccio sapere a breve' e poi piu' niente"
);
check("LLM in rate limit -> il motivo dice cosa e' successo", /rate limit/i.test(rr.motivo));

rr = verificaRisposta({ statusCode: 200, body: { choices: [{ message: { content: "   " } }] } });
check("LLM risponde il vuoto -> escalation", rr.azione === "escalation");

rr = verificaRisposta({ statusCode: 500, body: {} });
check("LLM in errore 500 -> escalation", rr.azione === "escalation");

console.log("\n=== 4. Escalation (nodo 'Escalation — avvisa il titolare') ===");

const codiceEsc = wf.nodes.find((n) => n.name === "Escalation — avvisa il titolare").parameters
  .jsCode;

/**
 * Esegue il nodo escalation con backend ed Evolution finti, e registra ogni chiamata HTTP.
 * `evolution` decide come si comporta l'invio WhatsApp: 'ok' o 'giu' (eccezione).
 * `env` sovrascrive le variabili n8n (es. per togliere NIAMARKETING_WHATSAPP).
 */
async function eseguiEscalation({ evolution = "ok", tenant = {}, env = {} } = {}) {
  const chiamate = [];
  const dati = {
    tenant: {
      client_id: "x",
      nome: "Attività X",
      instance: "istanza-x",
      escalation: { whatsapp: "+39 333 999 8877", agenda_token: "tok-agenda" },
      ...tenant,
    },
    messaggio: { testo: "ho un dolore fortissimo", nome_contatto: "Mario" },
    telefono: "393331112233",
    motivo: "urgenza",
    conversazione: { stato: {} },
  };

  const ctx = {
    helpers: {
      httpRequest: async (opt) => {
        chiamate.push(opt);
        if (opt.url.includes("/message/sendText/")) {
          if (evolution === "giu") throw new Error("ECONNREFUSED");
          return { key: { id: "finto" } };
        }
        return { ok: true };
      },
    },
  };

  const $env = {
    BACKEND_URL: "http://backend",
    BACKEND_API_KEY: "k",
    EVOLUTION_URL: "http://evolution",
    EVOLUTION_API_KEY: "k-evo",
    NIAMARKETING_WHATSAPP: "+39 333 000 0000",
    ...env,
  };
  const $input = { all: () => [{ json: dati }] };

  const fn = new Function(
    "$env",
    "$input",
    `return (async () => { ${codiceEsc} })()`
  ).bind(ctx);
  const risultato = await fn($env, $input);
  return { risultato: risultato[0].json, chiamate };
}

const invii = (chiamate) => chiamate.filter((c) => c.url.includes("/message/sendText/"));

let e = await eseguiEscalation();
check(
  "mette in pausa il bot",
  e.chiamate.some((c) => c.url.includes("/pausa-bot/393331112233")),
  "nessuna chiamata a pausa-bot"
);
check(
  "avvisa su WhatsApp titolare E NiaMarketing (doppio invio)",
  invii(e.chiamate).length === 2,
  `invii: ${invii(e.chiamate).length}`
);
check(
  "il numero del titolare viene dalla config del CLIENTE, normalizzato",
  invii(e.chiamate).some((c) => c.body?.number === "393339998877")
);
check(
  "il numero NiaMarketing viene dalle variabili n8n, normalizzato",
  invii(e.chiamate).some((c) => c.body?.number === "393330000000")
);
check(
  "l'avviso parte dall'istanza del cliente",
  invii(e.chiamate).every((c) => c.url.endsWith("/message/sendText/istanza-x"))
);
check("segnala l'avviso come inviato", e.risultato.avviso_inviato === true);
check(
  "il cliente riceve comunque una risposta di cortesia",
  typeof e.risultato.risposta === "string" && e.risultato.risposta.length > 10
);
check(
  "l'avviso contiene motivo e messaggio originale",
  e.risultato.avviso_titolare.includes("urgenza") &&
    e.risultato.avviso_titolare.includes("dolore fortissimo")
);
check(
  "l'avviso contiene l'istruzione RIATTIVA col numero del cliente",
  e.risultato.avviso_titolare.includes("RIATTIVA 393331112233")
);
check(
  "l'avviso contiene il link all'agenda con il token del cliente",
  e.risultato.avviso_titolare.includes("http://backend/x/agenda?token=tok-agenda")
);

// La pausa deve avvenire PRIMA dell'avviso: se Evolution e' giu', il bot deve tacere comunque.
const iPausa = e.chiamate.findIndex((c) => c.url.includes("/pausa-bot/"));
const iInvio = e.chiamate.findIndex((c) => c.url.includes("/message/sendText/"));
check(
  "mette in pausa PRIMA di avvisare (se Evolution e' giu', il bot tace lo stesso)",
  iPausa >= 0 && iInvio >= 0 && iPausa < iInvio
);

// Cliente senza agenda_token: l'avviso parte lo stesso, solo senza link.
e = await eseguiEscalation({ tenant: { escalation: { whatsapp: "+393339998877" } } });
check(
  "senza agenda_token l'avviso parte comunque, senza link",
  e.risultato.avviso_inviato === true && !e.risultato.avviso_titolare.includes("agenda?token")
);

// Titolare e NiaMarketing sono lo stesso numero: un solo invio, non due doppioni.
e = await eseguiEscalation({ tenant: { escalation: { whatsapp: "+39 333 000 0000" } } });
check("titolare == NiaMarketing -> un solo invio, niente doppioni", invii(e.chiamate).length === 1);

// Evolution irraggiungibile.
e = await eseguiEscalation({ evolution: "giu" });
check("Evolution giu' -> il nodo non esplode", e.risultato.avviso_inviato === false);
check(
  "Evolution giu' -> logga 'avviso_non_inviato' per ogni destinatario",
  e.chiamate.filter((c) => c.body?.tipo === "avviso_non_inviato").length === 2,
  "un avviso perso in silenzio non lo scopre nessuno"
);
check("Evolution giu' -> il bot e' comunque in pausa", e.chiamate.some((c) => c.url.includes("/pausa-bot/")));
check(
  "Evolution giu' -> il cliente riceve comunque la risposta",
  typeof e.risultato.risposta === "string"
);

// Nessun destinatario da nessuna parte: si logga, non si perde in silenzio.
e = await eseguiEscalation({ tenant: { escalation: {} }, env: { NIAMARKETING_WHATSAPP: "" } });
check(
  "nessun destinatario configurato -> logga 'avviso_non_inviato'",
  e.risultato.avviso_inviato === false &&
    e.chiamate.some((c) => c.body?.tipo === "avviso_non_inviato")
);

check(
  "nessun riferimento a Slack rimasto nel workflow",
  !/slack/i.test(testo),
  "l'escalation ora viaggia su WhatsApp"
);

console.log("\n=== 5. Comando RIATTIVA (nodo 'Comando dal titolare (RIATTIVA)') ===");

const codiceCmd = wf.nodes.find((n) => n.name === "Comando dal titolare (RIATTIVA)").parameters
  .jsCode;

/** Esegue il nodo comando: `mittente` e `testo` simulano il messaggio in arrivo. */
async function eseguiComando({ mittente, testo, env = {} } = {}) {
  const chiamate = [];
  const tenant = {
    client_id: "x",
    instance: "istanza-x",
    escalation: { whatsapp: "+39 333 999 8877" },
  };
  const msg = { numero_mittente: mittente, testo };

  const ctx = { helpers: { httpRequest: async (opt) => { chiamate.push(opt); return { ok: true }; } } };
  const $ = () => ({ first: () => ({ json: msg }) });
  const $env = {
    BACKEND_URL: "http://backend",
    BACKEND_API_KEY: "k",
    EVOLUTION_URL: "http://evolution",
    EVOLUTION_API_KEY: "k-evo",
    NIAMARKETING_WHATSAPP: "+39 333 000 0000",
    ...env,
  };
  const $input = { all: () => [{ json: { statusCode: 200, body: tenant } }] };

  const fn = new Function("$", "$env", "$input", `return (async () => { ${codiceCmd} })()`).bind(ctx);
  return { risultato: await fn($, $env, $input), chiamate };
}

let c = await eseguiComando({ mittente: "393339998877@s.whatsapp.net", testo: "RIATTIVA 393331112233" });
check(
  "titolare scrive RIATTIVA <numero> -> chiama riattiva-bot",
  c.chiamate.some((x) => x.url === "http://backend/x/riattiva-bot/393331112233")
);
check("comando eseguito -> il flusso si FERMA (niente classificatore)", c.risultato.length === 0);
check(
  "il titolare riceve la conferma, subito e senza ritardo umano",
  c.chiamate.some((x) => x.url.includes("/message/sendText/") && /riattivato/i.test(x.body?.text))
);

c = await eseguiComando({ mittente: "393339998877@s.whatsapp.net", testo: "riattiva +39 333 111 22 33" });
check(
  "numero formattato con spazi e prefisso -> normalizzato",
  c.chiamate.some((x) => x.url.endsWith("/riattiva-bot/393331112233"))
);

c = await eseguiComando({ mittente: "393330000000@s.whatsapp.net", testo: "RIATTIVA 393331112233" });
check(
  "anche NiaMarketing puo' riattivare",
  c.chiamate.some((x) => x.url.includes("/riattiva-bot/393331112233"))
);

c = await eseguiComando({ mittente: "393339998877@s.whatsapp.net", testo: "riattiva" });
check(
  "RIATTIVA senza numero -> chiede il numero, non riattiva nessuno",
  !c.chiamate.some((x) => x.url.includes("/riattiva-bot/")) &&
    c.chiamate.some((x) => x.url.includes("/message/sendText/")) &&
    c.risultato.length === 0
);

c = await eseguiComando({ mittente: "393339998877@s.whatsapp.net", testo: "ciao, com'è andata oggi?" });
check(
  "messaggio normale del titolare -> passa oltre come un cliente qualunque",
  c.risultato.length === 1 && c.chiamate.length === 0
);
check(
  "il passthrough conserva il tenant per il nodo successivo",
  c.risultato[0]?.json?.body?.client_id === "x"
);

c = await eseguiComando({ mittente: "393317654321@s.whatsapp.net", testo: "RIATTIVA 393331112233" });
check(
  "un cliente qualunque che scrive RIATTIVA non comanda niente",
  c.risultato.length === 1 && !c.chiamate.some((x) => x.url.includes("/riattiva-bot/")),
  "solo i numeri di escalation sono autorizzati"
);

console.log("\n=== 6. Fallback LLM (classificazione e generazione risposta) ===");

/**
 * Esegue un nodo LLM (classifica o rispondi) con provider finti.
 * `primario`/`fallback`: 'ok' o un numero di stato HTTP con cui fallire.
 */
async function eseguiLLM(nomeNodo, { primario = "ok", fallback = "ok", env = {} } = {}) {
  const codiceLLM = wf.nodes.find((n) => n.name === nomeNodo).parameters.jsCode;
  const chiamate = [];
  const rispostaBuona = { choices: [{ message: { content: '{"intento":"info","confidenza":0.9}' } }] };

  const ctx = {
    helpers: {
      httpRequest: async (opt) => {
        chiamate.push(opt);
        const esito = opt.url.includes("primario") ? primario : fallback;
        if (esito !== "ok") {
          const err = new Error(`Request failed with status code ${esito}`);
          err.response = { status: esito };
          throw err;
        }
        return rispostaBuona;
      },
    },
  };

  const $env = {
    LLM_URL: "http://primario/v1/chat",
    LLM_API_KEY: "k1",
    LLM_MODEL: "llama-primario",
    LLM_FALLBACK_URL: "http://riserva/v1/chat",
    LLM_FALLBACK_KEY: "k2",
    LLM_FALLBACK_MODEL: "llama-riserva",
    ...env,
  };
  const dati = {
    vault: { servizi: "Pulizia — 80€", "brand-voice": "cordiale", orari: "9-18", faq: "", vincoli: "" },
    messaggio: { testo: "che orari fate?" },
  };
  const $input = { all: () => [{ json: dati }] };

  const fn = new Function("$env", "$input", `return (async () => { ${codiceLLM} })()`).bind(ctx);
  const risultato = await fn($env, $input);
  return { esito: risultato[0].json, chiamate };
}

for (const nomeNodo of ["Classifica intento (Llama)", "Genera risposta dal vault"]) {
  const corto = nomeNodo === "Classifica intento (Llama)" ? "classifica" : "rispondi";

  let l = await eseguiLLM(nomeNodo);
  check(
    `[${corto}] primario ok -> una sola chiamata, nessun fallback`,
    l.esito.statusCode === 200 && l.chiamate.length === 1 && l.chiamate[0].url.includes("primario")
  );
  check(
    `[${corto}] il modello del primario viene dalle variabili`,
    l.chiamate[0].body?.model === "llama-primario"
  );

  l = await eseguiLLM(nomeNodo, { primario: 429 });
  check(
    `[${corto}] primario in quota (429) -> ritenta sulla riserva e risponde`,
    l.esito.statusCode === 200 && l.chiamate.length === 2 && l.chiamate[1].url.includes("riserva")
  );
  check(
    `[${corto}] la riserva usa il SUO modello`,
    l.chiamate[1].body?.model === "llama-riserva"
  );
  check(
    `[${corto}] primario e riserva ricevono lo STESSO prompt`,
    JSON.stringify(l.chiamate[0].body.messages) === JSON.stringify(l.chiamate[1].body.messages),
    "se i prompt divergono, il fallback risponde in un altro modo"
  );

  l = await eseguiLLM(nomeNodo, { primario: 429, fallback: 500 });
  check(
    `[${corto}] falliscono entrambi -> statusCode non-200, a valle si escala`,
    l.esito.statusCode !== 200 && l.esito.body?.error?.message
  );

  l = await eseguiLLM(nomeNodo, {
    primario: 429,
    env: { LLM_FALLBACK_URL: "", LLM_FALLBACK_KEY: "" },
  });
  check(
    `[${corto}] riserva non configurata -> niente secondo tentativo, si escala`,
    l.esito.statusCode === 429 && l.chiamate.length === 1
  );
}

console.log(
  falliti === 0
    ? `\n[OK] workflow valido — ${wf.nodes.length} nodi, tutti i test passati\n`
    : `\n[X] ${falliti} test falliti\n`
);
process.exit(falliti === 0 ? 0 : 1);
