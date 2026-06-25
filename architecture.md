# Architecture Diagram — AI File Processing Pipeline

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                            │
│                                                                     │
│   ┌──────────────────────┐        ┌───────────────────────────┐    │
│   │    Gradio UI          │        │   External HTTP Client    │    │
│   │  (port 7860)          │        │   (curl / Postman / etc.) │    │
│   │                       │        │                           │    │
│   │  • File upload widget │        │  POST /upload             │    │
│   │  • Task selector      │        │  GET  /result/{job_id}    │    │
│   │  • 2-sec poll loop    │        │                           │    │
│   └──────────┬───────────┘        └────────────┬──────────────┘    │
└──────────────┼──────────────────────────────────┼───────────────────┘
               │ HTTP (httpx)                      │ HTTP
               ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYER  (FastAPI)                       │
│                                                                     │
│   POST /upload ──► validates form ──► returns 202 + job_id         │
│   GET  /result/{job_id} ──► reads job store ──► returns JSON       │
│                                                                     │
│   api/main.py  ·  api/schemas.py                                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ BackgroundTask (non-blocking)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                                │
│                                                                     │
│  ┌───────────────────────┐    ┌─────────────────────────────────┐  │
│  │   JobService           │    │   PipelineService               │  │
│  │                        │    │                                 │  │
│  │  create_job()          │    │  run_pipeline() ─── async      │  │
│  │  get_job()             │    │    │                            │  │
│  │  mark_running()        │    │    ├─► Stage 1: Preprocess      │  │
│  │  mark_completed()      │    │    ├─► Stage 2: Inference       │  │
│  │  mark_failed()         │    │    └─► Stage 3: Store result    │  │
│  └───────────────────────┘    └─────────────────────────────────┘  │
│                                   (runs in ThreadPoolExecutor)      │
│  services/job_service.py  ·  services/pipeline_service.py          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
┌──────────────────┐ ┌─────────────────┐ ┌────────────────────────────┐
│  PROCESSING      │ │  PROCESSING     │ │  PROCESSING                │
│  Validator       │ │  Preprocessor   │ │  Inference Layer           │
│                  │ │                 │ │                            │
│ • Extension check│ │ • TXT decode    │ │  ┌──────────────────────┐ │
│ • Size check     │ │ • PDF extract   │ │  │  InferenceEngine     │ │
│ • Empty check    │ │   (pypdf)       │ │  │  (Abstract Base)     │ │
│                  │ │                 │ │  └──────────┬───────────┘ │
│ processing/      │ │ processing/     │ │             │             │
│ validator.py     │ │ preprocessor.py │ │   ┌─────────┴──────────┐ │
└──────────────────┘ └─────────────────┘ │   │                    │ │
                                         │  HuggingFaceEngine  MockEngine│
                                         │   │                    │ │
                                         │   │  • summarize()     │ │
                                         │   │  • keywords()      │ │
                                         │   │  • sentiment()     │ │
                                         │   │  • answer_question │ │
                                         │   └────────────────────┘ │
                                         │  processing/inference/   │
                                         └────────────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                                │
│                                                                     │
│   JobStore  (in-memory, thread-safe)                                │
│                                                                     │
│   job_id ──► Job { status, task, result, error, timestamps }       │
│                                                                     │
│   Swappable: replace job_store singleton with Redis/SQL adapter     │
│   without changing any service-layer code.                          │
│                                                                     │
│   storage/job_store.py                                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Request Lifecycle

```
Client                 FastAPI             Background          JobStore
  │                      │                  Worker               │
  │── POST /upload ──────►│                    │                  │
  │                       │── validate file    │                  │
  │                       │── create_job() ───────────────────────►│
  │◄── 202 {job_id} ──────│                    │                  │
  │                       │── schedule task ───►│                  │
  │                       │                    │── mark_running() ─►│
  │── GET /result ────────►│                    │                  │
  │◄── {RUNNING} ─────────│                    │── preprocess      │
  │                       │                    │── inference       │
  │── GET /result ────────►│                    │── mark_done() ───►│
  │◄── {COMPLETED, ...} ──│                    │                  │
```

## Layer Responsibilities

| Layer      | Module(s)                          | Responsibility                          |
|------------|------------------------------------|-----------------------------------------|
| API        | api/main.py, api/schemas.py        | HTTP routing, input parsing, response   |
| Service    | services/job_service.py            | Job CRUD — no business logic            |
|            | services/pipeline_service.py       | Pipeline orchestration, error catching  |
| Processing | processing/validator.py            | File type + size enforcement            |
|            | processing/preprocessor.py        | Text extraction (TXT/PDF)               |
|            | processing/inference/*             | AI task execution; engine-swappable     |
| Storage    | storage/job_store.py               | Job persistence; swap without rewiring  |
| UI         | ui/gradio_app.py                   | Browser frontend; calls API only        |

## Model Swappability

To swap the inference model:
1. Change `INFERENCE_ENGINE=mock` → `INFERENCE_ENGINE=huggingface` in `.env`, **or**
2. Change specific model IDs (`SUMMARIZATION_MODEL`, `SENTIMENT_MODEL`, `QA_MODEL`), **or**
3. Implement a new `InferenceEngine` subclass and register it in `factory.py`.

No changes needed in API, service, or storage layers.
