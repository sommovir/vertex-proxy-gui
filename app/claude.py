"""Chat con i modelli Claude (Anthropic) su Vertex AI, con l'SDK ufficiale anthropic[vertex]."""

import base64

import anthropic

from . import archivio

MAX_MESSAGGI_CONTESTO = 20
MESSAGGI_CON_FILE = 6
MAX_BYTE_FILE_CONTESTO = 15 * 1024 * 1024
IMMAGINI = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _blocco_file(conv_id: str, f: dict) -> dict | None:
    if f["mime"] not in IMMAGINI and f["mime"] != "application/pdf":
        return None
    try:
        dati = archivio.percorso_file(conv_id, f["nome"]).read_bytes()
    except (OSError, ValueError):
        return None
    sorgente = {"type": "base64", "media_type": f["mime"], "data": base64.standard_b64encode(dati).decode()}
    return {"type": "image" if f["mime"] in IMMAGINI else "document", "source": sorgente, "_byte": len(dati)}


def _contesto(conv_id: str) -> list[dict]:
    messaggi = [m for m in archivio.leggi(conv_id)["messaggi"] if m["ruolo"] in ("utente", "modello")]
    messaggi = messaggi[-MAX_MESSAGGI_CONTESTO:]
    while messaggi and messaggi[0]["ruolo"] != "utente":  # il primo messaggio deve essere dell'utente
        messaggi.pop(0)
    budget = MAX_BYTE_FILE_CONTESTO
    risultato = []
    for i, m in enumerate(messaggi):
        contenuto = []
        if m["ruolo"] == "utente" and i >= len(messaggi) - MESSAGGI_CON_FILE:
            for f in m.get("file", []):
                blocco = _blocco_file(conv_id, f)
                if blocco and blocco["_byte"] <= budget:
                    budget -= blocco.pop("_byte")
                    contenuto.append(blocco)
        if m.get("testo"):
            contenuto.append({"type": "text", "text": m["testo"]})
        if contenuto:
            risultato.append({"role": "user" if m["ruolo"] == "utente" else "assistant", "content": contenuto})
    return risultato


def genera(client: anthropic.AnthropicVertex, m: dict, conv_id: str, istruzioni: str) -> dict:
    richiesta = {"model": m["id"], "max_tokens": 16000, "messages": _contesto(conv_id)}
    if istruzioni:
        richiesta["system"] = istruzioni
    try:
        risposta = client.messages.create(**richiesta)
    except anthropic.NotFoundError as e:
        raise RuntimeError(f"Modello {m['id']} non trovato o non abilitato nel Model Garden "
                           "del progetto (va attivato una volta dalla console Vertex AI).") from e
    except anthropic.PermissionDeniedError as e:
        raise RuntimeError(f"Accesso negato a {m['id']}: il modello va abilitato nel Model Garden "
                           f"del progetto. Dettaglio: {e.message}") from e
    if risposta.stop_reason == "refusal":
        dettaglio = getattr(risposta, "stop_details", None)
        motivo = f" (categoria: {dettaglio.category})" if dettaglio and dettaglio.category else ""
        raise RuntimeError(f"Il modello ha rifiutato la richiesta{motivo}. Prova a riformularla o usa un altro modello.")
    testo = "\n\n".join(b.text for b in risposta.content if b.type == "text")
    if risposta.stop_reason == "max_tokens":
        testo += "\n\n_(risposta interrotta: raggiunto il limite di lunghezza)_"
    if not testo:
        raise RuntimeError("Il modello non ha restituito testo.")
    return {"testo": testo, "file": []}


def verifica(client: anthropic.AnthropicVertex, mid: str) -> None:
    """Conteggio token (gratuito): fallisce se il modello non esiste o non è abilitato."""
    client.messages.count_tokens(model=mid, messages=[{"role": "user", "content": "ping"}])
