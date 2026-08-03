"""La riga della campagna: dove si perdono le persone.

    inviate -> consegnate -> hanno aperto -> hanno compilato -> call fissata

Quando un numero crolla si sa cosa cambiare: se aprono e non compilano il
problema e' il questionario, non la mail; se non aprono e' l'oggetto.

Le aperture NON si misurano con l'immaginetta invisibile dentro la mail:
quella fa finire in spam, e su un dominio nuovo e' il modo migliore per
rovinare tutto. Si misurano qui, perche' ogni mail porta un indirizzo diverso
col nome dell'attivita' dentro: quando la pagina si apre, il server sa gia'
chi e'. Nessun pixel, nessun link riscritto.
"""
from __future__ import annotations

import html as html_mod
import json
import os
import urllib.request

TIPO_APERTURA = "questionario_aperto"

RESEND_CHIAVE = os.getenv("RESEND_API_KEY", "")
RESEND_URL = "https://api.resend.com/emails?limit=100"


def stato_invii() -> dict:
    """Quante mail sono partite e quante sono arrivate, da Resend.
    Senza chiave restituisce zeri: il resto della vista funziona lo stesso."""
    if not RESEND_CHIAVE:
        return {}
    try:
        req = urllib.request.Request(
            RESEND_URL, headers={"Authorization": f"Bearer {RESEND_CHIAVE}"})
        with urllib.request.urlopen(req, timeout=12) as r:
            dati = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - la campagna si guarda lo stesso
        return {}
    conteggi: dict[str, int] = {}
    for e in dati.get("data", []):
        conteggi[e.get("last_event") or "?"] = conteggi.get(e.get("last_event") or "?", 0) + 1
    conteggi["totale"] = len(dati.get("data", []))
    return conteggi


def _etichette(eventi: list[dict], tipo: str, filtro=None) -> dict[str, str]:
    """etichetta -> quando, per gli eventi di un certo tipo."""
    fuori: dict[str, str] = {}
    for e in eventi:
        if e.get("tipo") != tipo:
            continue
        d = e.get("dati") or {}
        if filtro and not filtro(d):
            continue
        et = d.get("etichetta") or ""
        if not et:
            cl = d.get("cliente") or {}
            et = (cl.get("nome") or "").strip().lower().replace(" ", "-")
        if et and et not in fuori:
            fuori[et] = str(e.get("ts", ""))[:16].replace("T", " ")
    return fuori


def vista_campagna(eventi: list[dict], tipo_scheda: str, call_fissate: int = 0) -> str:
    """La riga, e sotto chi ha aperto senza compilare: quelli da richiamare."""
    e = html_mod.escape
    aperture = _etichette(eventi, TIPO_APERTURA)
    compilate = _etichette(eventi, tipo_scheda,
                           filtro=lambda d: d.get("origine") == "campagna")
    # chi ha compilato senza che l'apertura sia stata registrata conta lo stesso
    aperte_tot = len(set(aperture) | set(compilate))

    invii = stato_invii()
    inviate = invii.get("totale", 0)
    consegnate = invii.get("delivered", 0)
    rimbalzate = invii.get("bounced", 0)

    def passo(numero, etichetta, nota=""):
        return (f'<div class="passo"><div class="n">{numero}</div>'
                f'<div class="l">{e(etichetta)}</div>'
                + (f'<div class="mini">{e(nota)}</div>' if nota else "")
                + "</div>")

    riga = (
        '<div class="riga-campagna">'
        + passo(inviate or "—", "inviate")
        + passo(consegnate or "—", "consegnate",
                f"{rimbalzate} rimbalzate" if rimbalzate else "")
        + passo(aperte_tot, "hanno aperto")
        + passo(len(compilate), "hanno compilato")
        + passo(call_fissate, "call fissate")
        + "</div>"
    )

    if not inviate and not aperte_tot:
        return riga + ('<div class="vuoto">Nessun dato ancora. I numeri compaiono '
                       'appena parte una campagna.</div>')

    da_richiamare = sorted(set(aperture) - set(compilate))
    if da_richiamare:
        carte = "".join(
            '<div class="card"><div class="info">'
            f'<div class="nome">{e(x.replace("-", " ").title())}</div>'
            f'<div class="servizio">ha aperto il {e(aperture[x])} e non ha compilato</div>'
            '</div><div class="azioni">'
            f'<a class="btn" href="/nia/questionario/{e(x)}?corto=1" target="_blank" '
            'title="Apri il suo questionario">&#128203;</a></div></div>'
            for x in da_richiamare)
        elenco = (f'<h2>Aperto e non compilato<span class="badge">{len(da_richiamare)}'
                  '</span></h2>'
                  '<p class="hint-abb">Hanno guardato e si sono fermati: sono i piu'
                  " caldi della lista. Una telefonata qui vale dieci mail nuove.</p>"
                  + carte)
    else:
        elenco = ('<div class="vuoto">Nessuno si &egrave; fermato a met&agrave;: '
                  'chi ha aperto ha anche compilato &#127881;</div>')

    if not RESEND_CHIAVE:
        elenco += ('<p class="hint-abb">Inviate e consegnate non si vedono: manca '
                   '<code>RESEND_API_KEY</code> tra le variabili del servizio.</p>')
    return riga + elenco
