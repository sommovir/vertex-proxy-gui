"""API locali (solo 127.0.0.1) e pagina dell'interfaccia."""

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import account, archivio, generazione, impostazioni, modelli, vertex

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Vertex Studio", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _404(fn, *a):
    try:
        return fn(*a)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e)) from e


@app.get("/")
def pagina():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- impostazioni

@app.get("/api/impostazioni")
def leggi_impostazioni():
    return {**impostazioni.leggi(), "tipi": impostazioni.TIPI,
            "predefiniti": impostazioni.MODELLI_PREDEFINITI,
            "cartella_dati": str(impostazioni.CARTELLA_DATI)}


@app.put("/api/impostazioni")
def salva_impostazioni(dati: dict):
    try:
        salvate = impostazioni.salva(dati)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    vertex.azzera()
    return salvate


@app.post("/api/modelli/verifica")
def verifica_modelli(corpo: dict):
    try:
        return modelli.verifica(corpo.get("modelli") or [])
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/modelli/disponibili")
def modelli_disponibili():
    try:
        return modelli.disponibili()
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/stato")
def stato():
    profilo = impostazioni.profilo_attivo()
    if not profilo:
        senza = vertex.verifica({"progetto": "", "service_account": ""})
        return {"ok": False, "account": senza.get("account", ""), "profilo": None,
                "messaggio": "Nessun profilo: apri le Impostazioni e aggiungine uno."}
    return {**vertex.verifica(profilo), "profilo": profilo["nome"]}


# ---------------------------------------------------------------- account Google

@app.post("/api/login")
def login():
    return account.avvia_login()


@app.get("/api/login")
def stato_login():
    return account.stato_login()


@app.post("/api/logout")
def logout():
    return account.logout()


# ---------------------------------------------------------------- conversazioni

@app.get("/api/conversazioni")
def elenco():
    return archivio.elenco()


@app.post("/api/conversazioni")
def nuova():
    return archivio.crea()


@app.get("/api/conversazioni/{conv_id}")
def leggi(conv_id: str):
    return _404(archivio.leggi, conv_id)


class Rinomina(BaseModel):
    titolo: str


@app.patch("/api/conversazioni/{conv_id}")
def rinomina(conv_id: str, corpo: Rinomina):
    return _404(archivio.rinomina, conv_id, corpo.titolo)


@app.delete("/api/conversazioni/{conv_id}")
def elimina(conv_id: str):
    _404(archivio.nel_cestino, conv_id)
    return {"ok": True}


@app.post("/api/conversazioni/{conv_id}/messaggi")
async def invia(conv_id: str, modello: str = Form(...), testo: str = Form(""),
                opzioni: str = Form("{}"), allegati: list[UploadFile] = File(default=[])):
    _404(archivio.cartella, conv_id)
    file = []
    for a in allegati:
        dati = await a.read()
        if dati:
            file.append(archivio.salva_file(conv_id, dati, a.content_type or "application/octet-stream", "allegato"))
    testo = testo.strip()
    if not testo and not file:
        raise HTTPException(400, "Messaggio vuoto")
    m = impostazioni.modello(modello)
    msg = archivio.aggiungi(conv_id, {"ruolo": "utente", "testo": testo, "file": file,
                                      "modello": modello, "tipo": m["tipo"] if m else ""})
    try:
        opz = json.loads(opzioni or "{}")
    except json.JSONDecodeError:
        opz = {}
    job = generazione.avvia(conv_id, modello, testo, file, opz)
    return {"job": job, "messaggio": msg}


@app.get("/api/job/{job_id}")
def job(job_id: str):
    s = generazione.stato(job_id)
    if not s:
        raise HTTPException(404, "Job non trovato (l'app è stata riavviata?)")
    return s


@app.get("/media/{conv_id}/{nome}")
def media(conv_id: str, nome: str):
    return FileResponse(_404(archivio.percorso_file, conv_id, nome))


@app.post("/api/apri-cartella")
def apri_cartella(conv_id: str | None = None):
    p = _404(archivio.cartella, conv_id) / "media" if conv_id else impostazioni.CARTELLA_DATI
    p.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"ok": True}
