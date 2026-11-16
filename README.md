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
3. Fai il login con il tuo account:

   ```bash
   gcloud auth application-default login
   ```

4. Un amministratore del progetto deve dare al tuo account il permesso di impersonare il
   service account:

   ```bash
   gcloud iam service-accounts add-iam-policy-binding SERVICE_ACCOUNT_EMAIL \
     --member="user:TUA_EMAIL" --role="roles/iam.serviceAccountTokenCreator"
   ```

   Il service account a sua volta deve avere il ruolo `Vertex AI User` (`roles/aiplatform.user`)
   sul progetto, e l'API Vertex AI deve essere abilitata.

## Avvio

- **Windows**: doppio clic su `avvia.bat`
- **Mac**: doppio clic su `avvia.command`. La prima volta potrebbe servire tasto destro → *Apri*.
  Se non parte, da terminale: `chmod +x avvia.command`.

Al primo avvio vengono installate le librerie in `.venv` (circa un minuto). Poi si apre il browser su
<http://127.0.0.1:8765>. L'app ascolta solo su questo computer.

Al primo avvio si apre il pannello Impostazioni: aggiungi un profilo con ID progetto e service
account. Il pallino in basso a sinistra diventa verde quando la connessione funziona.

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
  impostazioni.py  profili e modelli (file JSON locale)
  vertex.py        credenziali con impersonation e client google-genai
  generazione.py   chat, immagini, video
  archivio.py      salvataggio locale delle conversazioni
  static/          interfaccia (HTML/CSS/JS puro, senza build)
```

## Problemi comuni

| Messaggio | Soluzione |
|---|---|
| Login Google mancante | `gcloud auth application-default login` |
| Non può impersonare il service account | manca il ruolo *Service Account Token Creator* (vedi sopra) |
| Modello non trovato / 404 | il modello ha cambiato nome o non è disponibile in quella regione: correggilo in *Impostazioni → Modelli* |
| Nano Banana Pro / Gemini 3 non risponde | quei modelli richiedono la regione `global` |
