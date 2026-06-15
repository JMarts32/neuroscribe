# NEUROSCRIBE

Cyberpunk local transcription app. Drop an audio/video file → faster-whisper
(`large-v3`, int8, CPU) → copy/paste block with `[mm:ss]` timestamps.

Part of a larger YouTube-video creation workflow (a Chrome extension is planned
later but not built yet).

## Options

The UI exposes selectable options (model size, compute type, language, beam size,
VAD). A **↺ DEFAULTS (this PC)** button restores the tuned combo below, and a docs
page at **`/docs`** explains every model and option.

Model is held in a single RAM slot — switching models evicts the previous one, so
you never OOM (important on 14 GB). First use of a new size downloads it once.

## Default tuning for this machine

AMD Ryzen 7 PRO 8840U (8 cores / 16 threads, AVX512-VNNI):

| Setting        | Value      | Why                                   |
|----------------|------------|---------------------------------------|
| model          | `large-v3` | best accuracy                         |
| device         | `cpu`      | iGPU not supported by CTranslate2     |
| compute_type   | `int8`     | uses AVX512-VNNI → fastest on this CPU|
| cpu_threads    | `8`        | physical cores                        |
| language       | `en`       | forced English                        |
| beam_size      | `5`        | accuracy/speed balance                |
| vad_filter     | `on`       | skips silence, faster + cleaner       |

## Run

```bash
./run.sh
# then open http://127.0.0.1:8000
```

First run downloads `large-v3` (~3 GB) from Hugging Face once; it's cached
afterwards in `~/.cache/huggingface`.

## Layout

```
backend/
  main.py        FastAPI: upload → background job → progress polling
  transcribe.py  faster-whisper engine + tuning
frontend/
  index.html     cyberpunk UI
  style.css
  app.js
run.sh           launcher
```
