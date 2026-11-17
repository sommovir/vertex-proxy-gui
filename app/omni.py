"""Video con Gemini Omni (Interactions API di Vertex AI, location global).

Casi gestiti, in base agli allegati e al loro ruolo:
- solo testo                         -> nuovo video
- un'immagine «partenza»             -> image_to_video (primo fotogramma)
- immagini «riferimento» (max 6)     -> reference_to_video (personaggi, oggetti, stile)
- un video allegato                  -> edit (modifica del video con l'istruzione)

Il video torna inline (base64) nella risposta: nessun bucket, resta solo in locale.
Nota: Google documenta Omni su Vertex solo via REST; qui si usa client.interactions
dell'SDK google-genai, che espone la stessa API.
"""

import base64
import time

from . import archivio

TIMEOUT = 20 * 60
MAX_RIFERIMENTI = 6
MAX_BYTE_VIDEO_INPUT = 20 * 1024 * 1024
IN_CORSO = {"in_progress", "queued", "pending", "running", "processing"}


def _parte(conv_id: str, f: dict) -> dict:
    dati = archivio.percorso_file(conv_id, f["nome"]).read_bytes()
    tipo = "video" if f["mime"].startswith("video/") else "image"
    if tipo == "video" and len(dati) > MAX_BYTE_VIDEO_INPUT:
        raise RuntimeError("Il video allegato è troppo grande (max 20 MB, e al massimo 15 secondi).")
    return {"type": tipo, "data": base64.b64encode(dati).decode(), "mime_type": f["mime"]}


def _stato(interazione) -> str:
    s = getattr(interazione, "status", "") or ""
    return str(getattr(s, "value", s)).lower()


def _video_da(interazione) -> tuple[bytes, str] | None:
    candidati = [getattr(interazione, "output_video", None)]
    for step in getattr(interazione, "steps", None) or []:
        candidati += [c for c in (getattr(step, "content", None) or []) if getattr(c, "type", "") == "video"]
    for v in candidati:
        if v is not None and getattr(v, "data", None):
            dati = v.data
            return (base64.b64decode(dati) if isinstance(dati, str) else bytes(dati)), (v.mime_type or "video/mp4")
        if v is not None and getattr(v, "uri", None):
            raise RuntimeError(f"Omni ha salvato il video su {v.uri} invece di restituirlo.")
    return None


def genera(client, m: dict, conv_id: str, testo: str, allegati: list[dict], opzioni: dict) -> dict:
    ruoli = opzioni.get("ruoli") or []
    video = [f for f in allegati if f["mime"].startswith("video/")]
    immagini = [(f, ruoli[i] if i < len(ruoli) else "") for i, f in enumerate(allegati) if f["mime"].startswith("image/")]
    partenza = [f for f, r in immagini if r == "partenza"]
    riferimenti = [f for f, r in immagini if r != "partenza"]

    if not testo:
        raise RuntimeError("Scrivi cosa deve succedere nel video (o cosa modificare).")
    formato = {"type": "video", "delivery": "inline", "resolution": opzioni.get("risoluzione") or "720p"}
    parti = []
    if video:
        task = "edit"
        if len(riferimenti) > 2:
            raise RuntimeError("Per modificare un video si possono aggiungere al massimo 2 immagini di riferimento.")
        parti = [{"type": "text", "text": testo}, _parte(conv_id, video[0])] + [_parte(conv_id, f) for f in riferimenti]
    else:
        formato["aspect_ratio"] = opzioni.get("formato") or "16:9"
        formato["duration"] = f"{int(opzioni.get('durata') or 8)}s"
        if partenza and riferimenti:
            raise RuntimeError("Con Omni usa o un'immagine di partenza o delle immagini di riferimento, non entrambe.")
        if partenza:
            task = "image_to_video"
            parti = [_parte(conv_id, partenza[0]), {"type": "text", "text": testo}]
        elif riferimenti:
            if len(riferimenti) > MAX_RIFERIMENTI:
                raise RuntimeError(f"Al massimo {MAX_RIFERIMENTI} immagini di riferimento.")
            task = "reference_to_video"
            parti = [_parte(conv_id, f) for f in riferimenti] + [
                {"type": "text", "text": f"{testo}\n\nUse the image(s) as references to generate the video."}]
        else:
            task = None
            parti = [{"type": "text", "text": testo}]

    richiesta = {"model": m["id"], "input": parti, "response_format": [formato],
                 "store": True, "background": True}
    if task:
        richiesta["generation_config"] = {"video_config": {"task": task}}

    interazione = client.interactions.create(**richiesta)
    inizio = time.time()
    while _stato(interazione) in IN_CORSO:
        if time.time() - inizio > TIMEOUT:
            raise RuntimeError("La generazione del video ha superato i 20 minuti.")
        time.sleep(8)
        interazione = client.interactions.get(interazione.id)

    stato = _stato(interazione)
    if stato != "completed":
        errori = getattr(interazione, "errors", None)
        raise RuntimeError(f"Omni ha terminato con stato «{stato}»" + (f": {errori}" if errori else "."))
    risultato = _video_da(interazione)
    if not risultato:
        raise RuntimeError("Omni non ha restituito nessun video (forse bloccato dai filtri di sicurezza).")
    dati, mime = risultato
    return {"testo": "", "file": [archivio.salva_file(conv_id, dati, mime, "video")]}
