"""Archivio locale delle conversazioni.

Ogni conversazione è una cartella dentro ~/VertexStudio/conversazioni/:
    info.json        titolo e date
    messaggi.jsonl   un messaggio per riga
    media/           immagini, video e allegati
Le conversazioni eliminate finiscono in ~/VertexStudio/cestino/.
"""

import json
import mimetypes
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .impostazioni import CARTELLA_DATI

RADICE = CARTELLA_DATI / "conversazioni"
CESTINO = CARTELLA_DATI / "cestino"
_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]+$")
_NOME_VALIDO = re.compile(r"^[A-Za-z0-9_.-]+$")
_lock = threading.Lock()


def adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def cartella(conv_id: str) -> Path:
    if not _ID_VALIDO.match(conv_id or ""):
        raise ValueError("ID conversazione non valido")
    p = RADICE / conv_id
    if not p.is_dir():
        raise FileNotFoundError("Conversazione non trovata")
    return p


def _leggi_info(p: Path) -> dict:
    return json.loads((p / "info.json").read_text(encoding="utf-8"))


def _scrivi_info(p: Path, info: dict):
    (p / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def elenco() -> list[dict]:
    if not RADICE.exists():
        return []
    risultato = []
    for p in RADICE.iterdir():
        if (p / "info.json").exists():
            try:
                risultato.append(_leggi_info(p))
            except (OSError, json.JSONDecodeError):
                continue
    return sorted(risultato, key=lambda i: i.get("aggiornata", ""), reverse=True)


def crea() -> dict:
    conv_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    p = RADICE / conv_id
    (p / "media").mkdir(parents=True)
    info = {"id": conv_id, "titolo": "Nuova conversazione", "creata": adesso(), "aggiornata": adesso()}
    _scrivi_info(p, info)
    (p / "messaggi.jsonl").touch()
    return info


def leggi(conv_id: str) -> dict:
    p = cartella(conv_id)
    messaggi = []
    for riga in (p / "messaggi.jsonl").read_text(encoding="utf-8").splitlines():
        if riga.strip():
            messaggi.append(json.loads(riga))
    return {"info": _leggi_info(p), "messaggi": messaggi}


def aggiungi(conv_id: str, messaggio: dict) -> dict:
    with _lock:
        p = cartella(conv_id)
        messaggio = {"id": uuid.uuid4().hex[:10], "creato": adesso(), **messaggio}
        with (p / "messaggi.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(messaggio, ensure_ascii=False) + "\n")
        info = _leggi_info(p)
        info["aggiornata"] = adesso()
        if info["titolo"] == "Nuova conversazione" and messaggio.get("ruolo") == "utente" and messaggio.get("testo"):
            t = " ".join(messaggio["testo"].split())
            info["titolo"] = t[:60] + ("…" if len(t) > 60 else "")
        _scrivi_info(p, info)
    return messaggio


def rinomina(conv_id: str, titolo: str) -> dict:
    with _lock:
        p = cartella(conv_id)
        info = _leggi_info(p)
        info["titolo"] = (titolo or "").strip()[:120] or info["titolo"]
        _scrivi_info(p, info)
    return info


def nel_cestino(conv_id: str):
    with _lock:
        p = cartella(conv_id)
        CESTINO.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(CESTINO / conv_id))


def salva_file(conv_id: str, dati: bytes, mime: str, prefisso: str) -> dict:
    p = cartella(conv_id) / "media"
    p.mkdir(exist_ok=True)
    est = mimetypes.guess_extension(mime or "") or ".bin"
    if est == ".jpe":
        est = ".jpg"
    nome = f"{datetime.now():%Y%m%d-%H%M%S}-{prefisso}-{uuid.uuid4().hex[:6]}{est}"
    (p / nome).write_bytes(dati)
    return {"nome": nome, "mime": mime or "application/octet-stream"}


def percorso_file(conv_id: str, nome: str) -> Path:
    if not _NOME_VALIDO.match(nome or "") or ".." in nome:
        raise ValueError("Nome file non valido")
    f = cartella(conv_id) / "media" / nome
    if not f.is_file():
        raise FileNotFoundError(nome)
    return f
