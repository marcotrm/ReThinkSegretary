"""Abbonamenti Stripe: incasso ricorrente dei siti e stato dei pagamenti nella console.

Come funziona il giro:
  1. Marco crea in Stripe UN prodotto ricorrente da 50 euro/mese e UN Payment Link.
  2. Il link si manda al cliente aggiungendo  ?client_reference_id=<slug-del-cliente>
     cosi' Stripe ci ridice di chi e' il pagamento.
  3. Stripe chiama il nostro webhook a ogni fatto rilevante (primo pagamento, rinnovo
     riuscito, pagamento fallito, disdetta).
  4. Ogni evento finisce nella tabella 'eventi' (tipo 'pagamento'): da li' la console
     ricostruisce chi e' in regola, chi e' in ritardo e chi ha disdetto.

Nessuna tabella nuova e nessuna chiave segreta nel codice: la firma si verifica con
STRIPE_WEBHOOK_SECRET preso dall'ambiente.
"""
from __future__ import annotations

import hashlib
import hmac
import html as html_mod
import time
from datetime import datetime, timezone

TIPO_PAGAMENTO = "pagamento"
TIPO_MANUTENZIONE = "manutenzione"

# quanto aspettiamo prima di considerare uno "in ritardo" dopo un pagamento fallito.
# Stripe ritenta da solo per circa due settimane: staccare al primo errore e' sbagliato,
# spesso e' solo una carta scaduta.
GIORNI_TOLLERANZA = 14

EVENTI_UTILI = {
    "checkout.session.completed": "iscritto",
    "invoice.paid": "pagato",
    "invoice.payment_succeeded": "pagato",
    "invoice.payment_failed": "fallito",
    "customer.subscription.deleted": "disdetto",
    "customer.subscription.paused": "sospeso",
}


def verifica_firma(corpo: bytes, intestazione: str | None, segreto: str,
                   tolleranza_sec: int = 300) -> tuple[bool, str]:
    """Controlla la firma di Stripe (schema v1, HMAC-SHA256). Senza questa chiunque
    potrebbe fingere un pagamento."""
    if not segreto:
        return False, "STRIPE_WEBHOOK_SECRET non configurato"
    if not intestazione:
        return False, "firma assente"
    parti = {}
    for pezzo in intestazione.split(","):
        if "=" in pezzo:
            k, v = pezzo.split("=", 1)
            parti.setdefault(k.strip(), []).append(v.strip())
    ts = (parti.get("t") or [""])[0]
    firme = parti.get("v1") or []
    if not ts or not firme:
        return False, "firma malformata"
    try:
        if abs(time.time() - int(ts)) > tolleranza_sec:
            return False, "firma scaduta"
    except ValueError:
        return False, "marca temporale non valida"
    atteso = hmac.new(segreto.encode(), f"{ts}.".encode() + corpo, hashlib.sha256).hexdigest()
    if any(hmac.compare_digest(atteso, f) for f in firme):
        return True, "ok"
    return False, "firma non corrispondente"


def _euro(centesimi) -> str:
    try:
        return f"{int(centesimi) / 100:.2f}".replace(".", ",") + " €"
    except Exception:  # noqa: BLE001
        return "—"


def estrai(evento: dict) -> dict | None:
    """Riduce un evento Stripe ai pochi campi che ci servono. None se non ci interessa."""
    tipo = str(evento.get("type") or "")
    esito = EVENTI_UTILI.get(tipo)
    if not esito:
        return None
    o = ((evento.get("data") or {}).get("object")) or {}
    rif = (o.get("client_reference_id") or "").strip()
    cliente = o.get("customer") or ""
    email = (o.get("customer_email") or o.get("customer_details", {}).get("email")
             or o.get("customer_address", {}).get("email") or "")
    nome = (o.get("customer_details", {}).get("name") or o.get("customer_name") or "")
    importo = o.get("amount_paid", o.get("amount_total", o.get("amount_due")))
    return {
        "esito": esito,
        "evento": tipo,
        "riferimento": rif,
        "stripe_customer": cliente,
        "email": email,
        "nome": nome,
        "importo": importo,
        "quando": datetime.now(timezone.utc).isoformat(),
    }


def stato_abbonamenti(eventi: list[dict]) -> list[dict]:
    """Ricostruisce lo stato attuale di ogni abbonato dagli eventi (dal piu' recente)."""
    per_cliente: dict[str, dict] = {}
    manutenzione: set[str] = set()

    for ev in reversed(eventi):          # dal piu' vecchio al piu' recente
        tipo = ev.get("tipo")
        d = ev.get("dati") or {}
        if tipo == TIPO_MANUTENZIONE:
            chi = d.get("chiave") or ""
            if d.get("attiva"):
                manutenzione.add(chi)
            else:
                manutenzione.discard(chi)
            continue
        if tipo != TIPO_PAGAMENTO:
            continue
        chiave = d.get("riferimento") or d.get("stripe_customer") or d.get("email") or "?"
        r = per_cliente.setdefault(chiave, {
            "chiave": chiave, "nome": "", "email": "", "importo": None,
            "ultimo_ok": None, "ultimo_ko": None, "stato": "sconosciuto",
        })
        r["nome"] = d.get("nome") or r["nome"]
        r["email"] = d.get("email") or r["email"]
        if d.get("importo"):
            r["importo"] = d["importo"]
        quando = ev.get("ts") or d.get("quando")
        esito = d.get("esito")
        if esito in ("pagato", "iscritto"):
            r["ultimo_ok"] = quando
            r["stato"] = "in regola"
        elif esito == "fallito":
            r["ultimo_ko"] = quando
            r["stato"] = "pagamento fallito"
        elif esito in ("disdetto", "sospeso"):
            r["stato"] = "disdetto"

    # un pagamento fallito diventa "in ritardo" solo dopo la tolleranza
    ora = datetime.now(timezone.utc)
    fuori = []
    for r in per_cliente.values():
        if r["stato"] == "pagamento fallito" and r["ultimo_ko"]:
            try:
                quando = datetime.fromisoformat(str(r["ultimo_ko"]).replace("Z", "+00:00"))
                if (ora - quando).days >= GIORNI_TOLLERANZA:
                    r["stato"] = "in ritardo"
            except Exception:  # noqa: BLE001
                pass
        r["manutenzione"] = r["chiave"] in manutenzione
        fuori.append(r)
    ordine = {"in ritardo": 0, "pagamento fallito": 1, "disdetto": 2, "in regola": 3}
    fuori.sort(key=lambda x: (ordine.get(x["stato"], 9), x.get("nome") or x["chiave"]))
    return fuori


def vista_abbonamenti(righe: list[dict], client_id: str, token: str) -> str:
    """Riquadro della console: chi paga, chi no, e il comando per la manutenzione."""
    e = html_mod.escape
    if not righe:
        return (
            '<div class="vuoto">Nessun abbonamento ancora. Quando il primo cliente paga '
            'compare qui &#128179;</div>'
            '<p class="hint-abb">Il collegamento con Stripe si attiva incollando l\'indirizzo '
            'del webhook nel pannello Stripe. Se questa lista resta vuota dopo un pagamento, '
            'il webhook non sta arrivando.</p>'
        )

    colori = {
        "in regola": ("#dcfce7", "#14532d", "In regola"),
        "pagamento fallito": ("#fef3c7", "#78350f", "Pagamento fallito"),
        "in ritardo": ("#fee2e2", "#7f1d1d", "In ritardo"),
        "disdetto": ("#e2e8f0", "#334155", "Disdetto"),
        "sconosciuto": ("#e2e8f0", "#334155", "Da verificare"),
    }
    in_regola = sum(1 for r in righe if r["stato"] == "in regola")
    problemi = sum(1 for r in righe if r["stato"] in ("in ritardo", "pagamento fallito"))
    incasso = sum((r.get("importo") or 0) for r in righe if r["stato"] == "in regola")

    kpi = (
        '<div class="kpi-wrap">'
        f'<div class="kpi"><div class="n">{in_regola}</div><div class="l">Paganti</div></div>'
        f'<div class="kpi"><div class="n">{problemi}</div><div class="l">Da sollecitare</div></div>'
        f'<div class="kpi"><div class="n">{_euro(incasso)}</div><div class="l">Al mese</div></div>'
        '</div>'
    )

    carte = []
    for r in righe:
        sfondo, testo_col, etichetta = colori.get(r["stato"], colori["sconosciuto"])
        nome = e(r.get("nome") or r["chiave"])
        email = e(r.get("email") or "")
        ultimo = str(r.get("ultimo_ok") or "")[:10] or "mai"
        manut = (' <span class="pill" style="background:#1e293b;color:#fff">in manutenzione</span>'
                 if r.get("manutenzione") else "")
        azione = ""
        if r["stato"] in ("in ritardo", "disdetto") and not r.get("manutenzione"):
            azione = (f'<button class="mini" onclick="manutenzione(\'{e(r["chiave"])}\',true)">'
                      'Metti in manutenzione</button>')
        elif r.get("manutenzione"):
            azione = (f'<button class="mini riattiva" onclick="manutenzione(\'{e(r["chiave"])}\',false)">'
                      'Riattiva il sito</button>')
        carte.append(
            '<div class="card"><div class="info">'
            f'<div class="ora">{nome}{manut}</div>'
            f'<div class="chi"><span class="pill" style="background:{sfondo};color:{testo_col}">'
            f'{etichetta}</span> &middot; ultimo incasso: {e(ultimo)}</div>'
            + (f'<div class="nota">{email}</div>' if email else "")
            + f'</div><div class="azioni">{azione}</div></div>'
        )

    script = f"""
<script>
async function manutenzione(chiave, attiva) {{
  const testo = attiva
    ? 'Mettere il sito di ' + chiave + ' in manutenzione?'
    : 'Rimettere online il sito di ' + chiave + '?';
  if (!confirm(testo)) return;
  try {{
    const r = await fetch('/{e(client_id)}/manutenzione?token={e(token)}', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{chiave: chiave, attiva: attiva}})
    }});
    if (!r.ok) throw new Error((await r.json()).detail || 'errore');
    location.reload();
  }} catch (err) {{ alert('Non riuscito: ' + err.message); }}
}}
</script>"""
    return kpi + "\n".join(carte) + script


def applica_regole_automatiche(storage, client_id: str) -> list[dict]:
    """Accende e spegne la manutenzione da sola, senza che nessuno guardi la console.

    - chi resta non pagante oltre la tolleranza (o disdice) -> sito in manutenzione
    - chi torna a pagare -> sito ONLINE di nuovo, subito

    Ritorna l'elenco dei cambiamenti fatti, per poterli annunciare.
    """
    try:
        eventi = storage.elenca_eventi(client_id, limite=400)
    except Exception:  # noqa: BLE001
        return []
    cambi = []
    for r in stato_abbonamenti(eventi):
        giu = r["stato"] in ("in ritardo", "disdetto")
        if giu and not r["manutenzione"]:
            storage.registra_evento(client_id, TIPO_MANUTENZIONE, None,
                                    {"chiave": r["chiave"], "attiva": True,
                                     "automatico": True, "motivo": r["stato"]})
            cambi.append({"chiave": r["chiave"], "attiva": True, "motivo": r["stato"],
                          "nome": r.get("nome") or r["chiave"]})
        elif r["stato"] == "in regola" and r["manutenzione"]:
            storage.registra_evento(client_id, TIPO_MANUTENZIONE, None,
                                    {"chiave": r["chiave"], "attiva": False,
                                     "automatico": True, "motivo": "pagamento ricevuto"})
            cambi.append({"chiave": r["chiave"], "attiva": False, "motivo": "pagamento ricevuto",
                          "nome": r.get("nome") or r["chiave"]})
    return cambi
