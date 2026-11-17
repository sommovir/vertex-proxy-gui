# Vertex Studio

Client locale per usare **Vertex AI** (Gemini, Nano Banana, Imagen, Veo) dal proprio computer,
su **Mac e Windows**, senza API key e senza chiavi JSON.

- **Accesso con impersonation**: ognuno usa il proprio account Google e ottiene un token
  temporaneo a nome del service account del progetto.
- **Tutto in locale**: conversazioni, immagini e video restano nella cartella `~/VertexStudio`.
  Non c'è nessun server remoto né bucket. Le richieste vanno solo a Vertex AI.
- **Configurabile dall'app**: i profili (progetto, service account, regioni) e i modelli si
  gestiscono dal pannello *Impostazioni*. Vengono salvati in `~/VertexStudio/impostazioni.json`,
  mai nel repository.

## Prerequisiti (una volta sola)

1. **Python 3.10 o superiore**: <https://www.python.org/downloads/>
   (su Windows spunta "Add python.exe to PATH").
2. **Google Cloud CLI**: <https://cloud.google.com/sdk/docs/install>
3. Un amministratore del progetto deve dare al tuo account il permesso di impersonare il
   service account:

   ```bash
   gcloud iam service-accounts add-iam-policy-binding SERVICE_ACCOUNT_EMAIL \
     --member="user:TUA_EMAIL" --role="roles/iam.serviceAccountTokenCreator"
   ```

   Il service account a sua volta deve avere il ruolo `Vertex AI User` (`roles/aiplatform.user`)
   sul progetto. Sul progetto devono essere abilitate le API **Vertex AI** e
   **IAM Service Account Credentials**.

## Installazione

```bash
git clone https://github.com/sommovir/vertex-proxy-gui.git
cd vertex-proxy-gui
```

Per aggiornare a una versione nuova: `git pull` nella stessa cartella, poi riavvia l'app.
I dati in `~/VertexStudio` non vengono toccati.

## Avvio

- **Windows**: doppio clic su `avvia.bat`
- **Mac**: doppio clic su `avvia.command`. La prima volta potrebbe servire tasto destro → *Apri*.
  Se non parte, da terminale: `chmod +x avvia.command`.

Al primo avvio vengono installate le librerie in `.venv` (circa un minuto). Poi si apre il browser su
<http://127.0.0.1:8765>. L'app ascolta solo su questo computer.

Per chiuderla: `Ctrl+C` nella finestra del terminale che si è aperta, oppure chiudi la finestra.

Al primo avvio:

1. premi **Accedi** in basso a sinistra e scegli il tuo account Google nella pagina che si apre.
   Dietro le quinte l'app esegue `gcloud auth application-default login`. **Esci** revoca
   l'accesso da quel computer.
2. nel pannello **Impostazioni** aggiungi un profilo con ID progetto e service account.

Il pallino in basso a sinistra diventa verde quando la connessione funziona. Passandoci sopra
vedi con quale account sei collegato. L'identità è sempre quella dell'account con cui hai fatto
l'accesso: nel profilo non va scritta nessuna email personale.

## Uso

- **Chat**: Gemini, con allegati (immagini, PDF, audio, video brevi).
- **Immagine**:
  - *Nano Banana* genera e modifica le immagini e ricorda la conversazione: allega una foto
    o premi "Riusa immagine" e chiedi le modifiche.
  - *Imagen* genera da testo, anche più immagini alla volta.
- **Video**: Veo, da testo o da un'immagine di partenza allegata. Ci vogliono 1–3 minuti.

Le conversazioni eliminate finiscono in `~/VertexStudio/cestino`.

## Dove sono i dati

```
~/VertexStudio/
  impostazioni.json            profili e modelli
  conversazioni/<id>/
    info.json                  titolo e date
    messaggi.jsonl             un messaggio per riga
    media/                     immagini, video, allegati
  cestino/
```

Variabili d'ambiente opzionali: `VERTEX_STUDIO_DATI` (altra cartella dati),
`VERTEX_STUDIO_PORTA` (altra porta), `VERTEX_STUDIO_NO_BROWSER=1`.

## Struttura del codice

```
app/
  __main__.py      avvio del server locale (uvicorn su 127.0.0.1)
  main.py          API FastAPI
  account.py       accedi/esci tramite gcloud
  impostazioni.py  profili e modelli (file JSON locale)
  vertex.py        credenziali con impersonation e client google-genai
  generazione.py   chat, immagini, video
  archivio.py      salvataggio locale delle conversazioni
  static/          interfaccia (HTML/CSS/JS puro, senza build)
```

## Problemi comuni

| Messaggio | Soluzione |
|---|---|
| Accesso mancante o scaduto | premi **Accedi** (oppure `gcloud auth application-default login`) |
| Google Cloud CLI non trovata | installala (vedi Prerequisiti) e riavvia l'app |
| Non può impersonare il service account | al tuo account manca il ruolo *Service Account Token Creator* (vedi sopra) |
| Il service account non esiste | controlla l'email del service account in *Impostazioni → Profili* |
| API «IAM Service Account Credentials» non abilitata | va abilitata sul progetto dalla console Google Cloud |
| La pagina non si apre / porta occupata | un'altra istanza è già aperta, oppure avvia con `VERTEX_STUDIO_PORTA=8770` |
| Modello non trovato / 404 | il modello ha cambiato nome o non è disponibile in quella regione: correggilo in *Impostazioni → Modelli* |
| Nano Banana Pro / Gemini 3 non risponde | quei modelli richiedono la regione `global` |
