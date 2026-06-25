# Journal de construction — AI File Processing Pipeline

Document complet retraçant chaque étape de création du projet, dans l'ordre chronologique,
avec toutes les commandes exécutées et les décisions techniques prises.

---

## Table des matières

1. [Contexte et objectifs](#1-contexte-et-objectifs)
2. [Architecture choisie](#2-architecture-choisie)
3. [Création de la structure de fichiers](#3-création-de-la-structure-de-fichiers)
4. [Couche Config](#4-couche-config)
5. [Couche Storage](#5-couche-storage)
6. [Couche API — Schémas Pydantic](#6-couche-api--schémas-pydantic)
7. [Couche Processing — Validation](#7-couche-processing--validation)
8. [Couche Processing — Prétraitement](#8-couche-processing--prétraitement)
9. [Couche Processing — Inférence IA](#9-couche-processing--inférence-ia)
10. [Couche Service](#10-couche-service)
11. [Couche API — Routes FastAPI](#11-couche-api--routes-fastapi)
12. [Interface Gradio](#12-interface-gradio)
13. [Installation des dépendances](#13-installation-des-dépendances)
14. [Tests et validation locale](#14-tests-et-validation-locale)
15. [Dockerisation](#15-dockerisation)
16. [Connexion GitHub](#16-connexion-github)
17. [CI/CD avec GitHub Actions](#17-cicd-avec-github-actions)
18. [Déploiement sur Render](#18-déploiement-sur-render)
19. [Correctifs post-déploiement](#19-correctifs-post-déploiement)
20. [Résultat final](#20-résultat-final)

---

## 1. Contexte et objectifs

### Cahier des charges

Construire une plateforme de traitement de fichiers par IA avec les contraintes suivantes :

**Fonctionnel :**
- Upload de fichiers TXT ou PDF (max 5 MB)
- Traitement asynchrone (l'upload retourne immédiatement un `job_id`)
- 4 tâches IA : résumé, extraction de mots-clés, analyse de sentiment, question-réponse
- Récupération des résultats via `GET /result/{job_id}`
- Interface Gradio avec polling toutes les 2 secondes

**Technique :**
- Séparation stricte en 4 couches : API / Service / Processing / Storage
- Moteur IA interchangeable sans modifier les autres couches
- Les erreurs (fichier corrompu, échec d'inférence) ne doivent jamais crasher l'API
- Pas d'appel de modèle depuis Gradio
- Pas d'implémentation dans un seul fichier
- L'endpoint d'upload ne doit pas bloquer

**Interdits explicites :**
- Appels de modèle directs depuis Gradio
- Implémentation monofichier
- Endpoint d'upload synchrone et bloquant

---

## 2. Architecture choisie

```
Gradio UI  ──HTTP──►  FastAPI  ──BackgroundTask──►  Pipeline
                                                        │
                                          ┌─────────────┼─────────────┐
                                          ▼             ▼             ▼
                                      Validator   Preprocessor   Inference
                                                                    │
                                                         ┌──────────┴──────────┐
                                                         │                     │
                                                  HuggingFaceEngine       MockEngine
                                                         │
                                                    JobStore (Storage)
```

**Décisions d'architecture :**

| Décision | Justification |
|---|---|
| `BackgroundTasks` FastAPI | Retourne 202 immédiatement, traitement en arrière-plan |
| `ThreadPoolExecutor` | L'inférence torch est bloquante — il faut l'isoler du thread async |
| Classe abstraite `InferenceEngine` | Permet de swapper le moteur sans toucher aux autres couches |
| Singleton `job_store` | Partagé entre tous les threads, protégé par un `threading.Lock` |
| Moteur `mock` par défaut | Permet de développer et tester sans télécharger torch (~2 GB) |
| `pypdf` pour les PDF | Bibliothèque active, maintenue, pure Python |
| TF-IDF pour les mots-clés | Pas de modèle à télécharger, sklearn suffit |

---

## 3. Création de la structure de fichiers

### Commande exécutée

```powershell
New-Item -ItemType Directory -Force -Path "d:\Defit_IA\api"
New-Item -ItemType Directory -Force -Path "d:\Defit_IA\services"
New-Item -ItemType Directory -Force -Path "d:\Defit_IA\processing\inference"
New-Item -ItemType Directory -Force -Path "d:\Defit_IA\storage"
New-Item -ItemType Directory -Force -Path "d:\Defit_IA\ui"
```

### Structure finale

```
d:\Defit_IA\
├── api/
│   ├── __init__.py
│   ├── main.py            ← Routes FastAPI (POST /upload, GET /result)
│   └── schemas.py         ← Modèles Pydantic de réponse
├── services/
│   ├── __init__.py
│   ├── job_service.py     ← CRUD des jobs
│   └── pipeline_service.py ← Orchestration du pipeline
├── processing/
│   ├── __init__.py
│   ├── validator.py       ← Validation extension + taille + vide
│   ├── preprocessor.py    ← Extraction texte TXT/PDF
│   └── inference/
│       ├── __init__.py
│       ├── base.py        ← Classe abstraite InferenceEngine
│       ├── hf_engine.py   ← Implémentation HuggingFace
│       ├── mock_engine.py ← Implémentation factice (sans modèles)
│       └── factory.py     ← Singleton engine()
├── storage/
│   ├── __init__.py
│   └── job_store.py       ← Stockage en mémoire, thread-safe
├── ui/
│   └── gradio_app.py      ← Interface Gradio
├── config.py              ← Paramètres via pydantic-settings
├── main.py                ← Point d'entrée uvicorn
├── requirements.txt       ← Dépendances complètes (avec torch)
├── requirements.ui.txt    ← Dépendances UI uniquement (sans torch)
├── requirements.ci.txt    ← Dépendances CI légères (sans torch)
├── Dockerfile.api         ← Image Docker service API
├── Dockerfile.ui          ← Image Docker service UI
├── docker-compose.yml     ← Orchestration locale
├── .dockerignore
├── .gitignore
├── .gitattributes
├── .env / .env.example
├── render.yaml            ← Déploiement Render IaC
└── architecture.md        ← Diagramme ASCII complet
```

---

## 4. Couche Config

### Fichier : `config.py`

```python
from __future__ import annotations
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    max_file_size_mb: int = 5
    allowed_extensions: frozenset[str] = frozenset({".txt", ".pdf"})
    inference_engine: Literal["huggingface", "mock"] = "huggingface"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    gradio_port: int = 7860
    summarization_model: str = "sshleifer/distilbart-cnn-12-6"
    sentiment_model: str = "distilbert-base-uncased-finetuned-sst-2-english"
    qa_model: str = "deepset/minilm-uncased-squad2"

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Pourquoi `pydantic-settings` ?**
- Lit automatiquement le fichier `.env`
- Validation de types à l'import (ex : `inference_engine` ne peut valoir que `"huggingface"` ou `"mock"`)
- Pour changer de modèle, il suffit de modifier `.env` — aucun code à toucher

**Fichier `.env` (non versionné) :**
```env
INFERENCE_ENGINE=mock
SUMMARIZATION_MODEL=sshleifer/distilbart-cnn-12-6
SENTIMENT_MODEL=distilbert-base-uncased-finetuned-sst-2-english
QA_MODEL=deepset/minilm-uncased-squad2
MAX_FILE_SIZE_MB=5
API_HOST=0.0.0.0
API_PORT=8000
GRADIO_PORT=7860
```

**Fichier `.env.example` (versionné) :** copie du `.env` pour documenter les variables sans exposer de secrets.

---

## 5. Couche Storage

### Fichier : `storage/job_store.py`

```python
from __future__ import annotations
import time, uuid, threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"


@dataclass
class Job:
    job_id:     str
    task:       str
    status:     JobStatus = JobStatus.PENDING
    result:     Optional[str] = None
    error:      Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    """Stockage en mémoire, thread-safe. Remplacer par Redis/SQL sans changer le service layer."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, task: str) -> Job:
        job = Job(job_id=str(uuid.uuid4()), task=task)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = time.time()
            return job


job_store = JobStore()  # singleton partagé
```

**Points clés :**
- `threading.Lock()` : plusieurs threads (ThreadPoolExecutor) accèdent à `_jobs` en même temps
- `str(uuid.uuid4())` : identifiant unique non-devinable pour chaque job
- `**kwargs` dans `update()` : générique, pas besoin d'un setter par champ
- Le singleton `job_store` est importé par les services — pour passer à Redis, on remplace uniquement cette classe

---

## 6. Couche API — Schémas Pydantic

### Fichier : `api/schemas.py`

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel
from storage.job_store import JobStatus


class UploadResponse(BaseModel):
    job_id:  str
    status:  JobStatus
    message: str


class JobResult(BaseModel):
    job_id:  str
    status:  JobStatus
    task:    str
    result:  Optional[str] = None
    error:   Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str


AITask = Literal["summarize", "keywords", "sentiment", "qa"]
```

**Rôle :** définir la forme exacte des réponses JSON. FastAPI valide et sérialise automatiquement.

---

## 7. Couche Processing — Validation

### Fichier : `processing/validator.py`

```python
from __future__ import annotations
from fastapi import UploadFile
from config import settings


class ValidationError(Exception):
    pass


async def validate_file(file: UploadFile) -> bytes:
    """Valide extension et taille ; retourne les bytes bruts si OK."""
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix not in settings.allowed_extensions:
        raise ValidationError(
            f"Type de fichier '{suffix}' non supporté. Autorisés : {sorted(settings.allowed_extensions)}"
        )

    content = await file.read()

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationError(
            f"Fichier trop grand ({len(content)/1024/1024:.2f} MB). Limite : {settings.max_file_size_mb} MB."
        )

    if len(content) == 0:
        raise ValidationError("Le fichier uploadé est vide.")

    return content
```

**3 vérifications dans l'ordre :**
1. Extension (`.txt` ou `.pdf`)
2. Taille (< 5 MB)
3. Contenu vide

**Pourquoi une exception custom `ValidationError` ?** Pour distinguer les erreurs de validation (400) des erreurs serveur (500) dans la route FastAPI.

---

## 8. Couche Processing — Prétraitement

### Fichier : `processing/preprocessor.py`

```python
from __future__ import annotations
import io


class PreprocessingError(Exception):
    pass


def extract_text(content: bytes, filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "txt":
        return _extract_txt(content)
    if suffix == "pdf":
        return _extract_pdf(content)
    raise PreprocessingError(f"Impossible d'extraire le texte d'un '.{suffix}'.")


def _extract_txt(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = content.decode(encoding).strip()
            if text:
                return text
        except (UnicodeDecodeError, ValueError):
            continue
    raise PreprocessingError("Impossible de décoder le fichier texte.")


def _extract_pdf(content: bytes) -> str:
    try:
        import pypdf
    except ImportError as exc:
        raise PreprocessingError("pypdf requis pour les PDF.") from exc
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
    except Exception as exc:
        raise PreprocessingError(f"Échec de lecture du PDF : {exc}") from exc
    if not text:
        raise PreprocessingError("Le PDF ne contient pas de texte extractible (PDF image/scanné).")
    return text
```

**Choix techniques :**
- TXT : essai de 3 encodages successifs (`utf-8` → `latin-1` → `cp1252`) pour couvrir la majorité des fichiers Windows/Linux
- PDF : `pypdf` en import lazy (pas chargé si pas nécessaire)
- PDF image/scanné : détecté et rejeté avec message explicite

---

## 9. Couche Processing — Inférence IA

### 9.1 Classe abstraite — `processing/inference/base.py`

```python
from __future__ import annotations
from abc import ABC, abstractmethod


class InferenceEngine(ABC):
    @abstractmethod
    def summarize(self, text: str) -> str: ...

    @abstractmethod
    def extract_keywords(self, text: str) -> str: ...

    @abstractmethod
    def sentiment(self, text: str) -> str: ...

    @abstractmethod
    def answer_question(self, text: str, question: str) -> str: ...

    def run(self, task: str, text: str, question: str = "") -> str:
        dispatch = {
            "summarize": lambda: self.summarize(text),
            "keywords":  lambda: self.extract_keywords(text),
            "sentiment": lambda: self.sentiment(text),
            "qa":        lambda: self.answer_question(text, question),
        }
        handler = dispatch.get(task)
        if handler is None:
            raise ValueError(f"Tâche inconnue '{task}'.")
        return handler()
```

**Pattern Strategy via classe abstraite :** `run()` est le point d'entrée unique — le pipeline appelle toujours `engine().run(task, text, question)` sans connaître le moteur concret.

---

### 9.2 Moteur HuggingFace — `processing/inference/hf_engine.py`

```python
from __future__ import annotations
import math, re
from typing import Any
from processing.inference.base import InferenceEngine
from config import settings


class HuggingFaceEngine(InferenceEngine):
    """Chargement des modèles en lazy loading — téléchargés uniquement au premier appel."""

    def __init__(self) -> None:
        self._summarizer:    Any = None
        self._sentiment_pipe: Any = None
        self._qa_pipe:       Any = None

    def _get_summarizer(self):
        if self._summarizer is None:
            from transformers import pipeline
            self._summarizer = pipeline("summarization", model=settings.summarization_model, truncation=True)
        return self._summarizer

    def _get_sentiment(self):
        if self._sentiment_pipe is None:
            from transformers import pipeline
            self._sentiment_pipe = pipeline("sentiment-analysis", model=settings.sentiment_model)
        return self._sentiment_pipe

    def _get_qa(self):
        if self._qa_pipe is None:
            from transformers import pipeline
            self._qa_pipe = pipeline("question-answering", model=settings.qa_model)
        return self._qa_pipe

    def summarize(self, text: str) -> str:
        words = text.split()
        chunk = " ".join(words[:800])
        word_count = len(chunk.split())
        max_len = min(150, math.ceil(word_count * 0.4))
        min_len = min(40, max_len - 1)
        out = self._get_summarizer()(chunk, max_length=max_len, min_length=min_len, do_sample=False)
        return out[0]["summary_text"]

    def extract_keywords(self, text: str) -> str:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()] or [text]
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=500)
        try:
            tfidf = vectorizer.fit_transform(sentences)
        except ValueError:
            return "Impossible d'extraire les mots-clés."
        scores = np.asarray(tfidf.sum(axis=0)).flatten()
        feature_names = vectorizer.get_feature_names_out()
        top_idx = scores.argsort()[-15:][::-1]
        return ", ".join([feature_names[i] for i in top_idx])

    def sentiment(self, text: str) -> str:
        snippet = " ".join(text.split()[:400])
        out = self._get_sentiment()(snippet, truncation=True)[0]
        return f"{out['label'].capitalize()} (confidence: {out['score']:.2%})"

    def answer_question(self, text: str, question: str) -> str:
        if not question:
            return "Aucune question fournie pour la tâche Q&A."
        context = " ".join(text.split()[:500])
        out = self._get_qa()(question=question, context=context)
        return f"Réponse : {out['answer']} (confidence: {out['score']:.2%})"
```

**Modèles utilisés :**
| Tâche | Modèle | Taille approx. |
|---|---|---|
| Résumé | `sshleifer/distilbart-cnn-12-6` | ~900 MB |
| Sentiment | `distilbert-base-uncased-finetuned-sst-2-english` | ~260 MB |
| Q&A | `deepset/minilm-uncased-squad2` | ~130 MB |
| Mots-clés | TF-IDF (sklearn) | 0 MB |

---

### 9.3 Moteur Mock — `processing/inference/mock_engine.py`

```python
from __future__ import annotations
import time, random
from processing.inference.base import InferenceEngine


class MockEngine(InferenceEngine):
    """Moteur factice sans téléchargement. Utilisé avec INFERENCE_ENGINE=mock."""

    def summarize(self, text: str) -> str:
        time.sleep(0.5)
        return "[MOCK SUMMARY] " + " ".join(text.split()[:25]) + "..."

    def extract_keywords(self, text: str) -> str:
        time.sleep(0.3)
        sample = random.sample(text.split(), min(8, len(text.split())))
        return "[MOCK KEYWORDS] " + ", ".join(sample)

    def sentiment(self, text: str) -> str:
        time.sleep(0.2)
        label = random.choice(["Positive", "Negative", "Neutral"])
        return f"[MOCK] {label} (confidence: {random.uniform(0.7, 0.99):.2%})"

    def answer_question(self, text: str, question: str) -> str:
        time.sleep(0.4)
        snippet = " ".join(text.split()[2:7])
        return f"[MOCK] Réponse à '{question}' : {snippet}"
```

**Utilité :** développement local instantané, CI sans téléchargement de modèles.

---

### 9.4 Factory — `processing/inference/factory.py`

```python
from __future__ import annotations
from processing.inference.base import InferenceEngine

_engine: InferenceEngine | None = None


def get_engine() -> InferenceEngine:
    from config import settings
    if settings.inference_engine == "mock":
        from processing.inference.mock_engine import MockEngine
        return MockEngine()
    if settings.inference_engine == "huggingface":
        from processing.inference.hf_engine import HuggingFaceEngine
        return HuggingFaceEngine()
    raise ValueError(f"Moteur inconnu : '{settings.inference_engine}'")


def engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine
```

**Pour ajouter un nouveau moteur (ex : OpenAI) :**
1. Créer `processing/inference/openai_engine.py` qui hérite de `InferenceEngine`
2. Ajouter `if settings.inference_engine == "openai": ...` dans `get_engine()`
3. Mettre `INFERENCE_ENGINE=openai` dans `.env`

---

## 10. Couche Service

### 10.1 `services/job_service.py`

```python
from __future__ import annotations
from typing import Optional
from storage.job_store import Job, JobStatus, job_store


def create_job(task: str) -> Job:
    return job_store.create(task)

def get_job(job_id: str) -> Optional[Job]:
    return job_store.get(job_id)

def mark_running(job_id: str) -> None:
    job_store.update(job_id, status=JobStatus.RUNNING)

def mark_completed(job_id: str, result: str) -> None:
    job_store.update(job_id, status=JobStatus.COMPLETED, result=result)

def mark_failed(job_id: str, error: str) -> None:
    job_store.update(job_id, status=JobStatus.FAILED, error=error)
```

---

### 10.2 `services/pipeline_service.py`

```python
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from processing.preprocessor import PreprocessingError, extract_text
from processing.inference.factory import engine
from services import job_service

_executor = ThreadPoolExecutor(max_workers=4)


async def run_pipeline(job_id, file_content, filename, task, question="") -> None:
    loop = asyncio.get_event_loop()
    job_service.mark_running(job_id)
    try:
        # Stage 1 : Prétraitement (hors thread async)
        text = await loop.run_in_executor(_executor, extract_text, file_content, filename)
        # Stage 2 : Inférence IA (CPU-bound, thread pool)
        result = await loop.run_in_executor(_executor, _run_inference, task, text, question)
        # Stage 3 : Persistance du résultat
        job_service.mark_completed(job_id, result)
    except PreprocessingError as exc:
        job_service.mark_failed(job_id, f"Prétraitement échoué : {exc}")
    except Exception as exc:
        job_service.mark_failed(job_id, f"Inférence échouée : {exc}")


def _run_inference(task: str, text: str, question: str) -> str:
    return engine().run(task, text, question)
```

**Pourquoi `ThreadPoolExecutor` ?**
- FastAPI est async, mais `transformers` (PyTorch) est synchrone et bloquant
- `loop.run_in_executor()` exécute le code bloquant dans un thread séparé sans bloquer la boucle d'événements asyncio
- `max_workers=4` : 4 jobs peuvent tourner en parallèle

---

## 11. Couche API — Routes FastAPI

### Fichier : `api/main.py`

```python
from __future__ import annotations
from typing import Annotated, Optional
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from api.schemas import AITask, ErrorResponse, JobResult, UploadResponse
from processing.validator import ValidationError, validate_file
from services import job_service
from services.pipeline_service import run_pipeline
from storage.job_store import JobStatus

app = FastAPI(title="AI File Processing Pipeline", version="1.0.0")


@app.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    task: Annotated[AITask, Form()] = "summarize",
    question: Annotated[Optional[str], Form()] = "",
):
    try:
        content = await validate_file(file)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job = job_service.create_job(task)

    background_tasks.add_task(
        run_pipeline,
        job_id=job.job_id,
        file_content=content,
        filename=file.filename or "upload.txt",
        task=task,
        question=question or "",
    )

    return UploadResponse(job_id=job.job_id, status=JobStatus.PENDING,
                          message="Fichier accepté. Sondez /result/{job_id}.")


@app.get("/result/{job_id}", response_model=JobResult)
def get_result(job_id: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' introuvable.")
    return JobResult(job_id=job.job_id, status=job.status, task=job.task,
                     result=job.result, error=job.error)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
```

**Points clés :**
- `status_code=202` : "Accepted" — indique que la requête est acceptée mais pas encore traitée
- `background_tasks.add_task()` : FastAPI enregistre la tâche et répond **avant** qu'elle commence
- La validation est faite **dans** l'endpoint (synchrone, rapide) avant de lancer le background task
- `/health` exclu du schéma OpenAPI (n'apparaît pas dans `/docs`)

### Point d'entrée : `main.py`

```python
import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
```

---

## 12. Interface Gradio

### Fichier : `ui/gradio_app.py`

```python
from __future__ import annotations
import os, time
import httpx
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
POLL_INTERVAL = 2  # secondes


def process_file(file, task: str, question: str) -> tuple[str, str]:
    if file is None:
        return "Aucun fichier sélectionné.", ""

    # Upload
    with open(file.name, "rb") as f:
        filename = file.name.replace("\\", "/").split("/")[-1]
        mime = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
        try:
            resp = httpx.post(f"{API_BASE}/upload",
                              files={"file": (filename, f, mime)},
                              data={"task": task, "question": question or ""},
                              timeout=30)
        except httpx.ConnectError:
            return "Impossible de joindre le serveur API.", ""

    if resp.status_code != 202:
        return f"Upload échoué ({resp.status_code}) : {resp.text}", ""

    job_id = resp.json()["job_id"]

    # Polling toutes les 2 secondes
    while True:
        time.sleep(POLL_INTERVAL)
        poll = httpx.get(f"{API_BASE}/result/{job_id}", timeout=10)
        data = poll.json()
        status = data["status"]
        status_msg = f"Job : {job_id}\nStatut : {status}"
        if status == "COMPLETED":
            return status_msg, data.get("result", "")
        if status == "FAILED":
            return status_msg, f"Erreur : {data.get('error', '')}"


# Layout
with gr.Blocks(title="AI File Processor") as demo:
    # ... widgets ...

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False, theme=gr.themes.Soft())
```

**Points importants :**
- `API_BASE` lu depuis l'environnement → `http://127.0.0.1:8000` en local, `http://api:8000` en Docker, `https://defit-api.onrender.com` sur Render
- `server_name="0.0.0.0"` : obligatoire en Docker (sinon l'interface n'est accessible que de l'intérieur du container)
- `port = int(os.getenv("PORT", 7860))` : Render injecte `$PORT` dynamiquement
- `theme` déplacé dans `launch()` (breaking change Gradio 6.0)

---

## 13. Installation des dépendances

### Commandes exécutées

```powershell
# Dépendances principales (sans torch)
& "d:\Defit_IA\venv\Scripts\pip.exe" install `
    fastapi uvicorn[standard] python-multipart `
    pydantic pydantic-settings `
    pypdf gradio httpx scikit-learn

# PyTorch CPU uniquement (évite la version GPU de 5 GB)
& "d:\Defit_IA\venv\Scripts\pip.exe" install torch `
    --index-url https://download.pytorch.org/whl/cpu

# Transformers HuggingFace
& "d:\Defit_IA\venv\Scripts\pip.exe" install transformers
```

### Pourquoi 3 fichiers requirements ?

| Fichier | Contenu | Utilisé par |
|---|---|---|
| `requirements.txt` | Tout (torch inclus) | `Dockerfile.api` |
| `requirements.ui.txt` | Gradio + httpx seulement | `Dockerfile.ui` |
| `requirements.ci.txt` | Pas de torch (trop lourd pour CI) | `ci.yml` GitHub Actions |

---

## 14. Tests et validation locale

### Vérification des imports

```powershell
& "d:\Defit_IA\venv\Scripts\python.exe" -c "
from config import settings
from storage.job_store import job_store, JobStatus
from processing.validator import validate_file
from processing.preprocessor import extract_text
from processing.inference.base import InferenceEngine
from processing.inference.mock_engine import MockEngine
from processing.inference.factory import engine
from services.job_service import create_job, get_job, mark_completed
from api.schemas import UploadResponse, JobResult
print('Tous les imports OK')
print(f'Moteur configuré : {settings.inference_engine}')
"
```

### Test du moteur mock

```powershell
& "d:\Defit_IA\venv\Scripts\python.exe" -c "
from processing.inference.mock_engine import MockEngine
e = MockEngine()
print(e.run('summarize', 'Test document about AI.'))
print(e.run('sentiment', 'I love this product!'))
print(e.run('keywords', 'Machine learning deep learning neural network'))
"
```

### Test du cycle de vie d'un job

```powershell
& "d:\Defit_IA\venv\Scripts\python.exe" -c "
from services.job_service import create_job, mark_completed, get_job
from storage.job_store import JobStatus
job = create_job('summarize')
print('Créé :', job.job_id, job.status)
mark_completed(job.job_id, 'Résultat de test')
j = get_job(job.job_id)
print('Statut :', j.status, '| Résultat :', j.result)
"
```

### Test API end-to-end (serveur démarré)

```powershell
# Terminal 1 : démarrer le serveur
& "d:\Defit_IA\venv\Scripts\python.exe" main.py

# Terminal 2 : tester l'API
& "d:\Defit_IA\venv\Scripts\python.exe" -c @"
import httpx, time, json

base = 'http://127.0.0.1:8000'

# Health check
print(httpx.get(base + '/health').json())

# Upload
txt = b'AI transforms industries. ML automates decisions across healthcare and finance.'
r = httpx.post(base + '/upload',
    files={'file': ('test.txt', txt, 'text/plain')},
    data={'task': 'keywords'}, timeout=15)
print('Status upload :', r.status_code)
job_id = r.json()['job_id']

# Polling
for _ in range(15):
    time.sleep(1)
    r = httpx.get(base + '/result/' + job_id)
    s = r.json()['status']
    print('Statut :', s)
    if s in ('COMPLETED', 'FAILED'):
        print(json.dumps(r.json(), indent=2))
        break
"@
```

### Tests des cas d'erreur

```powershell
& "d:\Defit_IA\venv\Scripts\python.exe" -c @"
import httpx

base = 'http://127.0.0.1:8000'

# Mauvais type de fichier
r = httpx.post(base + '/upload',
    files={'file': ('doc.docx', b'data', 'application/octet-stream')},
    data={'task': 'summarize'})
print('Mauvais type :', r.status_code, r.json())

# Fichier trop grand (6 MB)
r = httpx.post(base + '/upload',
    files={'file': ('big.txt', b'a'*(6*1024*1024), 'text/plain')},
    data={'task': 'summarize'}, timeout=15)
print('Trop grand :', r.status_code, r.json())

# Job inexistant
r = httpx.get(base + '/result/id-inexistant')
print('Non trouvé :', r.status_code, r.json())
"@
```

**Résultats obtenus :**
```
Mauvais type : 400 {'detail': "Type '.docx' non supporté. Autorisés : ['.pdf', '.txt']"}
Trop grand   : 400 {'detail': 'Fichier trop grand (6.00 MB). Limite : 5 MB.'}
Non trouvé   : 404 {'detail': "Job 'id-inexistant' introuvable."}
```

---

## 15. Dockerisation

### 15.1 `Dockerfile.api`

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances en premier (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Code source
COPY api/ api/
COPY services/ services/
COPY processing/ processing/
COPY storage/ storage/
COPY config.py main.py .

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# $PORT injecté par Render ; fallback 8000 pour Docker Compose local
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### 15.2 `Dockerfile.ui`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.ui.txt .
RUN pip install --no-cache-dir -r requirements.ui.txt

COPY ui/ ui/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 API_BASE=http://api:8000

EXPOSE 7860

CMD ["sh", "-c", "PORT=${PORT:-7860} python ui/gradio_app.py"]
```

### 15.3 `docker-compose.yml`

```yaml
services:

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - hf_cache:/root/.cache/huggingface  # modèles persistés entre les runs
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
    restart: unless-stopped

  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports:
      - "7860:7860"
    environment:
      - API_BASE=http://api:8000   # nom du service dans le réseau Docker interne
    depends_on:
      api:
        condition: service_healthy  # attend que l'API soit prête
    restart: unless-stopped

volumes:
  hf_cache:
```

### 15.4 `.dockerignore`

```
__pycache__/
*.pyc *.pyo *.pyd *.egg-info/
venv/ .venv/ env/
.env *.env.local
.cache/
.vscode/ .idea/
.git/ .gitignore
contexte/
```

### 15.5 Commandes Docker

```powershell
# Construire et lancer
docker compose up --build

# En arrière-plan
docker compose up --build -d

# Logs en temps réel
docker compose logs -f

# Logs d'un seul service
docker compose logs -f api

# Arrêter
docker compose down

# Arrêter + supprimer le volume des modèles
docker compose down -v

# Rebuild d'un seul service
docker compose up --build api
```

---

## 16. Connexion GitHub

### Dépôt : https://github.com/ZarcDmC01/Defit_CI-CD

### Commandes exécutées

```powershell
# Git était déjà initialisé ; configuration de l'identité
git -C "d:\Defit_IA" config user.email "jessesteven26@gmail.com"
git -C "d:\Defit_IA" config user.name "ZarcDmC01"

# Ajout du remote
git -C "d:\Defit_IA" remote add origin https://github.com/ZarcDmC01/Defit_CI-CD.git

# Vérification que le dépôt distant est vide
git -C "d:\Defit_IA" ls-remote origin
# (aucune sortie = dépôt vide)
```

### `.gitignore` créé

```gitignore
__pycache__/ *.pyc *.pyo *.pyd *.egg-info/
venv/ .venv/ env/
.env *.env.local
.cache/
.vscode/ .idea/
.DS_Store Thumbs.db
*.tar
```

### `.gitattributes` créé

```
* text=auto eol=lf
```

Normalise les fins de ligne en LF sur tous les OS (évite les warnings `CRLF → LF` sur Windows).

### Premier commit et push

```powershell
git -C "d:\Defit_IA" add .dockerignore .env.example .gitattributes .github/ .gitignore `
    Dockerfile.api Dockerfile.ui docker-compose.yml main.py config.py `
    requirements.txt requirements.ui.txt requirements.ci.txt architecture.md `
    api/ services/ processing/ storage/ ui/

git -C "d:\Defit_IA" commit -m @'
feat: initial commit — AI File Processing Pipeline

FastAPI async backend + Gradio UI + Docker Compose.
4-layer architecture: API / Service / Processing / Storage.
Swappable HuggingFace/mock inference engine via .env.
CI workflow with syntax check, import test, and Docker build.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@

git -C "d:\Defit_IA" push -u origin main
```

---

## 17. CI/CD avec GitHub Actions

### Contexte

Le dépôt contenait déjà `.github/workflows/` avec :
- `ci.yml` : CI sur branches `Jesse`, `Simo`, `Matthieu` → inadapté (projet solo)
- `auto-pr.yml` : création automatique de PR → inutile en solo
- `autowatcher.py` : watcher local surveillant `FastAPI_UI.py` → fichier inexistant

### Modifications apportées

**`auto-pr.yml` — supprimé**
```powershell
Remove-Item "d:\Defit_IA\.github\workflows\auto-pr.yml" -Force
```

**`ci.yml` — réécrit**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Installer les dépendances
        run: pip install -r requirements.ci.txt   # sans torch

      - name: Vérifier la syntaxe Python
        run: find . -name "*.py" -not -path "./.github/*" -not -path "./venv/*"
             -exec python -m py_compile {} \;

      - name: Vérifier les imports critiques (moteur mock)
        env:
          INFERENCE_ENGINE: mock
        run: |
          python -c "
          from processing.inference.mock_engine import MockEngine
          e = MockEngine()
          assert 'MOCK' in e.summarize('hello world')
          print('OK')
          "

      - name: Test pipeline complet
        env:
          INFERENCE_ENGINE: mock
        run: |
          python -c "
          from services.job_service import create_job, mark_completed, get_job
          from storage.job_store import JobStatus
          job = create_job('summarize')
          mark_completed(job.job_id, 'test')
          assert get_job(job.job_id).status == JobStatus.COMPLETED
          print('OK')
          "

  docker-build:
    runs-on: ubuntu-latest
    needs: check
    steps:
      - uses: actions/checkout@v4
      - run: docker build -f Dockerfile.api -t defit-api:ci .
      - run: docker build -f Dockerfile.ui -t defit-ui:ci .
```

**`autowatcher.py` — mis à jour**

Avant : surveillait uniquement `FastAPI_UI.py` (fichier inexistant).
Après : surveille toutes les extensions `.py`, `.yml`, `.txt`, `.env.example`, en excluant `venv/`, `.git/`, `__pycache__/`.

```powershell
# Démarrage du watcher (optionnel, développement local)
& "d:\Defit_IA\venv\Scripts\python.exe" .github/workflows/autowatcher.py
```

### Commit

```powershell
git -C "d:\Defit_IA" add .github/workflows/ci.yml
git -C "d:\Defit_IA" rm .github/workflows/auto-pr.yml
git -C "d:\Defit_IA" commit -m @'
ci: simplify workflows for solo dev — trigger on main only

Remove auto-pr.yml (not needed alone).
CI now runs on every push/PR to main.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
git -C "d:\Defit_IA" push
```

### Pipeline CI résultant

```
Push sur main
     │
     ▼
  job: check
  ├── pip install requirements.ci.txt
  ├── py_compile sur tous les .py
  ├── test imports + moteur mock
  └── test cycle de vie d'un job
     │
     ▼ (si check OK)
  job: docker-build
  ├── docker build Dockerfile.api
  └── docker build Dockerfile.ui
```

---

## 18. Déploiement sur Render

### `render.yaml` créé (Infrastructure as Code)

```yaml
services:
  - type: web
    name: defit-api
    runtime: docker
    dockerfilePath: ./Dockerfile.api
    dockerContext: .
    branch: main
    autoDeploy: true
    envVars:
      - key: INFERENCE_ENGINE
        value: mock

  - type: web
    name: defit-ui
    runtime: docker
    dockerfilePath: ./Dockerfile.ui
    dockerContext: .
    branch: main
    autoDeploy: true
    envVars:
      - key: API_BASE
        value: https://defit-api.onrender.com
```

### Adaptation des ports pour Render

Render injecte une variable `$PORT` dynamique (valeur typique : `10000`).
Le container doit écouter sur ce port.

**`Dockerfile.api`** — avant :
```dockerfile
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Après :
```dockerfile
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**`Dockerfile.ui`** — avant :
```dockerfile
CMD ["python", "ui/gradio_app.py"]
```
Après :
```dockerfile
CMD ["sh", "-c", "PORT=${PORT:-7860} python ui/gradio_app.py"]
```

**`ui/gradio_app.py`** — avant :
```python
demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
```
Après :
```python
port = int(os.getenv("PORT", 7860))
demo.launch(server_name="0.0.0.0", server_port=port, share=False, theme=gr.themes.Soft())
```

### Paramètres Render — Service API (New Web Service)

| Champ | Valeur |
|---|---|
| Source | GitHub → ZarcDmC01/Defit_CI-CD |
| Name | `defit-api` |
| Branch | `main` |
| Runtime | Docker |
| Dockerfile Path | `./Dockerfile.api` |
| Docker Context | `.` |
| Instance Type | Free |
| `INFERENCE_ENGINE` (env var) | `mock` |

### Paramètres Render — Service UI (New Web Service)

| Champ | Valeur |
|---|---|
| Source | GitHub → ZarcDmC01/Defit_CI-CD |
| Name | `defit-ui` |
| Branch | `main` |
| Runtime | Docker |
| Dockerfile Path | `./Dockerfile.ui` |
| Docker Context | `.` |
| Instance Type | Free |
| `API_BASE` (env var) | `https://defit-api.onrender.com` |

### Commit

```powershell
git -C "d:\Defit_IA" add Dockerfile.api Dockerfile.ui ui/gradio_app.py render.yaml
git -C "d:\Defit_IA" commit -m @'
feat: add Render deployment support

- Dockerfiles use ${PORT:-default} for Render compatibility
- Gradio reads PORT env var dynamically
- Add render.yaml for IaC deployment (two services: api + ui)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
git -C "d:\Defit_IA" push
```

---

## 19. Correctifs post-déploiement

### Warning Gradio 6.0

**Symptôme observé dans les logs Render :**
```
UserWarning: The parameters have been moved from the Blocks constructor
to the launch() method in Gradio 6.0: theme.
```

**Cause :** Gradio 6.0 a déplacé `theme` de `gr.Blocks()` vers `launch()`.

**Correction dans `ui/gradio_app.py` :**

Avant :
```python
with gr.Blocks(title="AI File Processor", theme=gr.themes.Soft()) as demo:
    ...
demo.launch(server_name="0.0.0.0", server_port=port, share=False)
```

Après :
```python
with gr.Blocks(title="AI File Processor") as demo:
    ...
demo.launch(server_name="0.0.0.0", server_port=port, share=False, theme=gr.themes.Soft())
```

**Commit :**
```powershell
git -C "d:\Defit_IA" add ui/gradio_app.py
git -C "d:\Defit_IA" commit -m @'
fix: move theme param to launch() for Gradio 6.0 compatibility

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
git -C "d:\Defit_IA" push
```

Render redéploie automatiquement dès la réception du push.

---

## 20. Résultat final

### URLs de production

| Service | URL |
|---|---|
| Interface Gradio (UI) | https://defit-ci-cd.onrender.com |
| API FastAPI | https://defit-api.onrender.com |
| Documentation API (Swagger) | https://defit-api.onrender.com/docs |
| Health check | https://defit-api.onrender.com/health |

### Historique des commits

```
fbc752b  fix: move theme param to launch() for Gradio 6.0 compatibility
5932849  feat: add Render deployment support
30ef6c4  ci: simplify workflows for solo dev — trigger on main only
1232a32  feat: initial commit — AI File Processing Pipeline
```

### Flux de déploiement continu

```
Modification locale
       │
       ▼
  git add + commit + push
       │
       ▼
  GitHub (branche main)
       │
       ├──► GitHub Actions CI
       │      ├── syntaxe Python
       │      ├── imports + mock engine
       │      ├── pipeline job test
       │      └── docker build (api + ui)
       │
       └──► Render (auto-deploy)
              ├── rebuild image Docker
              └── redéploiement sans downtime
```

### Pour démarrer en local

```powershell
# Option 1 — Python direct
& "d:\Defit_IA\venv\Scripts\python.exe" main.py          # Terminal 1 (API)
& "d:\Defit_IA\venv\Scripts\python.exe" ui\gradio_app.py # Terminal 2 (UI)

# Option 2 — Docker Compose
docker compose up --build
```

### Pour switcher vers les vrais modèles IA

Modifier `.env` :
```env
INFERENCE_ENGINE=huggingface
```

Premier lancement : téléchargement des modèles (~1.3 GB, mis en cache dans le volume `hf_cache`).
Les lancements suivants utilisent le cache.
