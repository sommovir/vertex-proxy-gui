"""Credenziali Google tramite impersonation e client Vertex AI.

Nessuna chiave JSON: si parte dalle credenziali dell'utente
(`gcloud auth application-default login`) e si chiede a Google un token
a breve scadenza per conto del service account del profilo attivo.
"""

import threading

import google.auth
from google import genai
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_lock = threading.Lock()
_cache: dict = {}  # chiave (service_account) -> credenziali; (sa, progetto, regione) -> client


def _credenziali(service_account: str):
    chiave = ("cred", service_account)
    if chiave not in _cache:
        sorgente, _ = google.auth.default(scopes=SCOPES)
        if service_account:
            _cache[chiave] = impersonated_credentials.Credentials(
                source_credentials=sorgente,
                target_principal=service_account,
                target_scopes=SCOPES,
                lifetime=3600,
            )
        else:
            _cache[chiave] = sorgente
    return _cache[chiave]


def client(profilo: dict, regione: str) -> genai.Client:
    sa = profilo.get("service_account", "")
    chiave = ("client", sa, profilo["progetto"], regione)
    with _lock:
        if chiave not in _cache:
            _cache[chiave] = genai.Client(
                vertexai=True,
                project=profilo["progetto"],
                location=regione,
                credentials=_credenziali(sa),
            )
        return _cache[chiave]


def azzera():
    """Dimentica credenziali e client (dopo un cambio di profilo o un errore di login)."""
    with _lock:
        _cache.clear()


def spiega_errore(e: Exception) -> str:
    """Traduce gli errori di autenticazione più comuni in istruzioni chiare."""
    testo = str(e) or e.__class__.__name__
    if isinstance(e, google.auth.exceptions.DefaultCredentialsError):
        return "Login Google mancante. Esegui nel terminale: gcloud auth application-default login"
    if "invalid_grant" in testo or "Reauthentication" in testo:
        return "Login Google scaduto. Esegui nel terminale: gcloud auth application-default login"
    if "iam.serviceAccounts.getAccessToken" in testo:
        return ("Il tuo account non può impersonare questo service account: serve il ruolo "
                "«Service Account Token Creator». Dettaglio: " + testo)
    return testo


def errore_di_accesso(e: Exception) -> bool:
    return isinstance(e, google.auth.exceptions.GoogleAuthError)


def verifica(profilo: dict) -> dict:
    """Prova a ottenere un token. Ritorna {ok, messaggio}."""
    try:
        with _lock:
            cred = _credenziali(profilo.get("service_account", ""))
        cred.refresh(Request())
        chi = profilo.get("service_account") or "credenziali personali (senza impersonation)"
        return {"ok": True, "messaggio": f"Connesso come {chi}"}
    except Exception as e:  # noqa: BLE001 - mostriamo all'utente il motivo
        azzera()
        return {"ok": False, "messaggio": spiega_errore(e)}
