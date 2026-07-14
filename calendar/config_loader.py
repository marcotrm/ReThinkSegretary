"""Caricamento e validazione di config/clienti.json.

La config è la fonte di verità del multi-tenant: qui non si conosce nessun cliente
per nome, si legge il file. Aggiungere un cliente = modificare il JSON, mai il codice.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "clienti.json"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Chiusura:
    da: date
    a: date

    def copre(self, giorno: date) -> bool:
        return self.da <= giorno <= self.a


@dataclass(frozen=True)
class ConfigCalendario:
    timezone: ZoneInfo
    durata_slot_min: int
    capienza_per_slot: int
    anticipo_min_ore: int
    anticipo_max_giorni: int
    buffer_min: int
    orari_apertura: dict[str, list[tuple[time, time]]]
    chiusure: list[Chiusura]

    def intervalli_del_giorno(self, giorno: date) -> list[tuple[time, time]]:
        """Fasce di apertura di quel giorno; vuoto se chiuso o chiusura straordinaria."""
        if any(c.copre(giorno) for c in self.chiusure):
            return []
        return self.orari_apertura.get(GIORNI[giorno.weekday()], [])


@dataclass(frozen=True)
class Cliente:
    client_id: str
    nome: str
    attivo: bool
    vault_path: str
    calendario: ConfigCalendario


def _parse_ora(valore: str, dove: str) -> time:
    try:
        h, m = valore.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError) as exc:
        raise ConfigError(f"orario non valido '{valore}' in {dove}, atteso HH:MM") from exc


def _parse_calendario(raw: dict, client_id: str) -> ConfigCalendario:
    orari: dict[str, list[tuple[time, time]]] = {}
    for giorno, fasce in (raw.get("orari_apertura") or {}).items():
        if giorno not in GIORNI:
            raise ConfigError(f"[{client_id}] giorno sconosciuto '{giorno}', attesi: {GIORNI}")
        intervalli = []
        for fascia in fasce:
            inizio = _parse_ora(fascia[0], f"{client_id}/{giorno}")
            fine = _parse_ora(fascia[1], f"{client_id}/{giorno}")
            if inizio >= fine:
                raise ConfigError(f"[{client_id}] fascia invertita {giorno}: {fascia}")
            intervalli.append((inizio, fine))
        orari[giorno] = sorted(intervalli)

    chiusure = []
    for c in raw.get("chiusure") or []:
        da = date.fromisoformat(c["da"])
        a = date.fromisoformat(c["a"])
        if a < da:
            raise ConfigError(f"[{client_id}] chiusura invertita: {c}")
        chiusure.append(Chiusura(da=da, a=a))

    durata = int(raw.get("durata_slot_min", 30))
    if durata <= 0:
        raise ConfigError(f"[{client_id}] durata_slot_min deve essere > 0")
    capienza = int(raw.get("capienza_per_slot", 1))
    if capienza <= 0:
        raise ConfigError(f"[{client_id}] capienza_per_slot deve essere > 0")

    return ConfigCalendario(
        timezone=ZoneInfo(raw.get("timezone", "Europe/Rome")),
        durata_slot_min=durata,
        capienza_per_slot=capienza,
        anticipo_min_ore=int(raw.get("anticipo_min_ore", 0)),
        anticipo_max_giorni=int(raw.get("anticipo_max_giorni", 90)),
        buffer_min=int(raw.get("buffer_min", 0)),
        orari_apertura=orari,
        chiusure=chiusure,
    )


def carica_clienti(path: Path | str | None = None) -> dict[str, Cliente]:
    """Legge la config e restituisce {client_id: Cliente}. Solleva ConfigError se malformata."""
    path = Path(path or os.getenv("CLIENTI_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config non trovata: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config JSON non valida ({path}): {exc}") from exc

    clienti: dict[str, Cliente] = {}
    for voce in raw.get("clienti", []):
        cid = voce["client_id"]
        if cid in clienti:
            raise ConfigError(f"client_id duplicato: '{cid}'")
        clienti[cid] = Cliente(
            client_id=cid,
            nome=voce.get("nome", cid),
            attivo=bool(voce.get("attivo", False)),
            vault_path=voce.get("vault_path", f"vault/clienti/{cid}"),
            calendario=_parse_calendario(voce.get("calendario") or {}, cid),
        )
    return clienti


def adesso(tz: ZoneInfo) -> datetime:
    """Ora corrente nel fuso del cliente. Isolata qui per poterla sostituire nei test."""
    return datetime.now(tz)
