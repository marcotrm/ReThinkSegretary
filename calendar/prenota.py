"""Pagina pubblica per prenotare la call conoscitiva con Michele.

Un solo indirizzo da mandare al cliente: lui vede SOLO gli orari liberi e sceglie.
Le call gia' prese restano in console, dove le vediamo noi.

Gli orari proposti sono gia' filtrati dalle finestre di Michele e dal cuscinetto
di mezz'ora: qui non si decide niente, si mostra quello che il calendario dice.
"""
from __future__ import annotations

import html as html_mod

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
           "agosto", "settembre", "ottobre", "novembre", "dicembre"]

CSS = """
*{box-sizing:border-box}
:root{--sf:#f6f6f7;--carta:#fff;--testo:#16161a;--tenue:#6b6b76;--linea:#e6e6ea;--acc:#1f6feb}
@media (prefers-color-scheme:dark){
  :root{--sf:#0f0f11;--carta:#17171b;--testo:#f2f2f4;--tenue:#9a9aa4;--linea:#2a2a31}}
body{margin:0;background:var(--sf);color:var(--testo);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
header{padding:36px 20px 20px;text-align:center}
h1{margin:0 0 6px;font-size:1.55rem;letter-spacing:-.02em}
.sub{color:var(--tenue);font-size:.95rem}
main{max-width:680px;margin:0 auto;padding:0 16px 60px}
.giorno{margin:22px 0 8px;font-weight:700;text-transform:capitalize}
.slot{display:flex;flex-wrap:wrap;gap:8px}
.slot button{padding:11px 16px;border:1px solid var(--linea);border-radius:11px;
  background:var(--carta);color:var(--testo);font:inherit;font-weight:600;cursor:pointer}
.slot button:hover{border-color:var(--acc);color:var(--acc)}
.slot button[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
form{margin-top:26px;background:var(--carta);border:1px solid var(--linea);
  border-radius:16px;padding:18px}
form[hidden]{display:none}
label{display:block;font-weight:600;font-size:.9rem;margin:0 0 6px}
input,textarea{width:100%;padding:11px;border:1px solid var(--linea);border-radius:10px;
  font:inherit;background:transparent;color:var(--testo);margin-bottom:14px}
textarea{min-height:74px;resize:vertical}
button.primario{width:100%;padding:14px;border:0;border-radius:12px;background:var(--acc);
  color:#fff;font:inherit;font-weight:700;cursor:pointer}
button.primario:disabled{opacity:.55;cursor:default}
.scelto{font-size:.92rem;color:var(--tenue);margin-bottom:14px}
.esito{margin-top:12px;font-size:.92rem;min-height:1.2em}
.esito.ko{color:#c0392b}
.vuoto{background:var(--carta);border:1px solid var(--linea);border-radius:14px;
  padding:26px;text-align:center;color:var(--tenue)}
.fatto{text-align:center;padding:40px 20px}
.fatto .segno{font-size:2.6rem}
"""


def _etichetta_giorno(d) -> str:
    return f"{GIORNI_IT[d.weekday()]} {d.day} {MESI_IT[d.month]}"


def pagina_prenota(client_id: str, nome_console: str, slot: list,
                   durata_min: int = 30) -> str:
    """slot: oggetti con .inizio (datetime con fuso). Il cliente vede solo questi."""
    e = html_mod.escape

    per_giorno: dict = {}
    for s in slot:
        inizio = getattr(s, "inizio", None)
        if inizio is None:
            continue
        per_giorno.setdefault(inizio.date(), []).append(inizio)

    if per_giorno:
        blocchi = []
        for giorno in sorted(per_giorno):
            ore = "".join(
                f'<button type="button" data-iso="{i.isoformat()}" '
                f'onclick="scegli(this)">{i.strftime("%H:%M")}</button>'
                for i in sorted(per_giorno[giorno]))
            blocchi.append(f'<div class="giorno">{e(_etichetta_giorno(giorno))}</div>'
                           f'<div class="slot">{ore}</div>')
        corpo = "\n".join(blocchi)
    else:
        corpo = ('<div class="vuoto">In questo momento non ci sono orari liberi. '
                 'Riprovate fra qualche ora: se ne liberano di continuo.</div>')

    return f"""<!doctype html>
<html lang="it"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Prenota una chiamata &middot; {e(nome_console)}</title>
<style>{CSS}</style>
</head><body>
<div id="tutto">
<header>
  <h1>Prenota una chiamata</h1>
  <div class="sub">{durata_min} minuti, al telefono. Scegliete l'orario che vi comoda.</div>
</header>
<main>
  {corpo}
  <form id="modulo" hidden>
    <div class="scelto" id="scelto"></div>
    <label for="nome">Nome e cognome</label>
    <input id="nome" name="nome" required>
    <label for="tel">Telefono (vi chiamiamo qui)</label>
    <input id="tel" name="tel" inputmode="tel" required>
    <label for="note">Qualcosa che ci conviene sapere prima (facoltativo)</label>
    <textarea id="note" name="note"></textarea>
    <button class="primario" type="submit">Conferma la chiamata</button>
    <div class="esito" id="esito"></div>
  </form>
</main>
</div>
<script>
var iso = null;
function scegli(b) {{
  document.querySelectorAll('.slot button').forEach(function (x) {{
    x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
  }});
  iso = b.dataset.iso;
  var m = document.getElementById('modulo');
  m.hidden = false;
  document.getElementById('scelto').textContent = 'Orario scelto: ' + b.closest('.slot')
    .previousElementSibling.textContent + ' alle ' + b.textContent;
  m.scrollIntoView({{behavior: 'smooth', block: 'center'}});
}}
document.getElementById('modulo').addEventListener('submit', async function (ev) {{
  ev.preventDefault();
  var b = ev.target.querySelector('button'), esito = document.getElementById('esito');
  b.disabled = true; b.textContent = 'Un attimo…'; esito.className = 'esito';
  esito.textContent = '';
  try {{
    var r = await fetch('/{e(client_id)}/prenota-call', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        inizio: iso,
        nome: document.getElementById('nome').value,
        telefono: document.getElementById('tel').value,
        note: document.getElementById('note').value
      }})}});
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'non riuscito');
    document.getElementById('tutto').innerHTML =
      '<div class="fatto"><div class="segno">&#9989;</div>' +
      '<h1>Fissata</h1><div class="sub">' + d.quando +
      '<br>Vi arriva una conferma. A presto!</div></div>';
  }} catch (err) {{
    esito.className = 'esito ko';
    esito.textContent = 'Non fissata: ' + err.message +
      ' — quell\\'orario potrebbe essere appena stato preso, provatene un altro.';
    b.disabled = false; b.textContent = 'Conferma la chiamata';
  }}
}});
</script>
</body></html>"""


def riassunto_call(prenotazioni: list, limite: int = 30) -> str:
    """Le call gia' fissate, come le vediamo noi in console."""
    e = html_mod.escape
    if not prenotazioni:
        return ('<div class="vuoto">Nessuna call fissata. Manda il link di prenotazione '
                'a un cliente e comparirà qui.</div>')
    righe = []
    for p in prenotazioni[:limite]:
        d = p.to_dict() if hasattr(p, "to_dict") else p
        inizio = getattr(p, "inizio", None)
        quando = (f"{_etichetta_giorno(inizio.date())} alle {inizio.strftime('%H:%M')}"
                  if inizio is not None else str(d.get("inizio", "")))
        nome = e(str(d.get("nome_cliente") or "senza nome"))
        tel = "".join(ch for ch in str(d.get("telefono") or "") if ch.isdigit())
        note = e(str(d.get("note") or ""))
        wa = (f'<a class="btn wa" href="https://wa.me/{tel}" title="WhatsApp">&#128172;</a>'
              if tel else "")
        righe.append(
            '<div class="card"><div class="info">'
            f'<div class="ora">{e(quando)}</div>'
            f'<div class="chi">{nome}{" &middot; " + tel if tel else ""}</div>'
            + (f'<div class="nota">{note}</div>' if note else "")
            + f'</div><div class="azioni">{wa}</div></div>')
    return "\n".join(righe)
