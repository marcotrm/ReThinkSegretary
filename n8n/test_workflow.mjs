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

console.log("\n=== 3. Escalation (nodo 'Escalation — avvisa il titolare') ===");

const codiceEsc = wf.nodes.find((n) => n.name === "Escalation — avvisa il titolare").parameters
  .jsCode;

/**
 * Esegue il nodo escalation con backend e Slack finti, e registra ogni chiamata HTTP.
 * `slack` decide come si comporta Slack: 'ok', 'errore' (200 ma ok:false — il modo in cui
 * Slack fallisce davvero) o 'giu' (eccezione).
 */
async function eseguiEscalation({ slack = "ok", tenant = {} } = {}) {
  const chiamate = [];
  const dati = {
    tenant: {
      client_id: "x",
      nome: "Attività X",
      escalation: { slack_channel: "#canale-cliente" },
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
        if (opt.url.includes("slack.com")) {
          if (slack === "giu") throw new Error("ECONNREFUSED");
          return slack === "ok" ? { ok: true } : { ok: false, error: "channel_not_found" };
        }
        return { ok: true };
      },
    },
  };

  const $env = {
    BACKEND_URL: "http://backend",
    BACKEND_API_KEY: "k",
    SLACK_BOT_TOKEN: "xoxb-finto",
    SLACK_CHANNEL_DEFAULT: "#fallback",
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

let e = await eseguiEscalation({ slack: "ok" });
check(
  "mette in pausa il bot",
  e.chiamate.some((c) => c.url.includes("/pausa-bot/393331112233")),
  "nessuna chiamata a pausa-bot"
);
check(
  "avvisa su Slack",
  e.chiamate.some((c) => c.url.includes("slack.com/api/chat.postMessage")),
  "nessun avviso Slack"
);
check(
  "usa il canale Slack DEL CLIENTE, non uno fisso",
  e.chiamate.find((c) => c.url.includes("slack.com"))?.body?.channel === "#canale-cliente"
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

// La pausa deve avvenire PRIMA dell'avviso: se Slack e' giu', il bot deve tacere comunque.
const iPausa = e.chiamate.findIndex((c) => c.url.includes("/pausa-bot/"));
const iSlack = e.chiamate.findIndex((c) => c.url.includes("slack.com"));
check(
  "mette in pausa PRIMA di avvisare (se Slack e' giu', il bot tace lo stesso)",
  iPausa >= 0 && iSlack >= 0 && iPausa < iSlack
);

// Slack risponde 200 con ok:false — il modo in cui Slack fallisce davvero.
e = await eseguiEscalation({ slack: "errore" });
check("Slack risponde 200 ma ok:false -> non lo conta come inviato", e.risultato.avviso_inviato === false);
check(
  "Slack fallito -> logga l'evento 'avviso_non_inviato'",
  e.chiamate.some((c) => c.body?.tipo === "avviso_non_inviato"),
  "un avviso perso in silenzio non lo scopre nessuno"
);
check("Slack fallito -> il bot resta comunque in pausa", e.chiamate.some((c) => c.url.includes("/pausa-bot/")));

// Slack irraggiungibile.
e = await eseguiEscalation({ slack: "giu" });
check("Slack giu' -> il nodo non esplode", e.risultato.avviso_inviato === false);
check("Slack giu' -> il bot e' comunque in pausa", e.chiamate.some((c) => c.url.includes("/pausa-bot/")));
check(
  "Slack giu' -> il cliente riceve comunque la risposta",
  typeof e.risultato.risposta === "string"
);

// Cliente senza canale configurato: si usa il fallback, non si perde l'avviso.
e = await eseguiEscalation({ tenant: { escalation: {} } });
check(
  "cliente senza canale -> fallback, l'avviso non si perde",
  e.chiamate.find((c) => c.url.includes("slack.com"))?.body?.channel === "#fallback"
);

check(
  "nessun token Slack scritto nel JSON del workflow",
  !/xoxb-[A-Za-z0-9]/.test(testo),
  "i segreti vanno nelle Variables di n8n"
);

console.log(
  falliti === 0
    ? `\n[OK] workflow valido — ${wf.nodes.length} nodi, tutti i test passati\n`
    : `\n[X] ${falliti} test falliti\n`
);
process.exit(falliti === 0 ? 0 : 1);
