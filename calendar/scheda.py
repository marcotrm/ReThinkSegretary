"""Scheda cliente, questionario per il cliente e finestre di disponibilita' di Michele.

Tre pagine che vivono attorno alla console (stesso servizio, stesso database):

- SCHEDA (interna, con token): le domande che Michele fa durante la call conoscitiva.
  Commerciale + materiali + domande tecniche in un colpo solo.
- QUESTIONARIO (pubblico, per etichetta): la STESSA scheda ma da mandare al cliente,
  che se la compila da solo con calma. Utile quando il progetto e' grosso (un
  e-commerce) e le informazioni non stanno in una telefonata.
- FINESTRE: giorni e fasce in cui Michele accetta chiamate.

Le domande si adattano: quelle da e-commerce compaiono solo se ha detto che vende
online, e il caricamento delle foto solo se ha detto di averle.

Niente tabelle nuove: tutto nella tabella 'eventi' gia' esistente.
"""
from __future__ import annotations

import html as html_mod

TIPO_SCHEDA = "scheda_cliente"
TIPO_FINESTRE = "finestre_disponibilita"
TIPO_FOTO = "foto_cliente"

GIORNI = [
    ("lun", "Lunedì"), ("mar", "Martedì"), ("mer", "Mercoledì"), ("gio", "Giovedì"),
    ("ven", "Venerdì"), ("sab", "Sabato"), ("dom", "Domenica"),
]

SI_ECOM = ("vendita_online", ["Sì, e-commerce"])
HA_FOTO = ("foto", ["Molte e belle", "Poche ma buone", "Fatte col telefono"])

# (chiave, domanda, tipo, opzioni[, condizione])
# tipo: testo | lungo | scelta | multi | foto        condizione: (campo, [valori])
BLOCCHI: list[tuple[str, str, list[tuple]]] = [
    ("progetto", "Che cosa serve", [
        ("vendita_online", "Deve vendere online?", "scelta",
         ["No, solo vetrina", "Sì, e-commerce"]),
        ("obiettivo", "Obiettivo numero uno del sito", "scelta",
         ["Ricevere telefonate", "Ricevere prenotazioni", "Ricevere preventivi",
          "Vendere online", "Farsi trovare su Google", "Dare credibilità"]),
        ("cliente_tipo", "Chi deve arrivare sul sito (il cliente tipo)", "testo", []),
        ("riferimenti", "Due concorrenti o siti che vi piacciono", "testo", []),
        ("non_deve", "Cosa NON deve esserci sul sito", "lungo", []),
        ("tono", "Tono", "scelta",
         ["Istituzionale e serio", "Caldo e familiare", "Moderno e audace"]),
        ("scadenze", "Scadenze (una stagione, un evento, una data)", "testo", []),
    ]),
    ("ecommerce", "Il negozio online", [
        ("prodotti_quanti", "Quanti prodotti, all'incirca", "scelta",
         ["Meno di 20", "Da 20 a 100", "Da 100 a 500", "Più di 500"], SI_ECOM),
        ("prodotti_cosa", "Che prodotti vendete", "testo", [], SI_ECOM),
        ("varianti", "I prodotti hanno varianti (taglie, colori, formati)?", "scelta",
         ["Sì", "No", "Solo alcuni"], SI_ECOM),
        ("catalogo_dove", "Il catalogo dove sta adesso", "scelta",
         ["In un file Excel o CSV", "In un gestionale", "Solo sul sito attuale",
          "Da scrivere da zero"], SI_ECOM),
        ("marketplace", "Vendete già su altri canali?", "multi",
         ["Amazon", "eBay", "Etsy", "Instagram/Facebook Shop", "Solo in negozio",
          "Nessuno"], SI_ECOM),
        ("marketplace_sync", "Il catalogo va sincronizzato con quei canali?", "scelta",
         ["Sì, giacenze e prezzi allineati", "No, canali separati", "Da valutare"], SI_ECOM),
        ("spedizioni", "Spedizioni: chi spedisce, con quale corriere, in che zone",
         "lungo", [], SI_ECOM),
        ("costi_spedizione", "Come sono i costi di spedizione", "scelta",
         ["Fissi", "In base al peso", "In base alla zona", "Gratis sopra una cifra",
          "Da decidere"], SI_ECOM),
        ("pagamenti", "Come volete essere pagati", "multi",
         ["Carta di credito", "PayPal", "Bonifico", "Contrassegno", "Pagamento a rate"],
         SI_ECOM),
        ("magazzino", "Chi aggiorna le giacenze e con che frequenza", "testo", [], SI_ECOM),
        ("fatturazione", "Fatturazione elettronica: chi la gestisce", "scelta",
         ["Il commercialista", "Un gestionale", "Da impostare"], SI_ECOM),
        ("sito_attuale", "Sito attuale: indirizzo e cosa non funziona", "lungo", [], SI_ECOM),
    ]),
    ("materiali", "Cosa avete in mano", [
        ("foto", "Foto dei prodotti o dell'attività", "scelta",
         ["Molte e belle", "Poche ma buone", "Fatte col telefono", "Non ne ha"]),
        ("foto_caricate", "Caricate qui qualche foto (le rimpicciolisco io)", "foto",
         [], HA_FOTO),
        ("foto_link", "Oppure incollate un link a Drive / WeTransfer", "testo", [], HA_FOTO),
        ("logo", "Logo", "scelta",
         ["Sì, file vettoriale", "Sì, solo immagine", "Solo una firma/scritta", "Non ce l'ha"]),
        ("testi", "Testi già scritti", "scelta", ["Sì, pronti", "Qualche appunto", "Niente"]),
        ("video", "Video disponibili", "scelta", ["Sì", "No"]),
        ("social", "Social attivi e profilo Google dell'attività", "testo", []),
    ]),
    ("tecnico", "Parte tecnica", [
        ("chi_gestisce", "Chi gestirà il sito dopo la consegna", "scelta",
         ["Il titolare stesso", "Un familiare o dipendente", "Nessuno, ci pensiamo noi"]),
        ("carica_foto", "Le foto le caricate voi o le mettiamo noi", "scelta",
         ["Le carico io (serve il pannello)", "Le mettete voi", "Da decidere"]),
        ("dominio", "Dominio: ce l'avete già? chi lo gestisce? dove sono i DNS?", "testo", []),
        ("email", "Email", "scelta",
         ["Ho email professionale sul dominio", "Uso Gmail/Libero", "Da creare"]),
        ("hosting", "Hosting", "scelta", ["Ne ho già uno", "Si parte da zero", "Non lo so"]),
        ("contatto", "Cosa succede quando vi contattano", "multi",
         ["WhatsApp", "Email", "Telefono", "Modulo sul sito"]),
        ("prenotazione_online", "Serve la prenotazione online", "scelta", ["Sì", "No"]),
        ("vincoli", "Vincoli legali: P.IVA, ordini professionali, cose che non potete scrivere",
         "lungo", []),
    ]),
    ("chiusura", "Note", [
        ("impressione", "Impressione di Michele: com'è andata, quanto è caldo, cosa lo frena",
         "lungo", [], ("__solo_interno__", [])),
        ("note_cliente", "C'è altro che dovremmo sapere?", "lungo", [],
         ("__solo_pubblico__", [])),
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
fieldset.nascosto{display:none}
legend{font-weight:800;font-size:.78rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--brand);padding:0 0 6px}
.campo{margin:16px 0 0}
.campo.nascosto{display:none}
fieldset > .campo:first-of-type{margin-top:4px}
label.d{display:block;font-weight:600;font-size:.92rem;margin:0 0 7px;line-height:1.35}
input[type=text],textarea,select{width:100%;padding:11px 12px;border:1px solid var(--line);
  border-radius:10px;font:inherit;font-size:.95rem;background:#fff;color:var(--ink)}
textarea{min-height:76px;resize:vertical}
input:focus,textarea:focus,select:focus{outline:2px solid var(--brand);outline-offset:1px;border-color:transparent}
.opts{display:flex;flex-wrap:wrap;gap:7px}
.opts label{display:inline-flex;align-items:center;gap:7px;background:#f8fafc;border:1px solid var(--line);
  border-radius:999px;padding:8px 14px;font-size:.89rem;cursor:pointer}
.opts label:has(input:checked){background:#eef2ff;border-color:var(--brand);color:var(--brand);font-weight:600}
.hint{font-size:.79rem;color:var(--muted);margin:5px 0 0;line-height:1.45}
.drop{border:2px dashed var(--line);border-radius:12px;padding:20px;text-align:center;
  background:#f8fafc;cursor:pointer}
.drop:hover{border-color:var(--brand);background:#eef2ff}
.drop input{display:none}
.drop b{color:var(--brand)}
.provini{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.provini img{width:74px;height:74px;object-fit:cover;border-radius:8px;border:1px solid var(--line)}
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


def _cond_attr(cond) -> str:
    if not cond:
        return ""
    campo, valori = cond
    return f' data-se="{html_mod.escape(campo)}" data-val="{html_mod.escape("||".join(valori))}"'


def _campo(chiave: str, testo: str, tipo: str, opzioni: list[str], valore, cond=None) -> str:
    e = html_mod.escape
    dentro = [f'<label class="d" for="f_{chiave}">{e(testo)}</label>']
    if tipo == "lungo":
        dentro.append(f'<textarea id="f_{chiave}" name="{chiave}">{e(str(valore or ""))}</textarea>')
    elif tipo == "scelta":
        dentro.append('<div class="opts">' + "".join(
            f'<label><input type="radio" name="{chiave}" value="{e(o)}"'
            f'{" checked" if valore == o else ""}>{e(o)}</label>' for o in opzioni) + "</div>")
    elif tipo == "multi":
        scelti = valore if isinstance(valore, list) else ([valore] if valore else [])
        dentro.append('<div class="opts">' + "".join(
            f'<label><input type="checkbox" name="{chiave}" value="{e(o)}"'
            f'{" checked" if o in scelti else ""}>{e(o)}</label>' for o in opzioni) + "</div>")
    elif tipo == "foto":
        dentro.append(
            f'<label class="drop" for="file_{chiave}">'
            '<b>Scegli le foto</b><br><span class="hint">fino a 12, le rimpicciolisco io: '
            'non serve che siano leggere</span>'
            f'<input type="file" id="file_{chiave}" accept="image/*" multiple></label>'
            f'<div class="provini" id="prov_{chiave}"></div>'
        )
    else:
        dentro.append(f'<input type="text" id="f_{chiave}" name="{chiave}" '
                      f'value="{e(str(valore or ""))}">')
    return f'<div class="campo"{_cond_attr(cond)}>' + "\n".join(dentro) + "</div>"


def pagina_scheda(client_id: str, token: str, nome_console: str,
                  precompilato: dict | None = None, pubblico: bool = False,
                  etichetta: str = "", nome_cliente: str = "") -> str:
    """La scheda. Con pubblico=True diventa il questionario da mandare al cliente:
    niente token, niente domande interne, e le risposte arrivano lo stesso in console."""
    e = html_mod.escape
    dati = (precompilato or {}).get("risposte", {}) if precompilato else {}
    testata = (precompilato or {}).get("cliente", {}) if precompilato else {}

    blocchi_html = []
    for chiave_b, titolo, domande in BLOCCHI:
        campi = []
        for d in domande:
            k, t, tp, op = d[0], d[1], d[2], d[3]
            cond = d[4] if len(d) > 4 else None
            if cond and cond[0] == "__solo_interno__":
                if pubblico:
                    continue
                cond = None
            if cond and cond[0] == "__solo_pubblico__":
                if not pubblico:
                    continue
                cond = None
            campi.append(_campo(k, t, tp, op, dati.get(k), cond))
        if not campi:
            continue
        cond_b = ""
        if chiave_b == "ecommerce":
            cond_b = _cond_attr(SI_ECOM)
        blocchi_html.append(
            f'<fieldset{cond_b}><legend>{e(titolo)}</legend>\n' + "\n".join(campi) + "\n</fieldset>")

    if pubblico:
        destinazione = f"/{e(client_id)}/questionario/{e(etichetta)}"
        titolo_pag = f"Il vostro sito · {e(nome_cliente or nome_console)}"
        intestazione = f"""<header>
  <h1>Parlateci del vostro progetto</h1>
  <div class="sub">Dieci minuti di domande: da qui partiamo per costruire il sito.
  Potete salvare e riaprire questa pagina quando volete.</div>
</header>"""
        blocco_chi = f"""<fieldset>
    <legend>Chi siete</legend>
    <div class="campo"><label class="d" for="f_nome">Nome dell'attività</label>
    <input type="text" id="f_nome" name="_nome" value="{e(nome_cliente)}" required></div>
    <div class="campo"><label class="d" for="f_tel">Telefono WhatsApp</label>
    <input type="text" id="f_tel" name="_telefono" value=""></div>
  </fieldset>"""
        testo_bottone = "Invia le risposte"
        messaggio_ok = ("Ricevuto, grazie! Vi ricontattiamo a breve con la prima bozza.")
    else:
        destinazione = f"/{e(client_id)}/scheda?token={e(token)}"
        titolo_pag = f"Scheda cliente · {e(nome_console)}"
        intestazione = f"""<header>
  <a class="back" href="/{e(client_id)}/agenda?token={e(token)}">&#8592; Torna alla console</a>
  <h1>Scheda cliente</h1>
  <div class="sub">Da compilare durante la call conoscitiva &middot; si salva sulla console</div>
</header>"""
        blocco_chi = f"""<fieldset>
    <legend>Di chi stiamo parlando</legend>
    <div class="campo"><label class="d" for="f_nome">Nome dell'attività o della persona</label>
    <input type="text" id="f_nome" name="_nome" value="{e(str(testata.get('nome','')))}" required></div>
    <div class="campo"><label class="d" for="f_tel">Telefono (lo stesso con cui ha scritto su WhatsApp)</label>
    <input type="text" id="f_tel" name="_telefono" value="{e(str(testata.get('telefono','')))}">
    <p class="hint">Il telefono lega questa scheda alla conversazione con Alberto: mettilo uguale,
    così quando generiamo il sito ritroviamo tutto insieme.</p></div>
  </fieldset>"""
        testo_bottone = "Salva la scheda"
        messaggio_ok = "Scheda salvata. La ritrovi nella console."

    return f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{titolo_pag}</title>
<style>{CSS}</style>
</head><body>
{intestazione}
<main>
<form id="scheda">
  {blocco_chi}
  {chr(10).join(blocchi_html)}
  <div class="salva">
    <button class="primario" type="submit">{testo_bottone}</button>
    <div class="esito" id="esito"></div>
  </div>
</form>
</main>
<script>
// ---- domande che compaiono solo quando servono ----
function valoriDi(campo) {{
  const out = [];
  document.querySelectorAll('[name="' + campo + '"]').forEach(function(i) {{
    if ((i.type === 'radio' || i.type === 'checkbox') ? i.checked : i.value) out.push(i.value);
  }});
  return out;
}}
function aggiorna() {{
  document.querySelectorAll('[data-se]').forEach(function(el) {{
    const attesi = el.dataset.val.split('||');
    const presenti = valoriDi(el.dataset.se);
    const ok = attesi.some(function(v) {{ return presenti.indexOf(v) >= 0; }});
    el.classList.toggle('nascosto', !ok);
  }});
}}
document.addEventListener('change', aggiorna);
aggiorna();

// ---- foto: rimpicciolite qui nel telefono, cosi' l'invio e' leggero ----
const FOTO = [];
document.querySelectorAll('input[type=file]').forEach(function(inp) {{
  const prov = document.getElementById('prov_' + inp.id.replace('file_', ''));
  inp.addEventListener('change', function() {{
    Array.from(inp.files).slice(0, 12).forEach(function(f) {{
      const lettore = new FileReader();
      lettore.onload = function(ev) {{
        const im = new Image();
        im.onload = function() {{
          const max = 1400;
          const s = Math.min(1, max / Math.max(im.width, im.height));
          const cv = document.createElement('canvas');
          cv.width = Math.round(im.width * s); cv.height = Math.round(im.height * s);
          cv.getContext('2d').drawImage(im, 0, 0, cv.width, cv.height);
          const dato = cv.toDataURL('image/jpeg', 0.72);
          if (FOTO.length < 12) FOTO.push({{nome: f.name, dato: dato}});
          const th = document.createElement('img'); th.src = dato; prov.appendChild(th);
        }};
        im.src = ev.target.result;
      }};
      lettore.readAsDataURL(f);
    }});
  }});
}});

// ---- invio ----
document.getElementById('scheda').addEventListener('submit', async function(ev) {{
  ev.preventDefault();
  const bottone = ev.target.querySelector('button');
  const esito = document.getElementById('esito');
  bottone.disabled = true; bottone.textContent = 'Invio...';
  const fd = new FormData(ev.target);
  const risposte = {{}};
  for (const [k, v] of fd.entries()) {{
    if (k.startsWith('_')) continue;
    if (risposte[k] === undefined) risposte[k] = v;
    else if (Array.isArray(risposte[k])) risposte[k].push(v);
    else risposte[k] = [risposte[k], v];
  }}
  try {{
    const r = await fetch('{destinazione}', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        nome: fd.get('_nome') || '', telefono: fd.get('_telefono') || '',
        risposte: risposte, foto: FOTO
      }})
    }});
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'errore');
    esito.className = 'esito ok';
    esito.textContent = '{messaggio_ok}';
  }} catch (err) {{
    esito.className = 'esito ko';
    esito.textContent = 'Non sono riuscito a salvare: ' + err.message;
  }}
  bottone.disabled = false; bottone.textContent = '{testo_bottone}';
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

    def _min(hhmm, default: int) -> int:
        try:
            h, m = str(hhmm).split(":")[:2]
            return int(h) * 60 + int(m)
        except Exception:  # noqa: BLE001
            return default

    tenuti = []
    for s in slot:
        inizio = getattr(s, "inizio", None)
        if inizio is None:
            tenuti.append(s)
            continue
        if solo_ore_intere and inizio.minute != 0:
            continue
        f = attive.get(GIORNI[inizio.weekday()][0])
        if not f:
            continue
        minuti = inizio.hour * 60 + inizio.minute
        if _min(f.get("da"), 0) <= minuti < _min(f.get("a"), 24 * 60):
            tenuti.append(s)
    return tenuti


def riassunto_schede(eventi: list[dict], limite: int = 25,
                     client_id: str = "", token: str = "") -> str:
    """Elenco delle schede salvate, con i due link da mandare al cliente."""
    import abbonamenti as _abb
    e = html_mod.escape
    foto_per_chiave: dict[str, int] = {}
    for x in eventi:
        if x.get("tipo") == TIPO_FOTO:
            d = x.get("dati") or {}
            k = d.get("etichetta") or ""
            foto_per_chiave[k] = foto_per_chiave.get(k, 0) + int(d.get("quante") or 0)

    schede = [x for x in eventi if x.get("tipo") == TIPO_SCHEDA][:limite]
    if not schede:
        return ('<div class="vuoto">Nessuna scheda ancora. Compilane una durante la prossima '
                'call, oppure manda il questionario al cliente &#128203;</div>')

    righe = []
    for s in schede:
        d = s.get("dati") or {}
        cl = d.get("cliente") or {}
        r = d.get("risposte") or {}
        nome = e(str(cl.get("nome") or "senza nome"))
        tel = "".join(ch for ch in str(cl.get("telefono") or "") if ch.isdigit())
        et = _abb.slug(cl.get("nome") or "")
        obiettivo = e(str(r.get("obiettivo") or "—"))
        tipo = "e-commerce" if str(r.get("vendita_online") or "").startswith("Sì") else "vetrina"
        nfoto = foto_per_chiave.get(et, 0)
        extra = f' &middot; {nfoto} foto ricevute' if nfoto else ""
        wa = (f'<a class="btn wa" href="https://wa.me/{tel}" title="WhatsApp">&#128172;</a>'
              if tel else "")
        bottoni = (
            f'<button class="mini" data-et="{e(et)}" onclick="copia(this.dataset.et,\'questionario\')" '
            'title="Questionario da far compilare al cliente">&#128221; Questionario</button>'
            f'<button class="mini" data-et="{e(et)}" onclick="copia(this.dataset.et,\'attiva\')" '
            'title="Link per farlo pagare">&#128279; Attivazione</button>'
        )
        righe.append(
            '<div class="card"><div class="info">'
            f'<div class="ora">{nome}</div>'
            f'<div class="chi">{tipo} &middot; {obiettivo}{extra}</div>'
            f'<div class="nota">compilata il {e(str(s.get("ts",""))[:10])}</div>'
            f'</div><div class="azioni">{bottoni}{wa}</div></div>'
        )

    cid = e(client_id or "nia")
    script = (
        "<script>\n"
        "function copia(et, tipo) {\n"
        f"  var u = location.origin + '/{cid}/' + tipo + '/' + et;\n"
        "  var msg = tipo === 'attiva'\n"
        "    ? 'Link di pagamento copiato:' : 'Questionario copiato:';\n"
        "  if (navigator.clipboard) {\n"
        "    navigator.clipboard.writeText(u).then(\n"
        "      function(){ alert(msg + '\\n' + u + '\\n\\nMandalo al cliente.'); },\n"
        "      function(){ prompt('Copia questo link:', u); });\n"
        "  } else { prompt('Copia questo link:', u); }\n"
        "}\n</script>"
    )
    return "\n".join(righe) + script
