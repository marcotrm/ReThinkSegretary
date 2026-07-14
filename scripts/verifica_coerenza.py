"""Controlla che config/clienti.json e i vault dicano la stessa cosa.

Il vault è la fonte di verità, la config è una sua derivazione: se divergono, il cliente
riceve risposte che il calendario poi contraddice. Questo script trova la divergenza
prima che la trovi un cliente vero.

    python scripts/verifica_coerenza.py

Esce con 1 se trova problemi: usabile come check pre-commit o in CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# I nomi delle note contengono emoji; la console Windows (cp1252) non le sa stampare e
# lo script morirebbe proprio mentre segnala un problema.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PARAMETRI = ["durata_slot_min", "capienza_per_slot", "anticipo_min_ore", "anticipo_max_giorni", "buffer_min"]
FILE_VAULT = [
    "orari.md", "servizi.md", "faq.md", "brand-voice.md",
    "vincoli.md", "prenotazioni.md", "escalation.md", "obiettivi.md",
]


def parametri_dal_vault(prenotazioni_md: Path) -> dict[str, int]:
    """Legge la tabella 'Parametri calendario' di prenotazioni.md."""
    testo = prenotazioni_md.read_text(encoding="utf-8")
    trovati: dict[str, int] = {}
    for nome in PARAMETRI:
        m = re.search(rf"\|\s*`{nome}`\s*\|\s*(\d+)\s*\|", testo)
        if m:
            trovati[nome] = int(m.group(1))
    return trovati


def link_rotti() -> list[str]:
    """Wikilink [[...]] che non puntano a nessuna nota.

    In Obsidian un link rotto non da' errore: diventa solo un link grigio su cui nessuno
    clicchera' mai. Meglio accorgersene qui.
    """
    vault = ROOT / "vault"
    note = {p.stem for p in vault.rglob("*.md")}
    percorsi = {p.relative_to(vault).with_suffix("").as_posix() for p in vault.rglob("*.md")}

    rotti = []
    for md in vault.rglob("*.md"):
        if "_TEMPLATE" in md.as_posix():
            continue  # il template contiene segnaposto, non link veri
        for link in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", md.read_text(encoding="utf-8")):
            link = link.strip()
            if link not in percorsi and link not in note:
                rotti.append(f"link rotto in '{md.name}': [[{link}]]")
    return rotti


def main() -> int:
    problemi: list[str] = []
    config = json.loads((ROOT / "config" / "clienti.json").read_text(encoding="utf-8"))
    problemi.extend(link_rotti())

    for cliente in config["clienti"]:
        cid = cliente["client_id"]
        vault = ROOT / cliente.get("vault_path", f"vault/clienti/{cid}")

        if not vault.is_dir():
            problemi.append(f"[{cid}] vault mancante: {vault}")
            continue

        mancanti = [f for f in FILE_VAULT if not (vault / f).exists()]
        if mancanti:
            problemi.append(f"[{cid}] file di vault mancanti: {', '.join(mancanti)}")

        for f in FILE_VAULT:
            percorso = vault / f
            if percorso.exists() and "<<" in percorso.read_text(encoding="utf-8"):
                problemi.append(f"[{cid}] {f} contiene ancora segnaposto <<...>> da compilare")

        cal = cliente.get("calendario", {})
        prenotazioni = vault / "prenotazioni.md"
        if prenotazioni.exists():
            dal_vault = parametri_dal_vault(prenotazioni)
            for nome, atteso in dal_vault.items():
                effettivo = cal.get(nome)
                if effettivo != atteso:
                    problemi.append(
                        f"[{cid}] {nome}: vault dice {atteso}, config dice {effettivo} "
                        f"- il vault e' la fonte di verita', allinea la config"
                    )
            non_letti = [p for p in PARAMETRI if p not in dal_vault]
            if non_letti:
                problemi.append(
                    f"[{cid}] prenotazioni.md non dichiara: {', '.join(non_letti)}"
                )

    # La config deve anche essere caricabile dal servizio, non solo JSON valido.
    sys.path.insert(0, str(ROOT / "calendar"))
    try:
        from config_loader import carica_clienti

        carica_clienti(ROOT / "config" / "clienti.json")
    except Exception as exc:  # noqa: BLE001
        problemi.append(f"config non caricabile dal calendar service: {exc}")

    # ASCII soltanto: la console Windows (cp1252) non digerisce i simboli unicode.
    if problemi:
        print("PROBLEMI TROVATI:\n")
        for p in problemi:
            print(f"  [X] {p}")
        return 1

    attivi = [c["client_id"] for c in config["clienti"] if c.get("attivo")]
    print(f"[OK] config e vault coerenti - clienti attivi: {', '.join(attivi) or 'nessuno'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
