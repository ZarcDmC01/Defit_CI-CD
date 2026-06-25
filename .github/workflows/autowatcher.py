"""
Watcher local : surveille les fichiers source et push automatiquement.
Démarrage : python .github/workflows/autowatcher.py
"""
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

EXTENSIONS_SURVEILLEES = {".py", ".yml", ".txt", ".env.example"}

DOSSIERS_EXCLUS = {"venv", ".git", "__pycache__", ".cache"}


class SaveHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path.replace("\\", "/")
        if any(exclu in path for exclu in DOSSIERS_EXCLUS):
            return
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext not in EXTENSIONS_SURVEILLEES:
            return

        nom = path.split("/")[-1]
        print(f"[watcher] Changement détecté : {nom}")

        subprocess.run(["git", "add", "-A"])
        result = subprocess.run(
            ["git", "commit", "-m", f"auto: save {nom}"],
            capture_output=True,
            text=True,
        )
        if "nothing to commit" in result.stdout:
            return

        push = subprocess.run(["git", "push"], capture_output=True, text=True)
        if push.returncode == 0:
            print(f"[watcher] Push OK : {nom}")
        else:
            print(f"[watcher] Push échoué : {push.stderr}")


if __name__ == "__main__":
    print("Surveillance active sur les fichiers source... (Ctrl+C pour arrêter)")
    observer = Observer()
    observer.schedule(SaveHandler(), path=".", recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
