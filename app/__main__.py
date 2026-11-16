"""Avvio: python -m app  (apre il browser su http://127.0.0.1:8765)."""

import os
import threading
import webbrowser

import uvicorn

PORTA = int(os.environ.get("VERTEX_STUDIO_PORTA", "8765"))


def main():
    url = f"http://127.0.0.1:{PORTA}"
    if os.environ.get("VERTEX_STUDIO_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"\n  Vertex Studio è attivo su {url}\n  Per chiuderlo: Ctrl+C oppure chiudi questa finestra.\n")
    # Solo 127.0.0.1: l'app non è raggiungibile da altri computer.
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORTA, log_level="warning")


if __name__ == "__main__":
    main()
