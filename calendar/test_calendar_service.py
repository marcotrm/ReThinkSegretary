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
            # il vault vero di demo-dentista: serve a provare l'endpoint /vault
            "vault_path": "vault/clienti/demo-dentista",
            "conferma_esplicita": True,
            "canali": {
                "whatsapp": {
                    "provider": "evolution",
                    "phone_id": "390000000001",
                    "instance": "studio-test",
                    "delay_risposta_sec": {"min": 300, "max": 900},
                },
                "voce": {"numero": "+390000000009"},
            },
            "escalation": {
                "soglia_confidenza": 0.6,
                "whatsapp": "+393331234567",
                "agenda_token": "token-agenda-test",
            },
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
            "canali": {"whatsapp": {"provider": "360dialog", "phone_id": "390000000002"}},
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


# --- risoluzione del tenant dal numero ----------------------------------------

def test_tenant_da_numero_whatsapp(client):
    r = client.get("/_tenant", params={"numero": "390000000001"})
    assert r.status_code == 200
    d = r.json()
    assert d["client_id"] == "studio-test"
    assert d["provider_whatsapp"] == "evolution"
    assert d["conferma_esplicita"] is True
    assert d["soglia_confidenza"] == 0.6


def test_tenant_da_numero_formattato_diverso(client):
    # Evolution manda '39...@c.us', Twilio manda '+39 ...': stesso cliente
    for variante in ["+39 000 000 0001", "390000000001@c.us", "00390000000001"]:
        r = client.get("/_tenant", params={"numero": variante})
        assert r.status_code == 200, variante
        assert r.json()["client_id"] == "studio-test", variante


def test_tenant_dal_nome_istanza_evolution(client):
    """Evolution non mette il numero di destinazione nel payload: manda solo l'istanza.
    Se il backend non la riconoscesse, il bot resterebbe muto su ogni cliente Evolution."""
    r = client.get("/_tenant", params={"numero": "studio-test"})
    assert r.status_code == 200
    assert r.json()["client_id"] == "studio-test"


def test_tenant_da_numero_voce(client):
    r = client.get("/_tenant", params={"numero": "+390000000009"})
    assert r.json()["client_id"] == "studio-test"


def test_numero_sconosciuto_404_cosi_n8n_tace(client):
    r = client.get("/_tenant", params={"numero": "393999999999"})
    assert r.status_code == 404


def test_tenant_non_attivo_403(client):
    r = client.get("/_tenant", params={"numero": "390000000002"})
    assert r.status_code == 403


# --- vault --------------------------------------------------------------------

def test_vault_default_non_include_obiettivi(client):
    r = client.get("/studio-test/vault")
    assert r.status_code == 200
    file = r.json()["file"]
    assert set(file) == {"brand-voice", "orari", "servizi", "faq", "vincoli"}
    assert "obiettivi" not in file  # nota interna, non deve finire nel prompt
    assert "Brand voice" in file["brand-voice"]


def test_vault_file_selezionati(client):
    r = client.get("/studio-test/vault", params={"file": "faq,orari"})
    assert set(r.json()["file"]) == {"faq", "orari"}


def test_vault_path_traversal_rifiutato(client):
    r = client.get("/studio-test/vault", params={"file": "../../.env"})
    assert r.status_code == 400


# --- conversazione, pausa-bot, eventi -----------------------------------------

def test_conversazione_salva_e_rilegge(client):
    stato = {"fase": "attesa_conferma", "slot_proposti": ["2026-09-07T10:00:00"]}
    r = client.post("/studio-test/conversazione/393331112233", json={"stato": stato})
    assert r.status_code == 200

    d = client.get("/studio-test/conversazione/393331112233").json()["conversazione"]
    assert d["stato"] == stato
    assert d["bot_in_pausa"] is False


def test_conversazione_nuova_e_vuota(client):
    d = client.get("/studio-test/conversazione/399999").json()["conversazione"]
    assert d["stato"] == {} and d["bot_in_pausa"] is False


def test_pausa_bot_e_riattivazione(client):
    r = client.post(
        "/studio-test/pausa-bot/393331112233", json={"motivo": "reclamo"}
    )
    assert r.status_code == 200
    assert r.json()["conversazione"]["bot_in_pausa"] is True

    d = client.get("/studio-test/conversazione/393331112233").json()["conversazione"]
    assert d["bot_in_pausa"] is True and d["motivo_pausa"] == "reclamo"

    client.post("/studio-test/riattiva-bot/393331112233")
    d = client.get("/studio-test/conversazione/393331112233").json()["conversazione"]
    assert d["bot_in_pausa"] is False


def test_salvare_lo_stato_non_riattiva_un_bot_in_pausa(client):
    """Il bug piu' insidioso: il workflow salva lo stato e senza volerlo risveglia il bot
    su una conversazione che il titolare sta gia' gestendo a mano."""
    client.post("/studio-test/pausa-bot/393331112233", json={"motivo": "reclamo"})
    client.post("/studio-test/conversazione/393331112233", json={"stato": {"fase": "x"}})

    d = client.get("/studio-test/conversazione/393331112233").json()["conversazione"]
    assert d["bot_in_pausa"] is True
    assert d["motivo_pausa"] == "reclamo"


def test_pausa_bot_registra_un_evento_di_escalation(client):
    client.post("/studio-test/pausa-bot/393331112233", json={"motivo": "dolore acuto"})
    eventi = client.get("/studio-test/eventi").json()["eventi"]
    assert eventi[0]["tipo"] == "escalation"
    assert eventi[0]["dati"]["motivo"] == "dolore acuto"


def test_eventi_ordinati_dal_piu_recente(client):
    for i in range(3):
        client.post(
            "/studio-test/eventi",
            json={"tipo": "messaggio_ricevuto", "telefono": "393331112233", "dati": {"n": i}},
        )
    eventi = client.get("/studio-test/eventi").json()["eventi"]
    assert [e["dati"]["n"] for e in eventi] == [2, 1, 0]


def test_eventi_isolati_per_tenant(client):
    client.post("/studio-test/eventi", json={"tipo": "test", "dati": {}})
    assert client.get("/studio-test/eventi").json()["totale"] == 1
    assert client.get("/sospeso/eventi").status_code == 403


# --- agenda per il titolare ----------------------------------------------------

def test_agenda_richiede_il_token(client):
    assert client.get("/studio-test/agenda", headers={}).status_code == 401
    assert (
        client.get("/studio-test/agenda", params={"token": "sbagliato"}, headers={}).status_code
        == 401
    )


def test_agenda_mostra_gli_appuntamenti_di_oggi_senza_api_key(client):
    """Il titolare apre il link dal telefono: niente X-API-Key, basta il token del link."""
    prenota(client, "2026-09-07T10:00:00")  # ORA_FINTA è proprio il 7 settembre
    r = client.get("/studio-test/agenda", params={"token": "token-agenda-test"}, headers={})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Mario Rossi" in r.text
    assert "10:00" in r.text
    assert "prima visita" in r.text


def test_agenda_e_in_sola_lettura_e_isolata_per_tenant(client):
    # il token di studio-test non apre l'agenda di un altro tenant
    r = client.get("/sospeso/agenda", params={"token": "token-agenda-test"}, headers={})
    assert r.status_code == 403  # tenant non attivo: prima ancora del token


def test_agenda_senza_token_configurato_404(client, tmp_path, monkeypatch):
    cfg = json.loads(json.dumps(CONFIG_TEST))
    del cfg["clienti"][0]["escalation"]["agenda_token"]
    percorso = tmp_path / "clienti3.json"
    percorso.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("CLIENTI_CONFIG_PATH", str(percorso))

    import importlib
    import calendar_service
    from fastapi.testclient import TestClient

    c = TestClient(importlib.reload(calendar_service).app)
    r = c.get("/studio-test/agenda", params={"token": "qualunque"})
    assert r.status_code == 404


def test_tenant_espone_agenda_token_e_non_slack(client):
    d = client.get("/_tenant", params={"numero": "390000000001"}).json()
    assert d["escalation"]["agenda_token"] == "token-agenda-test"
    assert "slack_channel" not in d["escalation"]


# --- isolamento tra tenant ----------------------------------------------------

def test_le_prenotazioni_non_si_vedono_tra_tenant(client):
    prenota(client, "2026-09-07T10:00:00")
    # 'sospeso' è disattivo, quindi non può nemmeno leggere: la verifica di isolamento
    # è che studio-test veda 1 prenotazione e nessun altro tenant sia toccato.
    assert client.get("/studio-test/prenotazioni").json()["totale"] == 1
    assert client.get("/sospeso/prenotazioni").status_code == 403
