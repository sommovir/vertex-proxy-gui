"""Impostazioni locali: profili Google Cloud e modelli.

Vengono salvate in un file JSON nella cartella dati dell'utente
(di default ~/VertexStudio/impostazioni.json), MAI nel repository.
Non contengono segreti: solo ID progetto, email del service account e regioni.
"""

import json
import os
import threading
import uuid
from pathlib import Path

CARTELLA_DATI = Path(os.environ.get("VERTEX_STUDIO_DATI", "~/VertexStudio")).expanduser()
FILE = CARTELLA_DATI / "impostazioni.json"

# Tipi di modello gestiti:
#   chat             -> Gemini testo (accetta allegati)
#   gemini-immagine  -> Gemini che genera/modifica immagini (Nano Banana)
#   imagen           -> Imagen, testo -> immagine
#   veo              -> Veo, testo/immagine -> video
#   claude           -> Claude (Anthropic) su Vertex, chat con allegati
#   omni             -> Gemini Omni, video da testo/immagini/riferimenti e modifica di video
TIPI = ["chat", "claude", "gemini-immagine", "imagen", "veo", "omni"]

# Elenco aggiornato al 17/11/2026 (fonte: pagina «Model versions and lifecycle» di Vertex AI).
# I nomi cambiano nel tempo: si correggono o si aggiungono dal pannello Impostazioni → Modelli.
# Regione vuota = quella del profilo (global per Gemini, us-central1 per Veo).
MODELLI_PREDEFINITI = [
    {"id": "gemini-4-carbon", "nome": "Gemini 4 Carbon", "tipo": "chat", "regione": ""},
    {"id": "gemini-4-argon", "nome": "Gemini 4 Argon", "tipo": "chat", "regione": ""},
    {"id": "gemini-3.8-flash", "nome": "Gemini 3.8 Flash", "tipo": "chat", "regione": ""},
    {"id": "gemini-3.5-flash-lite", "nome": "Gemini 3.5 Flash Lite (economico)", "tipo": "chat", "regione": ""},
    {"id": "claude-opus-5-5", "nome": "Claude Opus 5.5", "tipo": "claude", "regione": ""},
    {"id": "claude-sonnet-5-5", "nome": "Claude Sonnet 5.5", "tipo": "claude", "regione": ""},
    {"id": "claude-haiku-5-5", "nome": "Claude Haiku 5.5 (economico)", "tipo": "claude", "regione": ""},
    {"id": "gemini-3.1-flash-image", "nome": "Nano Banana 2", "tipo": "gemini-immagine", "regione": ""},
    {"id": "gemini-3-pro-image", "nome": "Nano Banana Pro", "tipo": "gemini-immagine", "regione": ""},
    {"id": "gemini-nano-banana-2.1", "nome": "Nano Banana 2.1", "tipo": "gemini-immagine", "regione": ""},
    {"id": "gemini-3.1-flash-lite-image", "nome": "Nano Banana 2 Lite (economico)", "tipo": "gemini-immagine", "regione": ""},
    {"id": "gemini-omni-1.2-flash", "nome": "Gemini Omni 1.2 Flash", "tipo": "omni", "regione": "global"},
    {"id": "veo-3.1-generate-001", "nome": "Veo 3.1", "tipo": "veo", "regione": ""},
    {"id": "veo-3.1-fast-generate-001", "nome": "Veo 3.1 Fast", "tipo": "veo", "regione": ""},
]

# Ritirati da Google: tolti in automatico dalle impostazioni salvate.
MODELLI_RITIRATI = {
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite",
    "gemini-3-pro-preview", "gemini-3-pro-image-preview",
    "imagen-4.0-generate-001", "imagen-4.0-ultra-generate-001", "imagen-4.0-fast-generate-001",
    "imagen-3.0-generate-001", "imagen-3.0-generate-002",
    "veo-3.0-generate-001", "veo-3.0-fast-generate-001", "veo-2.0-generate-001",
}

# Da aumentare quando si aggiorna MODELLI_PREDEFINITI: le installazioni esistenti ricevono
# una volta sola i modelli nuovi (quelli aggiunti o tolti a mano restano come sono).
VERSIONE_MODELLI = 4

_lock = threading.Lock()


def _predefinite() -> dict:
    return {
        "profili": [],
        "profilo_attivo": None,
        "modelli": [dict(m) for m in MODELLI_PREDEFINITI],
        "istruzioni_sistema": "",
        "scelte": {},  # per modalità (chat/immagine/video): ultimo modello e formato usati
        "versione_modelli": VERSIONE_MODELLI,
        "gcloud_path": "",  # facoltativo: percorso di gcloud se non è nel PATH
    }


MODALITA = ("chat", "immagine", "video")


def leggi() -> dict:
    with _lock:
        if not FILE.exists():
            return _predefinite()
        try:
            dati = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _predefinite()
    base = _predefinite()
    base["versione_modelli"] = 1  # file vecchi senza versione
    base.update({k: v for k, v in dati.items() if k in base})
    if base["versione_modelli"] < VERSIONE_MODELLI:
        base = _aggiorna_modelli(base)
        try:
            salva(base)
        except (OSError, ValueError):
            pass
    return base


def _aggiorna_modelli(dati: dict) -> dict:
    modelli = [m for m in dati.get("modelli") or [] if m.get("id") not in MODELLI_RITIRATI]
    presenti = {m.get("id") for m in modelli}
    modelli += [dict(m) for m in MODELLI_PREDEFINITI if m["id"] not in presenti]
    return {**dati, "modelli": modelli, "versione_modelli": VERSIONE_MODELLI}


def salva(dati: dict) -> dict:
    # Le chiavi non inviate (es. le scelte, che il pannello non manda) restano quelle salvate.
    dati = {**leggi(), **dati}
    pulite = _valida(dati)
    with _lock:
        CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(pulite, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(FILE)
    return pulite


def _testo(v) -> str:
    return str(v or "").strip()


def normalizza_id(v) -> str:
    """Accetta anche l'ID copiato dalla console: publishers/google/models/x o google/x."""
    mid = _testo(v)
    for prefisso in ("publishers/google/models/", "google/"):
        if mid.startswith(prefisso):
            mid = mid[len(prefisso):]
    return mid


def _valida(dati: dict) -> dict:
    profili = []
    for p in dati.get("profili") or []:
        profilo = {
            "id": _testo(p.get("id")) or uuid.uuid4().hex[:8],
            "nome": _testo(p.get("nome")) or "Profilo",
            "progetto": _testo(p.get("progetto")),
            "service_account": _testo(p.get("service_account")),
            "regione": _testo(p.get("regione")) or "us-central1",
            "regione_gemini": _testo(p.get("regione_gemini")) or "global",
        }
        if not profilo["progetto"]:
            raise ValueError(f"Il profilo «{profilo['nome']}» non ha l'ID progetto.")
        profili.append(profilo)

    modelli = []
    for m in dati.get("modelli") or []:
        mid = normalizza_id(m.get("id"))
        if not mid:
            continue
        tipo = _testo(m.get("tipo"))
        if tipo not in TIPI:
            raise ValueError(f"Tipo non valido per il modello {mid}: {tipo}")
        modelli.append({"id": mid, "nome": _testo(m.get("nome")) or mid, "tipo": tipo,
                        "regione": _testo(m.get("regione"))})

    attivo = dati.get("profilo_attivo")
    ids = [p["id"] for p in profili]
    if attivo not in ids:
        attivo = ids[0] if ids else None

    return {
        "profili": profili,
        "profilo_attivo": attivo,
        "modelli": modelli or [dict(m) for m in MODELLI_PREDEFINITI],
        "istruzioni_sistema": _testo(dati.get("istruzioni_sistema")),
        "scelte": _valida_scelte(dati.get("scelte")),
        "versione_modelli": VERSIONE_MODELLI,
        "gcloud_path": _testo(dati.get("gcloud_path")),
    }


def _valida_scelte(scelte) -> dict:
    pulite = {}
    for m in MODALITA:
        voce = (scelte or {}).get(m) or {}
        pulite[m] = {k: _testo(voce.get(k)) for k in ("modello", "formato") if _testo(voce.get(k))}
    return pulite


def salva_scelta(modalita: str, valori: dict) -> dict:
    if modalita not in MODALITA:
        raise ValueError(f"Modalità non valida: {modalita}")
    dati = leggi()
    dati["scelte"].setdefault(modalita, {}).update(
        {k: _testo(v) for k, v in valori.items() if k in ("modello", "formato")})
    return salva(dati)["scelte"]


def profilo_attivo(dati: dict | None = None) -> dict | None:
    dati = dati or leggi()
    for p in dati["profili"]:
        if p["id"] == dati["profilo_attivo"]:
            return p
    return None


def modello(mid: str, dati: dict | None = None) -> dict | None:
    dati = dati or leggi()
    return next((m for m in dati["modelli"] if m["id"] == mid), None)


def regione_per(modello_cfg: dict, profilo: dict) -> str:
    if modello_cfg.get("regione"):
        return modello_cfg["regione"]
    if modello_cfg["tipo"] in ("chat", "claude", "gemini-immagine", "omni"):
        return profilo["regione_gemini"]
    return profilo["regione"]
