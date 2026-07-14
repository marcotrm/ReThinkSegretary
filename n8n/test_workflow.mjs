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

console.log(
  falliti === 0
    ? `\n[OK] workflow valido — ${wf.nodes.length} nodi, tutti i test passati\n`
    : `\n[X] ${falliti} test falliti\n`
);
process.exit(falliti === 0 ? 0 : 1);
