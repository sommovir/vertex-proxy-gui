"""Verifica dei modelli configurati e ricerca di quelli disponibili sul progetto.

Usa solo letture di metadati (models.get / models.list): non genera niente
e non consuma credito.
"""

import re
from concurrent.futures import ThreadPoolExecutor

import requests

from . import claude, impostazioni, vertex

CATALOGO_ANTHROPIC = "https://aiplatform.googleapis.com/v1beta1/publishers/anthropic/models"

REGIONI_RICERCA = ["global", "us-central1"]
ESCLUSI = ("embedding", "tts", "live", "audio", "native-audio", "computer-use", "aqa")


def _profilo() -> dict:
    p = impostazioni.profilo_attivo()
    if not p:
        raise RuntimeError("Nessun profilo attivo: aggiungine uno in Impostazioni → Profili.")
    return p


def verifica(modelli: list[dict]) -> list[dict]:
    profilo = _profilo()

    def una(m: dict) -> dict:
        regione = impostazioni.regione_per(m, profilo)
        try:
            if m.get("tipo") == "claude":
                claude.verifica(vertex.claude(profilo, regione), m["id"])
                return {"id": m["id"], "ok": True, "messaggio": f"Abilitato ({regione})"}
            vertex.client(profilo, regione).models.get(model=m["id"])
            return {"id": m["id"], "ok": True, "messaggio": f"Disponibile ({regione})"}
        except Exception as e:  # noqa: BLE001
            testo = str(e)
            if m.get("tipo") == "claude" and getattr(e, "status_code", None) in (403, 404):
                testo = f"Non abilitato nel Model Garden del progetto (o nome sbagliato) in {regione}"
            elif vertex.errore_di_accesso(e):
                vertex.azzera()
                testo = vertex.spiega_errore(e)
            elif "404" in testo or "NOT_FOUND" in testo:
                testo = f"Non trovato in {regione}: nome sbagliato, modello ritirato o regione non supportata"
            else:
                testo = vertex.spiega_errore(e)[:300]
            return {"id": m["id"], "ok": False, "messaggio": testo}

    validi = [m for m in modelli if m.get("id")]
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(una, validi))


def _tipo(nome: str) -> str | None:
    n = nome.lower()
    if any(x in n for x in ESCLUSI):
        return None
    if n.startswith("veo"):
        return "veo"
    if n.startswith("imagen"):
        return "imagen"
    if n.startswith("gemini-omni"):
        return "omni"
    if n.startswith("gemini"):
        return "gemini-immagine" if "image" in n else "chat"
    return None


def disponibili() -> list[dict]:
    profilo = _profilo()
    trovati: dict[str, dict] = {}
    errori = []
    for regione in REGIONI_RICERCA:
        try:
            for m in vertex.client(profilo, regione).models.list(config={"query_base": True, "page_size": 200}):
                mid = (m.name or "").split("/")[-1]
                tipo = _tipo(mid)
                if not tipo:
                    continue
                voce = trovati.setdefault(mid, {"id": mid, "nome": m.display_name or mid, "tipo": tipo, "regioni": []})
                voce["regioni"].append(regione)
        except Exception as e:  # noqa: BLE001
            errori.append(f"{regione}: {vertex.spiega_errore(e)[:200]}")
    try:
        for voce in _claude_abilitati(profilo):
            trovati[voce["id"]] = voce
    except Exception as e:  # noqa: BLE001
        errori.append(f"Anthropic: {vertex.spiega_errore(e)[:200]}")
    if not trovati and errori:
        raise RuntimeError("Ricerca non riuscita. " + " | ".join(errori))
    ordine = {"chat": 0, "claude": 1, "gemini-immagine": 2, "imagen": 3, "veo": 4, "omni": 5}
    return sorted(trovati.values(), key=lambda v: (ordine[v["tipo"]], v["id"]))


def _catalogo_claude(profilo: dict) -> list[dict]:
    """Modelli Claude del catalogo Vertex (tutti, abilitati o no)."""
    voci, pagina = [], None
    while True:
        r = requests.get(CATALOGO_ANTHROPIC, timeout=20,
                         params={"pageSize": 100, **({"pageToken": pagina} if pagina else {})},
                         headers={"Authorization": f"Bearer {vertex.token(profilo)}",
                                  "x-goog-user-project": profilo["progetto"]})
        r.raise_for_status()
        dati = r.json()
        voci += dati.get("publisherModels", [])
        pagina = dati.get("nextPageToken")
        if not pagina:
            return voci


def _claude_abilitati(profilo: dict) -> list[dict]:
    """Catalogo Anthropic filtrato con un conteggio token gratuito: restano solo gli abilitati."""
    ids = set()
    for voce in _catalogo_claude(profilo):
        mid = (voce.get("name") or "").split("/")[-1].split("@")[0]
        if re.match(r"^claude-[a-z0-9-]+$", mid) and "count-tokens" not in mid:
            ids.add(mid)
    client = vertex.claude(profilo, "global")

    def prova(mid: str) -> dict | None:
        try:
            claude.verifica(client, mid)
            return {"id": mid, "nome": mid, "tipo": "claude", "regioni": ["global"]}
        except Exception:  # noqa: BLE001 - non abilitato o non disponibile in global
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        return [v for v in pool.map(prova, sorted(ids)) if v]
