"""Calcolo della disponibilità.

Regola di fondo: uno slot è proponibile solo se **tutte** queste condizioni valgono.
Se una manca, lo slot non esiste — la segretaria AI non deve mai proporre un orario che
poi la prenotazione rifiuta.

1. Il giorno è aperto (orari.md) e non è una chiusura straordinaria.
2. L'appuntamento (durata + buffer) sta interamente dentro una fascia di apertura.
3. Rispetta anticipo_min_ore e anticipo_max_giorni.
4. I posti occupati in sovrapposizione sono < capienza_per_slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from config_loader import ConfigCalendario
from storage import Prenotazione


@dataclass(frozen=True)
class Slot:
    inizio: datetime
    fine: datetime
    posti_liberi: int

    def to_dict(self) -> dict:
        return {
            "inizio": self.inizio.isoformat(),
            "fine": self.fine.isoformat(),
            "posti_liberi": self.posti_liberi,
        }


def _occupati(prenotazioni: list[Prenotazione], inizio: datetime, fine: datetime) -> int:
    return sum(1 for p in prenotazioni if p.stato == "confermata" and p.si_sovrappone(inizio, fine))


def slot_prenotabile(
    inizio: datetime,
    durata_min: int,
    cfg: ConfigCalendario,
    prenotazioni: list[Prenotazione],
    adesso: datetime,
) -> tuple[bool, str | None]:
    """Verifica un singolo orario. Restituisce (ok, motivo_del_rifiuto).

    Usata sia da `disponibilita` sia da `prenota`: così l'endpoint di prenotazione applica
    esattamente le stesse regole che hanno generato le proposte.
    """
    inizio = inizio.astimezone(cfg.timezone)
    fine = inizio + timedelta(minutes=durata_min)
    fine_con_buffer = fine + timedelta(minutes=cfg.buffer_min)

    if inizio < adesso + timedelta(hours=cfg.anticipo_min_ore):
        return False, f"serve almeno {cfg.anticipo_min_ore}h di anticipo"

    if inizio.date() > (adesso + timedelta(days=cfg.anticipo_max_giorni)).date():
        return False, f"non si prenota oltre {cfg.anticipo_max_giorni} giorni"

    fasce = cfg.intervalli_del_giorno(inizio.date())
    if not fasce:
        return False, "giorno di chiusura"

    dentro_una_fascia = any(
        inizio.time() >= apre and fine_con_buffer.time() <= chiude
        # l'appuntamento non può scavalcare la mezzanotte né uscire dalla fascia
        and fine_con_buffer.date() == inizio.date()
        for apre, chiude in fasce
    )
    if not dentro_una_fascia:
        return False, "fuori dagli orari di apertura"

    if _occupati(prenotazioni, inizio, fine) >= cfg.capienza_per_slot:
        return False, "orario già occupato"

    return True, None


def disponibilita(
    cfg: ConfigCalendario,
    prenotazioni: list[Prenotazione],
    da: date,
    a: date,
    durata_min: int,
    adesso: datetime,
    limite: int | None = None,
) -> list[Slot]:
    """Tutti gli slot liberi tra `da` e `a` (estremi inclusi), in ordine cronologico."""
    slot: list[Slot] = []
    giorno = da
    passo = timedelta(minutes=cfg.durata_slot_min)

    while giorno <= a:
        for apre, chiude in cfg.intervalli_del_giorno(giorno):
            cursore = datetime.combine(giorno, apre, tzinfo=cfg.timezone)
            limite_fascia = datetime.combine(giorno, chiude, tzinfo=cfg.timezone)
            while cursore + timedelta(minutes=durata_min + cfg.buffer_min) <= limite_fascia:
                ok, _ = slot_prenotabile(cursore, durata_min, cfg, prenotazioni, adesso)
                if ok:
                    occupati = _occupati(
                        prenotazioni, cursore, cursore + timedelta(minutes=durata_min)
                    )
                    slot.append(
                        Slot(
                            inizio=cursore,
                            fine=cursore + timedelta(minutes=durata_min),
                            posti_liberi=cfg.capienza_per_slot - occupati,
                        )
                    )
                    if limite and len(slot) >= limite:
                        return slot
                cursore += passo
        giorno += timedelta(days=1)

    return slot
