"""Credenziali Google tramite impersonation e client Vertex AI.

Nessuna chiave JSON: si parte dalle credenziali dell'utente
(`gcloud auth application-default login`) e si chiede a Google un token
a breve scadenza per conto del service account del profilo attivo.
"""

import threading

import google.auth
import requests
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
        # Il quota project di gcloud (es. un progetto personale) farebbe addebitare lì la
        # richiesta di impersonation, che fallisce se lì l'API IAM Credentials è spenta.
        # Senza quota project la richiesta va sul progetto del service account.
        if getattr(sorgente, "quota_project_id", None) and hasattr(sorgente, "with_quota_project"):
            sorgente = sorgente.with_quota_project(None)
        _cache[("sorgente",)] = sorgente
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
    if "SERVICE_DISABLED" in testo and "iamcredentials" in testo:
        return ("L'API «IAM Service Account Credentials» non è abilitata sul progetto. "
                "Va abilitata dalla console Google Cloud. Dettaglio: " + testo)
    if "iam.serviceAccounts.getAccessToken" in testo:
        return ("Questo account non può impersonare il service account: gli serve il ruolo "
                "«Service Account Token Creator» (oppure accedi con un account che ce l'ha).")
    return testo


def errore_di_accesso(e: Exception) -> bool:
    return isinstance(e, google.auth.exceptions.GoogleAuthError)


def _chi_sono() -> str:
    """Email dell'account Google con cui è stato fatto il login gcloud su questo computer."""
    sorgente = _cache.get(("sorgente",))
    try:
        if getattr(sorgente, "token", None):
            r = requests.get("https://oauth2.googleapis.com/tokeninfo",
                             params={"access_token": sorgente.token}, timeout=10)
            return r.json().get("email", "") if r.ok else ""
    except requests.RequestException:
        pass
    return ""


def verifica(profilo: dict) -> dict:
    """Prova a ottenere un token. Ritorna {ok, messaggio, account}."""
    sa = profilo.get("service_account", "")
    try:
        with _lock:
            cred = _credenziali(sa)
            sorgente = _cache[("sorgente",)]
        if sa:
            sorgente.refresh(Request())
        account = _chi_sono()
        cred.refresh(Request())
        if sa:
            return {"ok": True, "account": account,
                    "messaggio": f"{account or 'Il tuo account'} sta usando il service account {sa}"}
        return {"ok": True, "account": account,
                "messaggio": f"Connesso come {account or 'utente'} (senza impersonation)"}
    except Exception as e:  # noqa: BLE001 - mostriamo all'utente il motivo
        account = _chi_sono()
        azzera()
        msg = spiega_errore(e)
        if account:
            msg = f"Login gcloud attuale: {account}. " + msg
        return {"ok": False, "account": account, "messaggio": msg}
