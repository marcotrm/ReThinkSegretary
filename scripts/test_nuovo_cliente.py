"""Test del wizard nuovo_cliente. Girano su una copia temporanea del repo:

    python -m pytest scripts -q
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

QUI = Path(__file__).resolve().parent
REPO = QUI.parent
sys.path.insert(0, str(QUI))
sys.path.insert(0, str(REPO / "calendar"))

from nuovo_cliente import (  # noqa: E402
    WizardError,
    aggiungi_config,
    crea_vault,
    parse_orari,
    solo_cifre,
)

DATI_BASE = {
    "client_id": "bar-test",
    "nome": "Bar Test",
    "whatsapp": "390000000042",
    "titolare": "393330000042",
    "durata_slot_min": 30,
    "capienza_per_slot": 2,
    "anticipo_min_ore": 1,
    "anticipo_max_giorni": 60,
    "buffer_min": 5,
    "backend_url": "https://backend.example",
}


@pytest.fixture()
def root(tmp_path):
    """Un mini-repo: il template VERO + una config con un cliente esistente."""
    shutil.copytree(REPO / "vault" / "_TEMPLATE", tmp_path / "vault" / "_TEMPLATE")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "clienti.json").write_text(json.dumps({
        "versione": 1,
        "clienti": [{
            "client_id": "esistente",
            "nome": "Gia' Presente",
            "attivo": True,
            "canali": {"whatsapp": {"provider": "evolution", "phone_id": "390000000001"}},
            "calendario": {"timezone": "Europe/Rome", "orari_apertura": {"lun": [["09:00", "18:00"]]}},
        }],
    }), encoding="utf-8")
    return tmp_path


def dati(orari="lun-ven=09:00-13:00,14:00-19:00;sab=09:00-13:00", **extra):
    d = {**DATI_BASE, "orari_apertura": parse_orari(orari), **extra}
    return d


# --- parse_orari ---------------------------------------------------------------

def test_parse_orari_intervallo_e_giorno_singolo():
    o = parse_orari("lun-ven=09:00-13:00,14:00-19:00;sab=09:00-13:00")
    assert o["lun"] == [["09:00", "13:00"], ["14:00", "19:00"]]
    assert o["ven"] == o["lun"]
    assert o["sab"] == [["09:00", "13:00"]]
    assert o["dom"] == []  # non citato = chiuso


def test_parse_orari_giorni_separati_da_virgola():
    o = parse_orari("lun,mer=10:00-18:00")
    assert o["lun"] == [["10:00", "18:00"]] and o["mer"] == o["lun"]
    assert o["mar"] == []


def test_parse_orari_errori():
    for testo in [
        "xyz=09:00-13:00",       # giorno sconosciuto
        "ven-lun=09:00-13:00",   # intervallo invertito
        "lun=13:00-09:00",       # fascia invertita
        "lun=1-2",               # orario non valido
        "lun=08:00-09:00,10:00-11:00,12:00-13:00",  # 3 fasce
        "lun 09:00-13:00",       # manca '='
    ]:
        with pytest.raises(WizardError):
            parse_orari(testo)


def test_solo_cifre():
    assert solo_cifre("+39 333 111 22 33") == "393331112233"
    assert solo_cifre("393331112233@s.whatsapp.net") == "393331112233"


# --- crea_vault -----------------------------------------------------------------

def test_vault_precompilato(root):
    dest = crea_vault(root, dati())

    orari = (dest / "orari.md").read_text(encoding="utf-8")
    assert "| Lunedì | 09:00 | 19:00 | 13:00-14:00 | no |" in orari
    assert "| Sabato | 09:00 | 13:00 | — | no |" in orari
    assert "| Domenica | — | — | — | sì |" in orari
    assert "<<client_id>>" not in orari and "Bar Test" in orari

    pren = (dest / "prenotazioni.md").read_text(encoding="utf-8")
    assert re.search(r"\|\s*`capienza_per_slot`\s*\|\s*2", pren)
    assert re.search(r"\|\s*`buffer_min`\s*\|\s*5", pren)

    esc = (dest / "escalation.md").read_text(encoding="utf-8")
    assert "+393330000042" in esc

    # i contenuti che servono dal cliente restano volutamente da compilare
    assert "<<" in (dest / "faq.md").read_text(encoding="utf-8")


def test_vault_gia_esistente_rifiutato(root):
    crea_vault(root, dati())
    with pytest.raises(WizardError):
        crea_vault(root, dati())


# --- aggiungi_config ------------------------------------------------------------

def test_config_aggiunta_e_caricabile(root):
    crea_vault(root, dati())
    token = aggiungi_config(root, dati())
    assert re.fullmatch(r"[0-9a-f]{32}", token)

    config = json.loads((root / "config" / "clienti.json").read_text(encoding="utf-8"))
    nuovo = next(c for c in config["clienti"] if c["client_id"] == "bar-test")
    assert nuovo["attivo"] is False  # il go-live e' una decisione, non un default
    assert nuovo["canali"]["whatsapp"]["instance"] == "bar-test"
    assert nuovo["escalation"]["whatsapp"] == "+393330000042"
    assert nuovo["calendario"]["orari_apertura"]["dom"] == []

    # digeribile dal calendar service vero, non solo JSON valido
    from config_loader import carica_clienti
    clienti = carica_clienti(root / "config" / "clienti.json")
    assert "bar-test" in clienti
    assert clienti["bar-test"].escalation.agenda_token == token


def test_client_id_duplicato_rifiutato(root):
    with pytest.raises(WizardError):
        aggiungi_config(root, dati(client_id="esistente"))


def test_parametri_vault_e_config_combaciano(root):
    """La tabella di prenotazioni.md e il blocco config devono dire la stessa cosa:
    e' esattamente cio' che verifica_coerenza controlla sui clienti veri."""
    d = dati()
    dest = crea_vault(root, d)
    aggiungi_config(root, d)

    pren = (dest / "prenotazioni.md").read_text(encoding="utf-8")
    config = json.loads((root / "config" / "clienti.json").read_text(encoding="utf-8"))
    cal = next(c for c in config["clienti"] if c["client_id"] == "bar-test")["calendario"]
    for nome in ["durata_slot_min", "capienza_per_slot", "anticipo_min_ore", "anticipo_max_giorni", "buffer_min"]:
        m = re.search(rf"\|\s*`{nome}`\s*\|\s*(\d+)\s*\|", pren)
        assert m, f"{nome} non trovato in prenotazioni.md"
        assert int(m.group(1)) == cal[nome], nome
