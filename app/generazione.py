"""Chiamate a Vertex AI per chat, immagini (Gemini/Imagen) e video (Veo).

Le generazioni girano in un thread: l'interfaccia riceve un job e ne
interroga lo stato finché il risultato non è salvato nell'archivio locale.
"""

import threading
import time
import traceback
import uuid

from google.genai import types

from . import archivio, claude, impostazioni, omni, vertex

MAX_MESSAGGI_CONTESTO = 20
MESSAGGI_CON_FILE = 6          # solo gli ultimi N messaggi rimandano i propri file
MAX_BYTE_FILE_CONTESTO = 15 * 1024 * 1024
TIMEOUT_VIDEO = 20 * 60

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------- job

def avvia(conv_id: str, modello_id: str, testo: str, allegati: list[dict], opzioni: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"stato": "in_corso", "conversazione": conv_id, "inizio": time.time()}
    threading.Thread(target=_esegui, args=(job_id, conv_id, modello_id, testo, allegati, opzioni),
                     daemon=True).start()
    return job_id


def stato(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _fine(job_id: str, **kw):
    with _lock:
        _jobs[job_id].update(kw)


def _esegui(job_id, conv_id, modello_id, testo, allegati, opzioni):
    try:
        imp = impostazioni.leggi()
        profilo = impostazioni.profilo_attivo(imp)
        if not profilo:
            raise RuntimeError("Nessun profilo configurato: aprilo dalle Impostazioni.")
        m = impostazioni.modello(modello_id, imp)
        if not m:
            raise RuntimeError(f"Modello sconosciuto: {modello_id}")
        regione = impostazioni.regione_per(m, profilo)

        if m["tipo"] == "claude":
            risposta = claude.genera(vertex.claude(profilo, regione), m, conv_id, imp["istruzioni_sistema"])
            msg = archivio.aggiungi(conv_id, {"ruolo": "modello", "modello": m["id"], **risposta})
            _fine(job_id, stato="fatto", messaggio=msg)
            return
        client = vertex.client(profilo, regione)

        if m["tipo"] == "chat":
            risposta = _chat(client, m, conv_id, imp["istruzioni_sistema"], immagini=False, opzioni=opzioni)
        elif m["tipo"] == "gemini-immagine":
            risposta = _chat(client, m, conv_id, imp["istruzioni_sistema"], immagini=True, opzioni=opzioni)
        elif m["tipo"] == "imagen":
            risposta = _imagen(client, m, conv_id, testo, opzioni)
        elif m["tipo"] == "omni":
            risposta = omni.genera(client, m, conv_id, testo, allegati, opzioni)
        else:
            risposta = _veo(client, m, conv_id, testo, allegati, opzioni)

        msg = archivio.aggiungi(conv_id, {"ruolo": "modello", "modello": m["id"], **risposta})
        _fine(job_id, stato="fatto", messaggio=msg)
    except Exception as e:  # noqa: BLE001 - l'errore va mostrato in chat
        traceback.print_exc()
        if vertex.errore_di_accesso(e):
            vertex.azzera()  # al prossimo tentativo rilegge il login
        testo_errore = vertex.spiega_errore(e)
        msg = archivio.aggiungi(conv_id, {"ruolo": "errore", "modello": modello_id, "testo": testo_errore})
        _fine(job_id, stato="errore", messaggio=msg)


# ---------------------------------------------------------------- contesto

def _contesto(conv_id: str, includi_media_modello: bool) -> list[types.Content]:
    messaggi = [m for m in archivio.leggi(conv_id)["messaggi"] if m["ruolo"] in ("utente", "modello")]
    messaggi = messaggi[-MAX_MESSAGGI_CONTESTO:]
    budget = MAX_BYTE_FILE_CONTESTO
    contenuti = []
    for i, m in enumerate(messaggi):
        parti = []
        recente = i >= len(messaggi) - MESSAGGI_CON_FILE
        if recente and (m["ruolo"] == "utente" or includi_media_modello):
            for f in m.get("file", []):
                if m["ruolo"] == "modello" and not f["mime"].startswith("image/"):
                    continue
                try:
                    dati = archivio.percorso_file(conv_id, f["nome"]).read_bytes()
                except (OSError, ValueError):
                    continue
                if len(dati) > budget:
                    continue
                budget -= len(dati)
                parti.append(types.Part.from_bytes(data=dati, mime_type=f["mime"]))
        if m.get("testo"):
            parti.append(types.Part.from_text(text=m["testo"]))
        if parti:
            contenuti.append(types.Content(role="user" if m["ruolo"] == "utente" else "model", parts=parti))
    return contenuti


# ---------------------------------------------------------------- generatori

def _chat(client, m, conv_id, istruzioni, immagini: bool, opzioni: dict) -> dict:
    config = {}
    if istruzioni:
        config["system_instruction"] = istruzioni
    if immagini:
        config["response_modalities"] = ["TEXT", "IMAGE"]
        if opzioni.get("formato"):
            config["image_config"] = types.ImageConfig(aspect_ratio=opzioni["formato"])
    risposta = client.models.generate_content(
        model=m["id"],
        contents=_contesto(conv_id, includi_media_modello=immagini),
        config=types.GenerateContentConfig(**config) if config else None,
    )
    testi, file = [], []
    for cand in (risposta.candidates or [])[:1]:
        for parte in (cand.content.parts if cand.content else None) or []:
            if getattr(parte, "thought", False):
                continue
            if parte.text:
                testi.append(parte.text)
            elif parte.inline_data and parte.inline_data.data:
                file.append(archivio.salva_file(conv_id, parte.inline_data.data,
                                                parte.inline_data.mime_type or "image/png", "immagine"))
    if not testi and not file:
        motivo = ""
        if risposta.candidates and risposta.candidates[0].finish_reason:
            motivo = f" (motivo: {risposta.candidates[0].finish_reason})"
        elif getattr(risposta, "prompt_feedback", None):
            motivo = f" ({risposta.prompt_feedback})"
        raise RuntimeError("Il modello non ha restituito niente" + motivo)
    return {"testo": "\n\n".join(testi), "file": file}


def _imagen(client, m, conv_id, testo, opzioni) -> dict:
    if not testo:
        raise RuntimeError("Scrivi una descrizione dell'immagine.")
    risposta = client.models.generate_images(
        model=m["id"],
        prompt=testo,
        config=types.GenerateImagesConfig(
            number_of_images=int(opzioni.get("numero") or 1),
            aspect_ratio=opzioni.get("formato") or "1:1",
        ),
    )
    file = [archivio.salva_file(conv_id, g.image.image_bytes, g.image.mime_type or "image/png", "immagine")
            for g in (risposta.generated_images or []) if g.image and g.image.image_bytes]
    if not file:
        raise RuntimeError("Nessuna immagine generata (probabilmente bloccata dai filtri di sicurezza).")
    return {"testo": "", "file": file}


def _immagine(conv_id: str, f: dict) -> types.Image:
    return types.Image(image_bytes=archivio.percorso_file(conv_id, f["nome"]).read_bytes(), mime_type=f["mime"])


def _veo(client, m, conv_id, testo, allegati, opzioni) -> dict:
    # Ruoli degli allegati scelti nell'interfaccia: partenza, fine, riferimento.
    ruoli = opzioni.get("ruoli") or []
    immagini = [(f, ruoli[i] if i < len(ruoli) else "") for i, f in enumerate(allegati) if f["mime"].startswith("image/")]
    partenza = next((f for f, r in immagini if r == "partenza"), None)
    fine = next((f for f, r in immagini if r == "fine"), None)
    riferimenti = [f for f, r in immagini if r == "riferimento"]
    if not ruoli and immagini:  # nessun ruolo indicato: la prima immagine è il primo fotogramma
        partenza = immagini[0][0]

    if riferimenti and (partenza or fine):
        raise RuntimeError("Veo non combina immagini di riferimento con primo/ultimo fotogramma: scegli uno dei due modi.")
    if fine and not partenza:
        raise RuntimeError("Per l'ultimo fotogramma serve anche un'immagine di partenza.")
    if len(riferimenti) > 3:
        raise RuntimeError("Veo accetta al massimo 3 immagini di riferimento.")
    immagine = _immagine(conv_id, partenza) if partenza else None
    if not testo and not immagine:
        raise RuntimeError("Scrivi una descrizione del video o allega un'immagine di partenza.")
    if any(f["mime"].startswith("video/") for f in allegati):
        raise RuntimeError("Veo non modifica video esistenti: per modificare un video usa Gemini Omni.")

    config = {"number_of_videos": 1, "aspect_ratio": opzioni.get("formato") or "16:9"}
    if opzioni.get("durata"):
        config["duration_seconds"] = int(opzioni["durata"])
    if opzioni.get("risoluzione"):
        config["resolution"] = opzioni["risoluzione"]
    if fine:
        config["last_frame"] = _immagine(conv_id, fine)
    if riferimenti:
        config["reference_images"] = [
            types.VideoGenerationReferenceImage(image=_immagine(conv_id, f), reference_type="ASSET")
            for f in riferimenti]
    if fine or riferimenti:
        config["duration_seconds"] = 8  # primo/ultimo fotogramma e riferimenti richiedono 8 secondi
    if "audio" in opzioni:
        config["generate_audio"] = bool(opzioni["audio"])
    # Nessun output_gcs_uri: il video torna nella risposta e resta solo in locale.
    op = client.models.generate_videos(
        model=m["id"], prompt=testo or None, image=immagine,
        config=types.GenerateVideosConfig(**config),
    )
    inizio = time.time()
    while not op.done:
        if time.time() - inizio > TIMEOUT_VIDEO:
            raise RuntimeError("La generazione del video ha superato i 20 minuti.")
        time.sleep(8)
        op = client.operations.get(op)
    if op.error:
        raise RuntimeError(f"Errore Veo: {op.error}")

    risultato = op.response or op.result
    file = []
    for v in (risultato.generated_videos if risultato else None) or []:
        if v.video and v.video.video_bytes:
            file.append(archivio.salva_file(conv_id, v.video.video_bytes, v.video.mime_type or "video/mp4", "video"))
        elif v.video and v.video.uri:
            raise RuntimeError(f"Vertex ha salvato il video su {v.video.uri} invece di restituirlo.")
    if not file:
        filtrati = getattr(risultato, "rai_media_filtered_reasons", None) if risultato else None
        raise RuntimeError("Nessun video generato" + (f": {filtrati}" if filtrati else "."))
    return {"testo": "", "file": file}
