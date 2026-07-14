"""Caricamento e validazione di config/clienti.json.

La config è la fonte di verità del multi-tenant: qui non si conosce nessun cliente
per nome, si legge il file. Aggiungere un cliente = modificare il JSON, mai il codice.
"""

from __future__ import annotations

import json
import os
import re
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
class Escalation:
    soglia_confidenza: float
    whatsapp: str | None
    slack_channel: str | None
    email: str | None


@dataclass(frozen=True)
class Cliente:
    client_id: str
    nome: str
    attivo: bool
    vault_path: str
    calendario: ConfigCalendario
    escalation: Escalation
    # Provider WhatsApp: 'evolution' nel pilota, '360dialog' a regime. Il workflow n8n non
    # deve MAI cablare l'uno o l'altro: migrare un cliente = cambiare questo campo.
    provider_whatsapp: str
    phone_id: str | None
    instance: str | None
    delay_risposta_sec: tuple[int, int]
    # Se True la AI manda un riepilogo e aspetta un "confermo" prima di prenotare davvero.
    conferma_esplicita: bool
    numero_voce: str | None
    elevenlabs_agent_id: str | None


PROVIDER_WHATSAPP = {"evolution", "360dialog"}


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
    numeri_visti: dict[str, str] = {}

    for voce in raw.get("clienti", []):
        cid = voce["client_id"]
        if cid in clienti:
            raise ConfigError(f"client_id duplicato: '{cid}'")

        canali = voce.get("canali") or {}
        wa = canali.get("whatsapp") or {}
        vocale = canali.get("voce") or {}

        provider = wa.get("provider", "evolution")
        if provider not in PROVIDER_WHATSAPP:
            raise ConfigError(
                f"[{cid}] provider WhatsApp sconosciuto '{provider}', attesi: {sorted(PROVIDER_WHATSAPP)}"
            )

        delay = wa.get("delay_risposta_sec") or {}
        delay_min, delay_max = int(delay.get("min", 300)), int(delay.get("max", 900))
        if delay_min > delay_max:
            raise ConfigError(f"[{cid}] delay_risposta_sec: min > max")

        esc = voce.get("escalation") or {}

        istanza = wa.get("instance")
        if istanza:
            chiave_istanza = f"instance:{istanza.lower()}"
            if chiave_istanza in numeri_visti and numeri_visti[chiave_istanza] != cid:
                raise ConfigError(
                    f"istanza Evolution '{istanza}' assegnata sia a "
                    f"'{numeri_visti[chiave_istanza]}' che a '{cid}'"
                )
            numeri_visti[chiave_istanza] = cid

        # Un numero deve identificare UN solo cliente: se due tenant condividono un numero,
        # il sistema risponderebbe a un cliente con la conoscenza di un altro.
        for numero in (wa.get("phone_id"), vocale.get("numero")):
            if not numero:
                continue
            chiave = normalizza_numero(numero)
            if chiave in numeri_visti and numeri_visti[chiave] != cid:
                raise ConfigError(
                    f"numero '{numero}' assegnato sia a '{numeri_visti[chiave]}' che a '{cid}'"
                )
            numeri_visti[chiave] = cid

        clienti[cid] = Cliente(
            client_id=cid,
            nome=voce.get("nome", cid),
            attivo=bool(voce.get("attivo", False)),
            vault_path=voce.get("vault_path", f"vault/clienti/{cid}"),
            calendario=_parse_calendario(voce.get("calendario") or {}, cid),
            escalation=Escalation(
                soglia_confidenza=float(esc.get("soglia_confidenza", 0.6)),
                whatsapp=esc.get("whatsapp"),
                slack_channel=esc.get("slack_channel"),
                email=esc.get("email"),
            ),
            provider_whatsapp=provider,
            phone_id=wa.get("phone_id"),
            instance=wa.get("instance"),
            delay_risposta_sec=(delay_min, delay_max),
            conferma_esplicita=bool(voce.get("conferma_esplicita", True)),
            numero_voce=vocale.get("numero"),
            elevenlabs_agent_id=vocale.get("elevenlabs_agent_id"),
        )
    return clienti


def normalizza_numero(numero: str) -> str:
    """'+39 333 111 22 33', '393331112233@c.us' -> '393331112233'.

    Evolution, 360dialog e Twilio formattano i numeri in modo diverso: la risoluzione del
    tenant non puo' dipendere da come li scrive il provider di turno.
    """
    solo_cifre = re.sub(r"\D", "", numero.split("@")[0])
    return solo_cifre.lstrip("0")


def risolvi_da_numero(clienti: dict[str, Cliente], chiave: str) -> Cliente | None:
    """Chiave in arrivo -> cliente. None se nessuno corrisponde: in quel caso NON si risponde.

    La chiave puo' essere un numero (Twilio, 360dialog) OPPURE il nome dell'istanza Evolution:
    nel payload di Evolution il numero su cui e' arrivato il messaggio spesso NON c'e', c'e'
    solo l'istanza. Se qui accettassimo solo numeri, il bot resterebbe muto su ogni cliente
    Evolution e nessuno capirebbe il perche'.
    """
    chiave = (chiave or "").strip()
    if not chiave:
        return None

    # 1. per nome istanza (Evolution)
    for c in clienti.values():
        if c.instance and c.instance.lower() == chiave.lower():
            return c

    # 2. per numero (Twilio, 360dialog, o Evolution quando il numero c'e')
    numero = normalizza_numero(chiave)
    if not numero:
        return None
    for c in clienti.values():
        for suo in (c.phone_id, c.numero_voce):
            if suo and normalizza_numero(suo) == numero:
                return c
    return None


def adesso(tz: ZoneInfo) -> datetime:
    """Ora corrente nel fuso del cliente. Isolata qui per poterla sostituire nei test."""
    return datetime.now(tz)
