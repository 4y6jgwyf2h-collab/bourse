"""Ouvre l'appli Bourse dans sa propre fenêtre (sans navigateur).

Démarre Streamlit en arrière-plan, puis affiche l'interface dans une fenêtre
Windows classique. Fermer la fenêtre arrête tout.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

DOSSIER = os.path.dirname(os.path.abspath(__file__))


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def attendre(url: str, delai: float = 60) -> bool:
    fin = time.time() + delai
    while time.time() < fin:
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    port = port_libre()
    url = f"http://127.0.0.1:{port}"
    python = sys.executable
    if python.lower().endswith("pythonw.exe"):
        python = python[:-5] + ".exe"  # pythonw -> python pour le serveur
    options = {}
    if os.name == "nt":
        options["creationflags"] = 0x08000000  # CREATE_NO_WINDOW : pas de fenêtre noire
    serveur = subprocess.Popen(
        [python, "-m", "streamlit", "run", os.path.join(DOSSIER, "app.py"),
         "--server.headless", "true", "--server.port", str(port),
         "--server.address", "127.0.0.1", "--browser.gatherUsageStats", "false",
         "--theme.base", "light"],
        env={**os.environ, "BOURSE_LOCAL": "1"},
        cwd=DOSSIER, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    try:
        if not attendre(url):
            raise RuntimeError("Le serveur Streamlit n'a pas démarré.")
        try:
            import webview
        except ImportError:
            webbrowser.open(url)  # repli : navigateur
            serveur.wait()
            return
        webview.create_window("Bourse — analyse des marchés", url,
                              width=1400, height=900, min_size=(900, 600))
        webview.start()
    finally:
        serveur.terminate()
        try:
            serveur.wait(timeout=5)
        except Exception:
            serveur.kill()


if __name__ == "__main__":
    main()
