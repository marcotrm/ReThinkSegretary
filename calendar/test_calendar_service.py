"""Test del calendar service. Girano su InMemoryStorage, nessun database richiesto.

    cd calendar && python -m pytest -q
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

ROMA = ZoneInfo("Europe/Rome")

# Lunedì 2026-09-07, ore 08:00. Fisso, così i test non dipendono da quando girano.
ORA_FINTA = datetime(2026, 9, 7, 8, 0, tzinfo=ROMA)

CONFIG_TEST = {
    "versione": 1,
    "clienti": [
        {
            "client_id": "studio-test",
            "nome": "Studio di test",
            "attivo": True,
            "vault_path": "vault/clienti/studio-test",
            "calendario": {
                "timezone": "Europe/Rome",
                "durata_slot_min": 30,
                "capienza_per_slot": 1,
                "anticipo_min_ore": 2,
                "anticipo_max_giorni": 30,
                "buffer_min": 0,
                "orari_apertura": {
                    "lun": [["09:00", "13:00"], ["14:00", "18:00"]],
                    "mar": [["09:00", "13:00"]],
                    "mer": [], "gio": [], "ven": [], "sab": [], "dom": [],
                },
                "chiusure": [{"da": "2026-09-08", "a": "2026-09-08", "motivo": "chiusura"}],
            },
        },
        {
            "client_id": "sospeso",
            "nome": "Cliente sospeso",
            "attivo": False,
            "calendario": {"timezone": "Europe/Rome", "orari_apertura": {"lun": [["09:00", "18:00"]]}},
        },
    ],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "clienti.json"
    cfg.write_text(json.dumps(CONFIG_TEST), encoding="utf-8")
    monkeypatch.setenv("CLIENTI_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("API_KEY", "chiave-test")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import config_loader

    monkeypatch.setattr(config_loader, "adesso", lambda tz: ORA_FINTA.astimezone(tz))

    import calendar_service
    import importlib

    calendar_service = importlib.reload(calendar_service)

    from fastapi.testclient import TestClient

    c = TestClient(calendar_service.app)
    c.headers.update({"X-API-Key": "chiave-test"})
    return c


def prenota(client, inizio: str, **kw):
    body = {
        "servizio": "prima visita",
        "nome_cliente": "Mario Rossi",
        "telefono": "+393331112233",
        "inizio": inizio,
        **kw,
    }
    return client.post("/studio-test/prenota", json=body)


# --- multi-tenant e auth ------------------------------------------------------

def test_cliente_sconosciuto_404(client):
    r = client.get("/non-esiste/disponibilita")
    assert r.status_code == 404


def test_cliente_non_attivo_403(client):
    r = client.get("/sospeso/disponibilita")
    assert r.status_code == 403


def test_senza_api_key_401(client):
    r = client.get("/studio-test/disponibilita", headers={"X-API-Key": "sbagliata"})
    assert r.status_code == 401


def test_health_non_richiede_auth(client):
    r = client.get("/health", headers={})
    assert r.status_code == 200
    assert r.json()["clienti_attivi"] == ["studio-test"]


# --- disponibilità ------------------------------------------------------------

def test_disponibilita_rispetta_orari_e_anticipo(client):
    r = client.get("/studio-test/disponibilita", params={"da": "2026-09-07", "a": "2026-09-07"})
    assert r.status_code == 200
    slot = [datetime.fromisoformat(s["inizio"]) for s in r.json()["slot"]]

    # anticipo minimo 2h da un "adesso" delle 08:00 → il primo slot utile è alle 10:00,
    # non alle 09:00 dell'apertura.
    assert slot[0].strftime("%H:%M") == "10:00"
    # pausa pranzo: niente slot tra le 13:00 e le 14:00
    assert not any(s.strftime("%H:%M") in {"13:00", "13:30"} for s in slot)
    # l'ultimo slot da 30' deve finire entro le 18:00
    assert slot[-1].strftime("%H:%M") == "17:30"


def test_giorno_chiuso_nessuno_slot(client):
    # martedì 8 settembre è una chiusura straordinaria
    r = client.get("/studio-test/disponibilita", params={"da": "2026-09-08", "a": "2026-09-08"})
    assert r.json()["slot"] == []


def test_domenica_nessuno_slot(client):
    r = client.get("/studio-test/disponibilita", params={"da": "2026-09-13", "a": "2026-09-13"})
    assert r.json()["slot"] == []


def test_durata_lunga_non_scavalca_la_chiusura(client):
    r = client.get(
        "/studio-test/disponibilita",
        params={"da": "2026-09-07", "a": "2026-09-07", "durata_min": 90},
    )
    slot = [datetime.fromisoformat(s["inizio"]) for s in r.json()["slot"]]
    # un appuntamento di 90' non può iniziare alle 12:00 (finirebbe alle 13:30, oltre la pausa)
    assert all(s.strftime("%H:%M") != "12:00" for s in slot)
    assert slot[-1].strftime("%H:%M") == "16:30"


def test_limite_slot(client):
    r = client.get(
        "/studio-test/disponibilita",
        params={"da": "2026-09-07", "a": "2026-09-30", "limite": 3},
    )
    assert len(r.json()["slot"]) == 3


def test_finestra_troppo_ampia_400(client):
    r = client.get(
        "/studio-test/disponibilita", params={"da": "2026-09-07", "a": "2027-09-07"}
    )
    assert r.status_code == 400


# --- prenotazione -------------------------------------------------------------

def test_prenota_e_lo_slot_sparisce(client):
    r = prenota(client, "2026-09-07T10:00:00")
    assert r.status_code == 200, r.text
    pid = r.json()["prenotazione"]["id"]

    d = client.get("/studio-test/disponibilita", params={"da": "2026-09-07", "a": "2026-09-07"})
    orari = [datetime.fromisoformat(s["inizio"]).strftime("%H:%M") for s in d.json()["slot"]]
    assert "10:00" not in orari

    lista = client.get("/studio-test/prenotazioni").json()
    assert lista["totale"] == 1
    assert lista["prenotazioni"][0]["id"] == pid


def test_doppia_prenotazione_stesso_slot_409(client):
    assert prenota(client, "2026-09-07T10:00:00").status_code == 200
    r = prenota(client, "2026-09-07T10:00:00")
    assert r.status_code == 409


def test_prenotazione_sovrapposta_parzialmente_409(client):
    # 10:00 per 60' occupa anche le 10:30
    assert prenota(client, "2026-09-07T10:00:00", durata_min=60).status_code == 200
    assert prenota(client, "2026-09-07T10:30:00").status_code == 409


def test_prenota_fuori_orario_409(client):
    r = prenota(client, "2026-09-07T20:00:00")
    assert r.status_code == 409
    assert "orari" in r.json()["detail"]


def test_prenota_in_pausa_pranzo_409(client):
    assert prenota(client, "2026-09-07T13:00:00").status_code == 409


def test_prenota_senza_anticipo_minimo_409(client):
    # adesso sono le 08:00, questa sarebbe fra un'ora: sotto le 2h di anticipo
    r = prenota(client, "2026-09-07T09:00:00")
    assert r.status_code == 409
    assert "anticipo" in r.json()["detail"]


def test_prenota_oltre_anticipo_massimo_409(client):
    r = prenota(client, "2026-11-02T10:00:00")  # oltre i 30 giorni
    assert r.status_code == 409


def test_prenota_giorno_di_chiusura_409(client):
    assert prenota(client, "2026-09-08T10:00:00").status_code == 409


def test_capienza_multipla(client, tmp_path, monkeypatch):
    # con capienza 2 lo stesso orario accetta due prenotazioni, la terza no
    cfg = json.loads(json.dumps(CONFIG_TEST))
    cfg["clienti"][0]["calendario"]["capienza_per_slot"] = 2
    percorso = tmp_path / "clienti2.json"
    percorso.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("CLIENTI_CONFIG_PATH", str(percorso))

    import importlib
    import calendar_service
    from fastapi.testclient import TestClient

    c = TestClient(importlib.reload(calendar_service).app)
    c.headers.update({"X-API-Key": "chiave-test"})

    assert prenota(c, "2026-09-07T10:00:00").status_code == 200
    assert prenota(c, "2026-09-07T10:00:00").status_code == 200
    assert prenota(c, "2026-09-07T10:00:00").status_code == 409


# --- spostamento e cancellazione ---------------------------------------------

def test_sposta(client):
    pid = prenota(client, "2026-09-07T10:00:00").json()["prenotazione"]["id"]
    r = client.post(
        "/studio-test/sposta",
        json={"prenotazione_id": pid, "nuovo_inizio": "2026-09-07T15:00:00"},
    )
    assert r.status_code == 200
    assert r.json()["prenotazione"]["inizio"].startswith("2026-09-07T15:00")

    orari = [
        datetime.fromisoformat(s["inizio"]).strftime("%H:%M")
        for s in client.get(
            "/studio-test/disponibilita", params={"da": "2026-09-07", "a": "2026-09-07"}
        ).json()["slot"]
    ]
    assert "10:00" in orari and "15:00" not in orari


def test_sposta_sullo_stesso_orario_non_va_in_conflitto_con_se_stessa(client):
    pid = prenota(client, "2026-09-07T10:00:00").json()["prenotazione"]["id"]
    r = client.post(
        "/studio-test/sposta",
        json={"prenotazione_id": pid, "nuovo_inizio": "2026-09-07T10:00:00"},
    )
    assert r.status_code == 200


def test_sposta_su_slot_occupato_409(client):
    pid = prenota(client, "2026-09-07T10:00:00").json()["prenotazione"]["id"]
    prenota(client, "2026-09-07T11:00:00", nome_cliente="Anna Bianchi")
    r = client.post(
        "/studio-test/sposta",
        json={"prenotazione_id": pid, "nuovo_inizio": "2026-09-07T11:00:00"},
    )
    assert r.status_code == 409


def test_sposta_prenotazione_inesistente_404(client):
    r = client.post(
        "/studio-test/sposta",
        json={"prenotazione_id": "nonesiste", "nuovo_inizio": "2026-09-07T15:00:00"},
    )
    assert r.status_code == 404


def test_cancella_libera_lo_slot(client):
    pid = prenota(client, "2026-09-07T10:00:00").json()["prenotazione"]["id"]
    r = client.post("/studio-test/cancella", json={"prenotazione_id": pid})
    assert r.status_code == 200
    assert r.json()["prenotazione"]["stato"] == "cancellata"

    orari = [
        datetime.fromisoformat(s["inizio"]).strftime("%H:%M")
        for s in client.get(
            "/studio-test/disponibilita", params={"da": "2026-09-07", "a": "2026-09-07"}
        ).json()["slot"]
    ]
    assert "10:00" in orari

    assert client.get("/studio-test/prenotazioni").json()["totale"] == 0
    assert (
        client.get(
            "/studio-test/prenotazioni", params={"includi_cancellate": True}
        ).json()["totale"]
        == 1
    )


def test_cancella_inesistente_404(client):
    r = client.post("/studio-test/cancella", json={"prenotazione_id": "nonesiste"})
    assert r.status_code == 404


# --- isolamento tra tenant ----------------------------------------------------

def test_le_prenotazioni_non_si_vedono_tra_tenant(client):
    prenota(client, "2026-09-07T10:00:00")
    # 'sospeso' è disattivo, quindi non può nemmeno leggere: la verifica di isolamento
    # è che studio-test veda 1 prenotazione e nessun altro tenant sia toccato.
    assert client.get("/studio-test/prenotazioni").json()["totale"] == 1
    assert client.get("/sospeso/prenotazioni").status_code == 403
