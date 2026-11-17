"""Verifica dei modelli configurati e ricerca di quelli disponibili sul progetto.

Usa solo letture di metadati (models.get / models.list): non genera niente
e non consuma credito.
"""

from concurrent.futures import ThreadPoolExecutor

from . import impostazioni, vertex

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
            vertex.client(profilo, regione).models.get(model=m["id"])
            return {"id": m["id"], "ok": True, "messaggio": f"Disponibile ({regione})"}
        except Exception as e:  # noqa: BLE001
            testo = str(e)
            if vertex.errore_di_accesso(e):
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
    if not trovati and errori:
        raise RuntimeError("Ricerca non riuscita. " + " | ".join(errori))
    ordine = {"chat": 0, "gemini-immagine": 1, "imagen": 2, "veo": 3}
    return sorted(trovati.values(), key=lambda v: (ordine[v["tipo"]], v["id"]))
