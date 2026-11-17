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
TIPI = ["chat", "gemini-immagine", "imagen", "veo"]

# I nomi dei modelli possono cambiare nel tempo: si correggono dal pannello.
MODELLI_PREDEFINITI = [
    {"id": "gemini-2.5-flash", "nome": "Gemini 2.5 Flash", "tipo": "chat", "regione": ""},
    {"id": "gemini-2.5-pro", "nome": "Gemini 2.5 Pro", "tipo": "chat", "regione": ""},
    {"id": "gemini-4-carbon", "nome": "Gemini 4 Carbon", "tipo": "chat", "regione": "global"},
    {"id": "gemini-2.5-flash-image", "nome": "Nano Banana", "tipo": "gemini-immagine", "regione": ""},
    {"id": "gemini-3-pro-image-preview", "nome": "Nano Banana Pro", "tipo": "gemini-immagine", "regione": "global"},
    {"id": "imagen-4.0-generate-001", "nome": "Imagen 4", "tipo": "imagen", "regione": ""},
    {"id": "imagen-4.0-ultra-generate-001", "nome": "Imagen 4 Ultra", "tipo": "imagen", "regione": ""},
    {"id": "veo-3.0-generate-001", "nome": "Veo 3", "tipo": "veo", "regione": ""},
    {"id": "veo-3.0-fast-generate-001", "nome": "Veo 3 Fast", "tipo": "veo", "regione": ""},
]

_lock = threading.Lock()


def _predefinite() -> dict:
    return {
        "profili": [],
        "profilo_attivo": None,
        "modelli": [dict(m) for m in MODELLI_PREDEFINITI],
        "istruzioni_sistema": "",
    }


def leggi() -> dict:
    with _lock:
        if not FILE.exists():
            return _predefinite()
        try:
            dati = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _predefinite()
    base = _predefinite()
    base.update({k: v for k, v in dati.items() if k in base})
    return base


def salva(dati: dict) -> dict:
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
    }


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
    if modello_cfg["tipo"] in ("chat", "gemini-immagine"):
        return profilo["regione_gemini"]
    return profilo["regione"]
