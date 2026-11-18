"""Login e logout Google dall'interfaccia, usando la Google Cloud CLI.

Il login esegue `gcloud auth application-default login`: si apre la pagina di
Google nel browser, l'utente sceglie il proprio account e gcloud salva le
credenziali sul computer. Il logout esegue `gcloud auth application-default revoke`.
L'app non vede né salva mai password.
"""

import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import impostazioni, vertex

TIMEOUT_LOGIN = 5 * 60
INSTALLA = "https://cloud.google.com/sdk/docs/install"

_lock = threading.Lock()
_login = {"stato": "fermo", "messaggio": ""}  # fermo | in_corso | fatto | errore


# Dove l'installer ufficiale e Homebrew mettono gcloud, se non è nel PATH
# (es. app avviata con doppio clic prima di riaprire il terminale dopo l'installazione).
_PERCORSI_NOTI = [
    "~/google-cloud-sdk/bin/gcloud",
    "/opt/homebrew/bin/gcloud",
    "/opt/homebrew/share/google-cloud-sdk/bin/gcloud",
    "/usr/local/bin/gcloud",
    "/usr/local/share/google-cloud-sdk/bin/gcloud",
    "/usr/lib/google-cloud-sdk/bin/gcloud",
    "~/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
    "C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
    "C:/Program Files/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
]


def _da_percorso(scritto: str) -> Path | None:
    """Accetta il file gcloud, la cartella bin o la cartella google-cloud-sdk."""
    p = Path(scritto.strip().strip('"').strip("'")).expanduser()
    nomi = ["gcloud.cmd", "gcloud"] if sys.platform.startswith("win") else ["gcloud"]
    candidati = [p] + [p / n for n in nomi] + [p / "bin" / n for n in nomi]
    return next((c for c in candidati if c.is_file()), None)


def _gcloud() -> str | None:
    manuale = impostazioni.leggi().get("gcloud_path")
    if manuale:
        trovato = _da_percorso(manuale)
        if not trovato:
            raise FileNotFoundError(f"gcloud non trovato in «{manuale}» (Impostazioni → Generale).")
        return str(trovato)
    trovato = shutil.which("gcloud.cmd" if sys.platform.startswith("win") else "gcloud") or shutil.which("gcloud")
    if trovato:
        return trovato
    for p in _PERCORSI_NOTI:
        percorso = Path(p).expanduser()
        if percorso.is_file():
            return str(percorso)
    return None


def _esegui(argomenti: list[str], timeout: int) -> subprocess.CompletedProcess:
    eseguibile = _gcloud()
    if not eseguibile:
        raise FileNotFoundError(f"Google Cloud CLI non trovata. Installala da {INSTALLA}, "
                                "oppure indica dove si trova in Impostazioni → Generale.")
    return _lancia(eseguibile, argomenti, timeout)


def _lancia(eseguibile: str, argomenti: list[str], timeout: int) -> subprocess.CompletedProcess:
    extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform.startswith("win") else {}
    comando = [eseguibile, *argomenti]
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, **extra)
    except PermissionError:
        # File copiato senza permesso di esecuzione (Mac/Linux): lo si lancia tramite la shell.
        return subprocess.run(["sh", *comando], capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)


def prova_percorso(scritto: str) -> dict:
    """Verifica un percorso di gcloud inserito a mano (vuoto = ricerca automatica)."""
    try:
        if scritto.strip():
            trovato = _da_percorso(scritto)
            if not trovato:
                return {"ok": False, "messaggio": "Nessun gcloud in questo percorso: indica il file gcloud "
                        "o la cartella google-cloud-sdk (o la sua sottocartella bin)."}
            eseguibile = str(trovato)
        else:
            eseguibile = _gcloud()
            if not eseguibile:
                return {"ok": False, "messaggio": f"gcloud non trovato automaticamente. Indica il percorso o installalo da {INSTALLA}."}
        r = _lancia(eseguibile, ["--version"], 60)
        if r.returncode != 0:
            return {"ok": False, "messaggio": f"{eseguibile} non parte: {_ultima_riga_utile(r.stderr or r.stdout)}"}
        versione = next((x for x in r.stdout.splitlines() if x.strip()), "")
        return {"ok": True, "messaggio": f"Trovato: {eseguibile} ({versione})"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "messaggio": str(e)}


def _ultima_riga_utile(testo: str) -> str:
    righe = [r.strip() for r in (testo or "").splitlines() if r.strip()]
    errori = [r for r in righe if r.startswith("ERROR")]
    return (errori or righe or ["Errore sconosciuto"])[-1]


def _thread_login():
    try:
        r = _esegui(["auth", "application-default", "login"], TIMEOUT_LOGIN)
        if r.returncode == 0:
            esito = {"stato": "fatto", "messaggio": "Accesso eseguito"}
        else:
            esito = {"stato": "errore", "messaggio": _ultima_riga_utile(r.stderr or r.stdout)}
    except subprocess.TimeoutExpired:
        esito = {"stato": "errore", "messaggio": "Accesso non completato entro 5 minuti."}
    except Exception as e:  # noqa: BLE001
        esito = {"stato": "errore", "messaggio": str(e)}
    vertex.azzera()
    with _lock:
        _login.update(esito)


def avvia_login() -> dict:
    try:
        trovato = _gcloud()
    except FileNotFoundError as e:
        return {"stato": "errore", "messaggio": str(e)}
    if not trovato:
        return {"stato": "errore", "messaggio": f"Google Cloud CLI non trovata. Installala da {INSTALLA}, "
                "oppure indica dove si trova in Impostazioni → Generale."}
    with _lock:
        if _login["stato"] != "in_corso":
            _login.update(stato="in_corso", messaggio="Completa l'accesso nella pagina di Google che si è aperta.")
            threading.Thread(target=_thread_login, daemon=True).start()
        return dict(_login)


def stato_login() -> dict:
    with _lock:
        return dict(_login)


def logout() -> dict:
    try:
        r = _esegui(["auth", "application-default", "revoke", "--quiet"], 60)
        ok = r.returncode == 0 or "No credentials" in (r.stderr or "")
        msg = "Disconnesso" if ok else _ultima_riga_utile(r.stderr or r.stdout)
    except Exception as e:  # noqa: BLE001
        ok, msg = False, str(e)
    vertex.azzera()
    with _lock:
        _login.update(stato="fermo", messaggio="")
    return {"ok": ok, "messaggio": msg}
