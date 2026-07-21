#!/usr/bin/env python3
"""Aggiorna l'agent ElevenLabs della voce Quisvapo in un colpo solo.

Carica dal vault il System Prompt aggiornato e imposta, via API ElevenLabs:
  - conversation_config.agent.prompt.prompt  -> il prompt del vault
  - conversation_config.asr.keywords         -> marchi svapo + termini prodotto (aiuta il riconoscimento)
  - conversation_config.turn.turn_timeout     -> risposta piu' pronta col rumore
  - conversation_config.turn.turn_eagerness   -> "eager"
  - conversation_config.vad.background_voice_detection -> ignora voci di sottofondo (TV, altre persone)

Uso:
  ELEVENLABS_API_KEY=sk_xxx python scripts/aggiorna_agent_voce.py
  (opzionale: --dry-run per vedere il payload senza inviare)
"""
import os
import re
import sys
import json
import urllib.request

AGENT_ID = "agent_2201ky21r7vqe329fd186nwmaees"
VAULT_PROMPT = os.path.join(
    os.path.dirname(__file__), "..", "vault", "clienti", "quisvapo", "prompt-agent-voce.md"
)

# Keyterms per l'ASR = parole che (a) il cliente dice al telefono e (b) la macchina sbaglia
# perche' straniere/inventate/nomi propri. NON parole italiane comuni (quelle le prende gia').
# Il tetto tecnico e' alto (>300) ma troppi diluiscono il biasing: si tiene una lista CURATA.
KEYWORDS = [
    # marchi (dal gestionale /marche, per numero prodotti)
    "VaporArt", "ToB", "Suprem-e", "Svaponext", "Aspire", "Kiwi", "Dea Flavor",
    "Flavourage", "Voopoo", "TNT Vape", "Vaporesso", "Geekvape", "FlavourArt",
    "La Tabaccheria", "ReloadVape", "Fantasi", "Iwik", "Airbar", "Elfbar", "Quisvapo",
    "Blendfeel", "Lost Vape", "Innokin", "Super Flavor", "King Liquid", "Seven Wonders",
    "Elfliq", "Eleaf", "Justfog", "Joyetech", "Oxva", "Vampire Vape", "Smok", "Five Pawns",
    "Da One", "Monster Vape Labs", "Vaptio", "Zeep", "PGVG Labs", "T-Juice", "Golisi",
    # monouso molto richiesti (spesso storpiati al telefono)
    "puff", "usa e getta", "Lost Mary", "Geekbar", "Crystal",
    # NB: NIENTE nomi di citta' nei keyterms. Collidono con parole prodotto italiane
    #     (es. "Maddaloni" veniva sentito al posto di "mandarino") e rovinano il
    #     riconoscimento dei prodotti, che e' la funzione principale. Le citta' le
    #     gestisce il modello con la geografia + lo strumento "negozi".
    # termini prodotto / gergo svapo
    "liquido", "aroma", "base", "nicotina", "pod", "resistenza", "atomizzatore",
    "batteria", "cartuccia", "sigaretta elettronica", "Fidelity Card",
]


def estrai_system_prompt(testo: str) -> str:
    """Prende tutto cio' che sta dopo la riga marcatore fino alla prossima sezione '## '."""
    m = re.search(r"## SYSTEM PROMPT.*?\n(.*?)(?:\n---\n)", testo, re.S)
    if not m:
        # fallback: dal marcatore 'incollare da qui in giu'' in poi
        m = re.search(r"incollare da qui in gi.*?\n+(.*?)(?:\n## MESSAGGIO)", testo, re.S)
    if not m:
        raise SystemExit("Non trovo la sezione SYSTEM PROMPT nel file vault.")
    return m.group(1).strip()


def main() -> None:
    dry = "--dry-run" in sys.argv
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key and not dry:
        raise SystemExit("Manca ELEVENLABS_API_KEY nell'ambiente.")

    with open(VAULT_PROMPT, encoding="utf-8") as f:
        prompt = estrai_system_prompt(f.read())

    payload = {
        "conversation_config": {
            "agent": {"prompt": {"prompt": prompt}},
            "asr": {"keywords": KEYWORDS},
            "turn": {"turn_timeout": 3, "turn_eagerness": "eager"},
            "vad": {"background_voice_detection": True},
            # Voce meno "sottovoce/triste". Il modello e' eleven_v3_conversational: la
            # malinconia veniva dai tag audio "Con empatia/Con eccitazione" applicati
            # SEMPRE. Li sostituiamo con un tono cordiale e sveglio, e abbassiamo un filo
            # la stability per renderla piu' viva. (voice_id/model_id restano invariati:
            # il PATCH fa merge.)
            "tts": {
                "stability": 0.4,
                "suggested_audio_tags": [
                    {"tag": "Con tono cordiale e sveglio", "description": "sempre"},
                    {"tag": "Ride", "description": "quando ride chi parla a telefono"},
                ],
            },
        }
    }

    print(f"[i] prompt: {len(prompt)} caratteri | keyterms: {len(KEYWORDS)}")
    if dry:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])
        return

    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/convai/agents/{AGENT_ID}",
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[OK] HTTP {resp.status} - agent aggiornato.")
    except urllib.error.HTTPError as e:
        print(f"[ERRORE] HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:500]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
