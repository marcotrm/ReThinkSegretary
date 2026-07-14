"""Persistenza delle prenotazioni.

`Storage` è l'interfaccia. Due implementazioni:

- `InMemoryStorage` — per i test e lo sviluppo locale. NON usare in produzione: i dati
  spariscono al riavvio.
- `PostgresStorage` — per Railway. Stessa interfaccia, quindi passare dall'una all'altra
  è una variabile d'ambiente (DATABASE_URL), non una riscrittura.

Le prenotazioni sono salvate in UTC. La conversione da/verso il fuso del cliente avviene
al confine (API), mai qui.
"""

from __future__ import annotations

import os
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class ConflittoPrenotazione(Exception):
    """Lo slot non è più libero (capienza esaurita)."""


class PrenotazioneNonTrovata(Exception):
    pass


@dataclass(frozen=True)
class Prenotazione:
    id: str
    client_id: str
    servizio: str
    nome_cliente: str
    telefono: str
    inizio: datetime  # sempre timezone-aware
    durata_min: int
    note: str | None = None
    stato: str = "confermata"  # confermata | cancellata

    @property
    def fine(self) -> datetime:
        return self.inizio + timedelta(minutes=self.durata_min)

    def si_sovrappone(self, inizio: datetime, fine: datetime) -> bool:
        return self.inizio < fine and inizio < self.fine

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "servizio": self.servizio,
            "nome_cliente": self.nome_cliente,
            "telefono": self.telefono,
            "inizio": self.inizio.isoformat(),
            "fine": self.fine.isoformat(),
            "durata_min": self.durata_min,
            "note": self.note,
            "stato": self.stato,
        }


@dataclass(frozen=True)
class Conversazione:
    """Memoria di una chat. Vive in Postgres, non nella memoria di n8n: una prenotazione
    dura piu' messaggi e non deve morire al riavvio del workflow."""

    client_id: str
    telefono: str
    stato: dict  # dove siamo nel flusso + slot proposti in attesa di conferma
    bot_in_pausa: bool = False
    motivo_pausa: str | None = None

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "telefono": self.telefono,
            "stato": self.stato,
            "bot_in_pausa": self.bot_in_pausa,
            "motivo_pausa": self.motivo_pausa,
        }


class Storage(ABC):
    # --- conversazioni ed eventi ---------------------------------------------

    @abstractmethod
    def leggi_conversazione(self, client_id: str, telefono: str) -> Conversazione: ...

    @abstractmethod
    def salva_conversazione(self, c: Conversazione) -> Conversazione: ...

    @abstractmethod
    def registra_evento(self, client_id: str, tipo: str, telefono: str | None, dati: dict) -> dict: ...

    @abstractmethod
    def elenca_eventi(self, client_id: str, limite: int = 100) -> list[dict]: ...

    # --- prenotazioni ---------------------------------------------------------

    @abstractmethod
    def elenca(
        self,
        client_id: str,
        da: datetime | None = None,
        a: datetime | None = None,
        includi_cancellate: bool = False,
    ) -> list[Prenotazione]: ...

    @abstractmethod
    def leggi(self, client_id: str, prenotazione_id: str) -> Prenotazione: ...

    @abstractmethod
    def crea(self, p: Prenotazione, capienza: int) -> Prenotazione:
        """Crea la prenotazione solo se lo slot ha ancora posto.

        Il controllo di capienza e l'inserimento devono essere ATOMICI: due richieste
        simultanee per l'ultimo posto non devono passare entrambe.
        """

    @abstractmethod
    def sposta(self, client_id: str, prenotazione_id: str, nuovo_inizio: datetime, capienza: int) -> Prenotazione: ...

    @abstractmethod
    def cancella(self, client_id: str, prenotazione_id: str) -> Prenotazione: ...


def _posti_occupati(prenotazioni: list[Prenotazione], inizio: datetime, fine: datetime, escludi: str | None = None) -> int:
    return sum(
        1
        for p in prenotazioni
        if p.stato == "confermata" and p.id != escludi and p.si_sovrappone(inizio, fine)
    )


class InMemoryStorage(Storage):
    """Implementazione di sviluppo/test. Thread-safe, ma volatile."""

    def __init__(self) -> None:
        self._dati: dict[str, dict[str, Prenotazione]] = {}
        self._conversazioni: dict[tuple[str, str], Conversazione] = {}
        self._eventi: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def _tenant(self, client_id: str) -> dict[str, Prenotazione]:
        return self._dati.setdefault(client_id, {})

    def leggi_conversazione(self, client_id, telefono):
        with self._lock:
            return self._conversazioni.get(
                (client_id, telefono), Conversazione(client_id, telefono, stato={})
            )

    def salva_conversazione(self, c):
        with self._lock:
            self._conversazioni[(c.client_id, c.telefono)] = c
        return c

    def registra_evento(self, client_id, tipo, telefono, dati):
        evento = {
            "client_id": client_id,
            "tipo": tipo,
            "telefono": telefono,
            "dati": dati,
            "ts": ora_utc().isoformat(),
        }
        with self._lock:
            self._eventi.setdefault(client_id, []).append(evento)
        return evento

    def elenca_eventi(self, client_id, limite=100):
        with self._lock:
            return list(reversed(self._eventi.get(client_id, [])))[:limite]

    def elenca(self, client_id, da=None, a=None, includi_cancellate=False):
        with self._lock:
            out = [
                p
                for p in self._tenant(client_id).values()
                if (includi_cancellate or p.stato == "confermata")
                and (da is None or p.fine > da)
                and (a is None or p.inizio < a)
            ]
        return sorted(out, key=lambda p: p.inizio)

    def leggi(self, client_id, prenotazione_id):
        with self._lock:
            p = self._tenant(client_id).get(prenotazione_id)
        if p is None:
            raise PrenotazioneNonTrovata(prenotazione_id)
        return p

    def crea(self, p, capienza):
        with self._lock:
            esistenti = list(self._tenant(p.client_id).values())
            if _posti_occupati(esistenti, p.inizio, p.fine) >= capienza:
                raise ConflittoPrenotazione(p.inizio.isoformat())
            self._tenant(p.client_id)[p.id] = p
        return p

    def sposta(self, client_id, prenotazione_id, nuovo_inizio, capienza):
        with self._lock:
            tenant = self._tenant(client_id)
            p = tenant.get(prenotazione_id)
            if p is None or p.stato != "confermata":
                raise PrenotazioneNonTrovata(prenotazione_id)
            nuova = Prenotazione(**{**p.__dict__, "inizio": nuovo_inizio})
            altri = list(tenant.values())
            if _posti_occupati(altri, nuova.inizio, nuova.fine, escludi=p.id) >= capienza:
                raise ConflittoPrenotazione(nuovo_inizio.isoformat())
            tenant[p.id] = nuova
        return nuova

    def cancella(self, client_id, prenotazione_id):
        with self._lock:
            tenant = self._tenant(client_id)
            p = tenant.get(prenotazione_id)
            if p is None:
                raise PrenotazioneNonTrovata(prenotazione_id)
            cancellata = Prenotazione(**{**p.__dict__, "stato": "cancellata"})
            tenant[p.id] = cancellata
        return cancellata


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prenotazioni (
    id            TEXT PRIMARY KEY,
    client_id     TEXT NOT NULL,
    servizio      TEXT NOT NULL,
    nome_cliente  TEXT NOT NULL,
    telefono      TEXT NOT NULL,
    inizio        TIMESTAMPTZ NOT NULL,
    durata_min    INTEGER NOT NULL,
    note          TEXT,
    stato         TEXT NOT NULL DEFAULT 'confermata',
    creata_il     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prenotazioni_tenant_inizio
    ON prenotazioni (client_id, inizio) WHERE stato = 'confermata';

CREATE TABLE IF NOT EXISTS conversazioni (
    client_id     TEXT NOT NULL,
    telefono      TEXT NOT NULL,
    stato         JSONB NOT NULL DEFAULT '{}'::jsonb,
    bot_in_pausa  BOOLEAN NOT NULL DEFAULT false,
    motivo_pausa  TEXT,
    aggiornata_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (client_id, telefono)
);

-- Log strutturato: ogni messaggio, escalation, prenotazione. E' la base del report
-- settimanale al cliente e l'unico modo per capire cosa e' successo quando qualcosa va storto.
CREATE TABLE IF NOT EXISTS eventi (
    id         BIGSERIAL PRIMARY KEY,
    client_id  TEXT NOT NULL,
    tipo       TEXT NOT NULL,
    telefono   TEXT,
    dati       JSONB NOT NULL DEFAULT '{}'::jsonb,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eventi_tenant_ts ON eventi (client_id, ts DESC);
"""


class PostgresStorage(Storage):
    """Produzione (Railway). Richiede psycopg[binary]."""

    def __init__(self, dsn: str) -> None:
        import psycopg  # import locale: i test non devono richiedere psycopg
        from psycopg_pool import ConnectionPool

        self._psycopg = psycopg
        self._pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True)
        with self._pool.connection() as conn:
            conn.execute(SCHEMA_SQL)

    def leggi_conversazione(self, client_id, telefono):
        with self._pool.connection() as conn:
            r = conn.execute(
                """SELECT stato, bot_in_pausa, motivo_pausa FROM conversazioni
                   WHERE client_id = %s AND telefono = %s""",
                (client_id, telefono),
            ).fetchone()
        if r is None:
            return Conversazione(client_id, telefono, stato={})
        return Conversazione(
            client_id=client_id, telefono=telefono,
            stato=r[0] or {}, bot_in_pausa=r[1], motivo_pausa=r[2],
        )

    def salva_conversazione(self, c):
        from psycopg.types.json import Jsonb

        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO conversazioni (client_id, telefono, stato, bot_in_pausa, motivo_pausa)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (client_id, telefono) DO UPDATE
                   SET stato = EXCLUDED.stato,
                       bot_in_pausa = EXCLUDED.bot_in_pausa,
                       motivo_pausa = EXCLUDED.motivo_pausa,
                       aggiornata_il = now()""",
                (c.client_id, c.telefono, Jsonb(c.stato), c.bot_in_pausa, c.motivo_pausa),
            )
        return c

    def registra_evento(self, client_id, tipo, telefono, dati):
        from psycopg.types.json import Jsonb

        with self._pool.connection() as conn:
            r = conn.execute(
                """INSERT INTO eventi (client_id, tipo, telefono, dati)
                   VALUES (%s, %s, %s, %s) RETURNING ts""",
                (client_id, tipo, telefono, Jsonb(dati)),
            ).fetchone()
        return {
            "client_id": client_id, "tipo": tipo, "telefono": telefono,
            "dati": dati, "ts": r[0].isoformat(),
        }

    def elenca_eventi(self, client_id, limite=100):
        with self._pool.connection() as conn:
            righe = conn.execute(
                """SELECT tipo, telefono, dati, ts FROM eventi
                   WHERE client_id = %s ORDER BY ts DESC LIMIT %s""",
                (client_id, limite),
            ).fetchall()
        return [
            {"client_id": client_id, "tipo": r[0], "telefono": r[1],
             "dati": r[2], "ts": r[3].isoformat()}
            for r in righe
        ]

    @staticmethod
    def _riga_to_prenotazione(r) -> Prenotazione:
        return Prenotazione(
            id=r[0], client_id=r[1], servizio=r[2], nome_cliente=r[3], telefono=r[4],
            inizio=r[5], durata_min=r[6], note=r[7], stato=r[8],
        )

    _CAMPI = "id, client_id, servizio, nome_cliente, telefono, inizio, durata_min, note, stato"

    def elenca(self, client_id, da=None, a=None, includi_cancellate=False):
        sql = f"SELECT {self._CAMPI} FROM prenotazioni WHERE client_id = %s"
        params: list = [client_id]
        if not includi_cancellate:
            sql += " AND stato = 'confermata'"
        if da is not None:
            sql += " AND inizio + (durata_min * INTERVAL '1 minute') > %s"
            params.append(da)
        if a is not None:
            sql += " AND inizio < %s"
            params.append(a)
        sql += " ORDER BY inizio"
        with self._pool.connection() as conn:
            righe = conn.execute(sql, params).fetchall()
        return [self._riga_to_prenotazione(r) for r in righe]

    def leggi(self, client_id, prenotazione_id):
        with self._pool.connection() as conn:
            r = conn.execute(
                f"SELECT {self._CAMPI} FROM prenotazioni WHERE client_id = %s AND id = %s",
                (client_id, prenotazione_id),
            ).fetchone()
        if r is None:
            raise PrenotazioneNonTrovata(prenotazione_id)
        return self._riga_to_prenotazione(r)

    def _lock_tenant(self, conn, client_id: str) -> None:
        # Advisory lock sul tenant: serializza i controlli di capienza senza bloccare gli
        # altri clienti. Rilasciato a fine transazione.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (client_id,))

    def _occupati(self, conn, client_id, inizio, fine, escludi=None) -> int:
        sql = """
            SELECT count(*) FROM prenotazioni
            WHERE client_id = %s AND stato = 'confermata'
              AND inizio < %s
              AND inizio + (durata_min * INTERVAL '1 minute') > %s
        """
        params: list = [client_id, fine, inizio]
        if escludi:
            sql += " AND id <> %s"
            params.append(escludi)
        return conn.execute(sql, params).fetchone()[0]

    def crea(self, p, capienza):
        with self._pool.connection() as conn:
            with conn.transaction():
                self._lock_tenant(conn, p.client_id)
                if self._occupati(conn, p.client_id, p.inizio, p.fine) >= capienza:
                    raise ConflittoPrenotazione(p.inizio.isoformat())
                conn.execute(
                    """INSERT INTO prenotazioni
                       (id, client_id, servizio, nome_cliente, telefono, inizio, durata_min, note, stato)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (p.id, p.client_id, p.servizio, p.nome_cliente, p.telefono,
                     p.inizio, p.durata_min, p.note, p.stato),
                )
        return p

    def sposta(self, client_id, prenotazione_id, nuovo_inizio, capienza):
        with self._pool.connection() as conn:
            with conn.transaction():
                self._lock_tenant(conn, client_id)
                r = conn.execute(
                    f"SELECT {self._CAMPI} FROM prenotazioni WHERE client_id = %s AND id = %s",
                    (client_id, prenotazione_id),
                ).fetchone()
                if r is None or r[8] != "confermata":
                    raise PrenotazioneNonTrovata(prenotazione_id)
                p = self._riga_to_prenotazione(r)
                nuova = Prenotazione(**{**p.__dict__, "inizio": nuovo_inizio})
                if self._occupati(conn, client_id, nuova.inizio, nuova.fine, escludi=p.id) >= capienza:
                    raise ConflittoPrenotazione(nuovo_inizio.isoformat())
                conn.execute(
                    "UPDATE prenotazioni SET inizio = %s WHERE id = %s", (nuovo_inizio, p.id)
                )
        return nuova

    def cancella(self, client_id, prenotazione_id):
        with self._pool.connection() as conn:
            r = conn.execute(
                """UPDATE prenotazioni SET stato = 'cancellata'
                   WHERE client_id = %s AND id = %s
                   RETURNING id, client_id, servizio, nome_cliente, telefono, inizio,
                             durata_min, note, stato""",
                (client_id, prenotazione_id),
            ).fetchone()
        if r is None:
            raise PrenotazioneNonTrovata(prenotazione_id)
        return self._riga_to_prenotazione(r)


def nuova_prenotazione_id() -> str:
    return uuid.uuid4().hex[:12]


def crea_storage() -> Storage:
    """Sceglie l'implementazione in base all'ambiente. Railway imposta DATABASE_URL."""
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return PostgresStorage(dsn)
    return InMemoryStorage()


def ora_utc() -> datetime:
    return datetime.now(timezone.utc)
