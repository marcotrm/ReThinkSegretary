"""Scheda cliente e finestre di disponibilita' per la console condivisa Marco + Michele.

Due pagine che vivono dentro l'agenda (stesso token, stesso link):

- SCHEDA CLIENTE: le domande che Michele fa durante la call conoscitiva. Raccoglie in un
  colpo solo la parte commerciale, i materiali disponibili e le domande tecniche (che prima
  faceva Marco in un secondo giro). Da qui esce il brief con cui si genera il sito.
- FINESTRE: i giorni e le fasce in cui Michele accetta chiamate. Alberto propone slot solo
  dentro queste fasce, uno all'ora (call da 30 minuti + 30 di cuscinetto).

Niente tabelle nuove: si appoggiano alla tabella 'eventi' gia' esistente
(tipo 'scheda_cliente' e 'finestre_disponibilita'), cosi' non serve migrare il database.
"""
from __future__ import annotations

import html as html_mod
import json
from datetime import datetime

TIPO_SCHEDA = "scheda_cliente"
TIPO_FINESTRE = "finestre_disponibilita"

GIORNI = [
    ("lun", "Lunedì"), ("mar", "Martedì"), ("mer", "Mercoledì"), ("gio", "Giovedì"),
    ("ven", "Venerdì"), ("sab", "Sabato"), ("dom", "Domenica"),
]

# (chiave, domanda, tipo, opzioni)  tipo: testo | lungo | scelta | multi
BLOCCHI: list[tuple[str, str, list[tuple]]] = [
    ("commerciale", "Cosa vuole", [
        ("obiettivo", "Obiettivo numero uno del sito", "scelta",
         ["Ricevere telefonate", "Ricevere prenotazioni", "Ricevere preventivi",
          "Farsi trovare su Google", "Dare credibilità"]),
        ("cliente_tipo", "Chi deve arrivare sul sito (il cliente tipo)", "testo", []),
        ("riferimenti", "Due concorrenti o siti che gli piacciono", "testo", []),
        ("non_deve", "Cosa NON deve esserci sul sito", "lungo", []),
        ("tono", "Tono", "scelta",
         ["Istituzionale e serio", "Caldo e familiare", "Moderno e audace"]),
        ("scadenze", "Scadenze (una stagione, un evento, una data)", "testo", []),
    ]),
    ("materiali", "Cosa ha in mano", [
        ("foto", "Foto sue: quante e come sono", "scelta",
         ["Molte e belle", "Poche ma buone", "Fatte col telefono", "Non ne ha"]),
        ("logo", "Logo", "scelta",
         ["Sì, file vettoriale", "Sì, solo immagine", "Solo una firma/scritta", "Non ce l'ha"]),
        ("testi", "Testi già scritti", "scelta", ["Sì, pronti", "Qualche appunto", "Niente"]),
        ("video", "Video disponibili", "scelta", ["Sì", "No"]),
        ("social", "Social attivi e profilo Google dell'attività", "testo", []),
    ]),
    ("tecnico", "Domande tecniche", [
        ("chi_gestisce", "Chi gestirà il sito dopo la consegna", "scelta",
         ["Il titolare stesso", "Un familiare o dipendente", "Nessuno, ci pensiamo noi"]),
        ("carica_foto", "Le foto le carica lui o le mettiamo noi", "scelta",
         ["Le carica lui (serve il pannello)", "Le mettiamo noi", "Da decidere"]),
        ("dominio", "Dominio: ce l'ha già? chi lo gestisce? dove sono i DNS?", "testo", []),
        ("email", "Email", "scelta",
         ["Ha email professionale sul dominio", "Usa Gmail/Libero", "Da creare"]),
        ("hosting", "Hosting", "scelta",
         ["Ne ha già uno", "Si parte da zero", "Non lo sa"]),
        ("contatto", "Cosa succede quando lo contattano", "multi",
         ["WhatsApp", "Email", "Telefono", "Modulo sul sito"]),
        ("prenotazione_online", "Serve la prenotazione online", "scelta", ["Sì", "No"]),
        ("vendita_online", "Deve vendere online", "scelta",
         ["No, solo vetrina", "Sì, e-commerce"]),
        ("vincoli", "Vincoli legali: P.IVA, ordini professionali, cose che non può scrivere",
         "lungo", []),
    ]),
    ("chiusura", "A caldo, dopo la call", [
        ("impressione", "Impressione di Michele: com'è andata, quanto è caldo, cosa lo frena",
         "lungo", []),
    ]),
]

CSS = """
:root{--ink:#0f172a;--muted:#64748b;--brand:#4f46e5;--brand2:#7c3aed;--bg:#f1f5f9;--line:#e2e8f0}
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",system-ui,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(120deg,var(--brand),var(--brand2));color:#fff;padding:20px 18px 16px}
header h1{margin:0;font-size:1.2rem}
header .sub{margin-top:4px;font-size:.82rem;opacity:.88}
header a.back{color:#fff;text-decoration:none;font-size:.82rem;opacity:.9;display:inline-block;margin-bottom:10px}
main{padding:16px 14px 40px;max-width:720px;margin:0 auto}
fieldset{border:0;background:#fff;border-radius:16px;padding:16px;margin:0 0 14px;
  box-shadow:0 1px 2px rgba(15,23,42,.06)}
legend{font-weight:800;font-size:.78rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--brand);padding:0 0 6px}
label.d{display:block;font-weight:600;font-size:.92rem;margin:16px 0 7px;line-height:1.35}
fieldset > label.d:first-of-type{margin-top:4px}
input[type=text],textarea,select{width:100%;padding:11px 12px;border:1px solid var(--line);
  border-radius:10px;font:inherit;font-size:.95rem;background:#fff;color:var(--ink)}
textarea{min-height:76px;resize:vertical}
input:focus,textarea:focus,select:focus{outline:2px solid var(--brand);outline-offset:1px;border-color:transparent}
.opts{display:flex;flex-wrap:wrap;gap:7px}
.opts label{display:inline-flex;align-items:center;gap:7px;background:#f8fafc;border:1px solid var(--line);
  border-radius:999px;padding:8px 14px;font-size:.89rem;cursor:pointer}
.opts label:has(input:checked){background:#eef2ff;border-color:var(--brand);color:var(--brand);font-weight:600}
.hint{font-size:.79rem;color:var(--muted);margin:4px 0 0;line-height:1.4}
.salva{position:sticky;bottom:0;background:linear-gradient(transparent,var(--bg) 26%);padding:16px 0 6px}
button.primario{width:100%;padding:15px;border:0;border-radius:12px;background:var(--brand);color:#fff;
  font-weight:800;font-size:1rem;cursor:pointer}
button.primario:disabled{opacity:.6}
.esito{margin:10px 0 0;padding:12px 14px;border-radius:10px;font-size:.9rem;display:none}
.esito.ok{display:block;background:#dcfce7;color:#14532d}
.esito.ko{display:block;background:#fee2e2;color:#7f1d1d}
table.fin{width:100%;border-collapse:collapse;font-size:.92rem}
table.fin td{padding:8px 4px;border-bottom:1px solid var(--line)}
table.fin td:first-child{font-weight:600;width:34%}
table.fin input[type=time]{width:100%;padding:9px;border:1px solid var(--line);border-radius:9px;font:inherit}
table.fin td.off input{opacity:.35;pointer-events:none}
.sw{display:inline-flex;align-items:center;gap:8px;font-size:.9rem}
"""


def _campo(chiave: str, testo: str, tipo: str, opzioni: list[str], valore) -> str:
    e = html_mod.escape
    out = [f'<label class="d" for="f_{chiave}">{e(testo)}</label>']
    if tipo == "lungo":
        v = e(str(valore or ""))
        out.append(f'<textarea id="f_{chiave}" name="{chiave}">{v}</textarea>')
    elif tipo == "scelta":
        opts = "".join(
            f'<label><input type="radio" name="{chiave}" value="{e(o)}"'
            f'{" checked" if valore == o else ""}>{e(o)}</label>' for o in opzioni
        )
        out.append(f'<div class="opts" id="f_{chiave}">{opts}</div>')
    elif tipo == "multi":
        scelti = valore if isinstance(valore, list) else []
        opts = "".join(
            f'<label><input type="checkbox" name="{chiave}" value="{e(o)}"'
            f'{" checked" if o in scelti else ""}>{e(o)}</label>' for o in opzioni
        )
        out.append(f'<div class="opts" id="f_{chiave}">{opts}</div>')
    else:
        v = e(str(valore or ""))
        out.append(f'<input type="text" id="f_{chiave}" name="{chiave}" value="{v}">')
    return "\n".join(out)


def pagina_scheda(client_id: str, token: str, nome_console: str,
                  precompilato: dict | None = None) -> str:
    """Form della call conoscitiva. Se 'precompilato' arriva, riapre una scheda esistente."""
    e = html_mod.escape
    dati = (precompilato or {}).get("risposte", {}) if precompilato else {}
    testata = (precompilato or {}).get("cliente", {}) if precompilato else {}

    blocchi_html = []
    for _chiave_b, titolo, domande in BLOCCHI:
        campi = "\n".join(_campo(k, t, tp, op, dati.get(k)) for k, t, tp, op in domande)
        blocchi_html.append(f"<fieldset><legend>{e(titolo)}</legend>\n{campi}\n</fieldset>")

    return f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Scheda cliente · {e(nome_console)}</title>
<style>{CSS}</style>
</head><body>
<header>
  <a class="back" href="/{e(client_id)}/agenda?token={e(token)}">&#8592; Torna alla console</a>
  <h1>Scheda cliente</h1>
  <div class="sub">Da compilare durante la call conoscitiva &middot; si salva sulla console</div>
</header>
<main>
<form id="scheda">
  <fieldset>
    <legend>Di chi stiamo parlando</legend>
    <label class="d" for="f_nome">Nome dell'attività o della persona</label>
    <input type="text" id="f_nome" name="_nome" value="{e(str(testata.get('nome','')))}" required>
    <label class="d" for="f_tel">Telefono (lo stesso con cui ha scritto su WhatsApp)</label>
    <input type="text" id="f_tel" name="_telefono" value="{e(str(testata.get('telefono','')))}">
    <p class="hint">Il telefono lega questa scheda alla conversazione con Alberto: mettilo uguale,
    così quando generiamo il sito ritroviamo tutto insieme.</p>
  </fieldset>
  {chr(10).join(blocchi_html)}
  <div class="salva">
    <button class="primario" type="submit">Salva la scheda</button>
    <div class="esito" id="esito"></div>
  </div>
</form>
</main>
<script>
document.getElementById('scheda').addEventListener('submit', async function(ev) {{
  ev.preventDefault();
  const bottone = ev.target.querySelector('button');
  const esito = document.getElementById('esito');
  bottone.disabled = true; bottone.textContent = 'Salvo...';
  const fd = new FormData(ev.target);
  const risposte = {{}};
  for (const [k, v] of fd.entries()) {{
    if (k.startsWith('_')) continue;
    if (risposte[k] === undefined) risposte[k] = v;
    else if (Array.isArray(risposte[k])) risposte[k].push(v);
    else risposte[k] = [risposte[k], v];
  }}
  try {{
    const r = await fetch('/{e(client_id)}/scheda?token={e(token)}', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        nome: fd.get('_nome') || '', telefono: fd.get('_telefono') || '', risposte: risposte
      }})
    }});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'errore');
    esito.className = 'esito ok';
    esito.textContent = 'Scheda salvata. La ritrovi nella console.';
  }} catch (err) {{
    esito.className = 'esito ko';
    esito.textContent = 'Non sono riuscito a salvare: ' + err.message;
  }}
  bottone.disabled = false; bottone.textContent = 'Salva la scheda';
}});
</script>
</body></html>"""


def pagina_finestre(client_id: str, token: str, nome_console: str, finestre: dict) -> str:
    """Michele sceglie giorni e fasce in cui accetta le call."""
    e = html_mod.escape
    righe = []
    for chiave, etichetta in GIORNI:
        f = finestre.get(chiave) or {}
        attivo = bool(f.get("attivo"))
        da = e(str(f.get("da", "10:00")))
        a = e(str(f.get("a", "18:00")))
        righe.append(
            f'<tr data-g="{chiave}">'
            f'<td><label class="sw"><input type="checkbox" class="on" '
            f'{"checked" if attivo else ""}> {e(etichetta)}</label></td>'
            f'<td class="{"" if attivo else "off"}"><input type="time" class="da" value="{da}"></td>'
            f'<td class="{"" if attivo else "off"}"><input type="time" class="a" value="{a}"></td>'
            f'</tr>'
        )
    return f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Disponibilità · {e(nome_console)}</title>
<style>{CSS}</style>
</head><body>
<header>
  <a class="back" href="/{e(client_id)}/agenda?token={e(token)}">&#8592; Torna alla console</a>
  <h1>Quando sei disponibile</h1>
  <div class="sub">Alberto proporrà le call solo dentro queste fasce, una all'ora</div>
</header>
<main>
<fieldset>
  <legend>Giorni e orari</legend>
  <table class="fin"><tbody>
  {chr(10).join(righe)}
  </tbody></table>
  <p class="hint">Ogni call dura 30 minuti e ne lascia 30 di cuscinetto: gli slot proposti
  partono a ogni ora piena. Togli la spunta ai giorni in cui non vuoi essere chiamato.</p>
</fieldset>
<div class="salva">
  <button class="primario" id="salva">Salva le disponibilità</button>
  <div class="esito" id="esito"></div>
</div>
</main>
<script>
document.querySelectorAll('tr[data-g] .on').forEach(function(c) {{
  c.addEventListener('change', function() {{
    const tr = c.closest('tr');
    tr.querySelectorAll('td:not(:first-child)').forEach(function(td) {{
      td.classList.toggle('off', !c.checked);
    }});
  }});
}});
document.getElementById('salva').addEventListener('click', async function() {{
  const b = this, esito = document.getElementById('esito');
  b.disabled = true; b.textContent = 'Salvo...';
  const finestre = {{}};
  document.querySelectorAll('tr[data-g]').forEach(function(tr) {{
    finestre[tr.dataset.g] = {{
      attivo: tr.querySelector('.on').checked,
      da: tr.querySelector('.da').value,
      a: tr.querySelector('.a').value
    }};
  }});
  try {{
    const r = await fetch('/{e(client_id)}/finestre?token={e(token)}', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{finestre: finestre}})
    }});
    if (!r.ok) throw new Error((await r.json()).detail || 'errore');
    esito.className = 'esito ok'; esito.textContent = 'Disponibilità salvate.';
  }} catch (err) {{
    esito.className = 'esito ko'; esito.textContent = 'Non salvate: ' + err.message;
  }}
  b.disabled = false; b.textContent = 'Salva le disponibilità';
}});
</script>
</body></html>"""


def filtra_per_finestre(slot: list, finestre: dict, solo_ore_intere: bool = True) -> list:
    """Tiene solo gli slot dentro le fasce dichiarate e, di default, a ogni ora piena
    (call 30 min + 30 min di cuscinetto). Se non ci sono fasce, non filtra nulla."""
    if not finestre:
        return slot
    attive = {k: v for k, v in finestre.items() if isinstance(v, dict) and v.get("attivo")}
    if not attive:
        return slot

    def _min(hhmm: str, default: int) -> int:
        try:
            h, m = str(hhmm).split(":")[:2]
            return int(h) * 60 + int(m)
        except Exception:  # noqa: BLE001
            return default

    tenuti = []
    for s in slot:
        inizio: datetime = getattr(s, "inizio", None)
        if inizio is None:
            tenuti.append(s)
            continue
        if solo_ore_intere and inizio.minute != 0:
            continue
        chiave = GIORNI[inizio.weekday()][0]
        f = attive.get(chiave)
        if not f:
            continue
        minuti = inizio.hour * 60 + inizio.minute
        if _min(f.get("da"), 0) <= minuti < _min(f.get("a"), 24 * 60):
            tenuti.append(s)
    return tenuti


def riassunto_schede(eventi: list[dict], limite: int = 25) -> str:
    """Elenco delle schede salvate, per la console."""
    e = html_mod.escape
    schede = [x for x in eventi if x.get("tipo") == TIPO_SCHEDA][:limite]
    if not schede:
        return ('<div class="vuoto">Nessuna scheda ancora. Compilane una durante '
                'la prossima call &#128203;</div>')
    righe = []
    for s in schede:
        d = s.get("dati") or {}
        cl = d.get("cliente") or {}
        r = d.get("risposte") or {}
        quando = str(s.get("ts", ""))[:10]
        nome = e(str(cl.get("nome") or "senza nome"))
        tel = "".join(ch for ch in str(cl.get("telefono") or "") if ch.isdigit())
        obiettivo = e(str(r.get("obiettivo") or "—"))
        gestione = e(str(r.get("chi_gestisce") or "—"))
        wa = (f'<a class="btn wa" href="https://wa.me/{tel}" title="WhatsApp">&#128172;</a>'
              if tel else "")
        righe.append(
            '<div class="card"><div class="info">'
            f'<div class="ora">{nome}</div>'
            f'<div class="chi">{obiettivo} &middot; gestisce: {gestione}</div>'
            f'<div class="nota">compilata il {e(quando)}</div>'
            f'</div><div class="azioni">{wa}</div></div>'
        )
    return "\n".join(righe)
