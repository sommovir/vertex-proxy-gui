# Vertex Studio

Client locale per usare **Vertex AI** (Gemini, Claude, Nano Banana, Veo) dal proprio computer,
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
   (su Windows spunta "Add python.exe to PATH"; su Mac il `python3` preinstallato con gli
   strumenti di Xcode è spesso la 3.9, troppo vecchia: installa quello di python.org).
2. **Google Cloud CLI**: <https://cloud.google.com/sdk/docs/install>
3. Un amministratore del progetto deve dare al tuo account il permesso di impersonare il
   service account:

   ```bash
   gcloud iam service-accounts add-iam-policy-binding SERVICE_ACCOUNT_EMAIL \
     --member="user:TUA_EMAIL" --role="roles/iam.serviceAccountTokenCreator"
   ```

   Il service account a sua volta deve avere il ruolo `Vertex AI User` (`roles/aiplatform.user`)
   sul progetto. Sul progetto devono essere abilitate le API **Vertex AI** e
   **IAM Service Account Credentials**. Per usare **Claude** i modelli Anthropic vanno attivati
   una volta nel **Model Garden** di Vertex AI (pagina del modello → *Enable*).

## Installazione

```bash
git clone https://github.com/sommovir/vertex-proxy-gui.git
cd vertex-proxy-gui
```

Per aggiornare a una versione nuova: `git pull` nella stessa cartella, poi riavvia l'app.
I dati in `~/VertexStudio` non vengono toccati.

### Cartella copiata da un altro computer (es. da Windows a Mac)

Funziona, con tre accortezze:

- **L'accesso Google non viaggia con la cartella**: sta nel computer, nella configurazione di
  gcloud. Sul nuovo computer basta premere **Accedi**.
- **Profili e conversazioni non viaggiano con la cartella**: stanno in `~/VertexStudio`.
  Si ricrea il profilo dalle Impostazioni, oppure si copia anche `~/VertexStudio/impostazioni.json`.
- **Su Mac, se il doppio clic su `avvia.command` non fa niente o dice «permesso negato»**: copiando
  da Windows (chiavetta, zip, cloud) si perde il permesso di esecuzione. Da terminale, nella cartella:

  ```bash
  chmod +x avvia.command
  ```

  Se macOS dice che il file «proviene da Internet» o «non può essere verificato»: tasto destro →
  *Apri* → *Apri*. In alternativa si può sempre avviare da terminale con `bash avvia.command`.

La cartella `.venv` copiata da un altro sistema non funziona: `avvia` se ne accorge e la ricrea
da sola al primo avvio (circa un minuto). Copiandola, conviene comunque lasciarla fuori.

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

- **Chat**: Gemini (allegati: immagini, PDF, audio, video brevi) e Claude (allegati: immagini e PDF).
- **Immagine**: *Nano Banana* genera e modifica le immagini e ricorda la conversazione: allega
  una foto o premi "Riusa immagine" e chiedi le modifiche. Imagen è stato ritirato da Google
  (giugno 2026), ma il tipo resta disponibile se ne servisse uno.
- **Video**: Veo 3.1 e Gemini Omni 1.2 Flash. Ci vogliono 1–3 minuti. Su ogni immagine allegata
  scegli il ruolo dal menu che compare sotto l'anteprima:
  - **Primo fotogramma** (e con Veo anche **Ultimo fotogramma**): il video parte (e finisce) da lì;
  - **Riferimento**: personaggi, oggetti o scene da mantenere coerenti
    (Veo fino a 3, Omni fino a 6; non si combinano con primo/ultimo fotogramma).
  - Con **Omni** puoi anche allegare un **video** (max 15 s) e scrivere cosa cambiare: lo modifica,
    eventualmente con 1–2 immagini di riferimento. Omni fa clip da 5 a 15 secondi con audio.
  - Primo+ultimo fotogramma e riferimenti con Veo richiedono 8 secondi (impostati in automatico).

I modelli predefiniti sono aggiornati al 17/11/2026: Gemini 4 Carbon/Argon, Gemini 3.8 Flash,
Claude Opus/Sonnet/Haiku 5.5, Nano Banana 2/Pro/2.1, Veo 3.1, Gemini Omni 1.2 Flash. Quando l'app si aggiorna con
`git pull`, i modelli nuovi vengono aggiunti alla tua lista e quelli ritirati tolti; quelli
che hai aggiunto tu restano.

Le conversazioni eliminate finiscono in `~/VertexStudio/cestino`.

### Provare altri modelli

- Dal menu dei modelli in chat scegli **＋ Altro modello…** e incolla l'ID così come appare nel
  Model Garden di Vertex (es. `gemini-4-carbon`, oppure `publishers/google/models/gemini-4-carbon`).
  L'app lo aggiunge e controlla subito che sia disponibile.
- In **Impostazioni → Modelli**:
  - **Verifica modelli** segna ✓/✗ su ogni modello della lista, senza consumare credito;
  - **Cerca modelli disponibili** elenca i Gemini/Veo visibili al progetto e i **Claude
    abilitati nel Model Garden**, e li aggiunge con un clic (per Claude la verifica usa il
    conteggio token, gratuito);
  - si può anche rinominare, cambiare regione o togliere un modello.

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
  modelli.py       verifica e ricerca dei modelli disponibili
  claude.py        chat con Claude (SDK anthropic[vertex])
  omni.py          video con Gemini Omni (Interactions API)
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
