"""faster-whisper transcription engine, tuned for AMD Ryzen 7 PRO 8840U (CPU).

The 8840U exposes AVX512 + VNNI + BF16, so int8 quantization via CTranslate2 is
the fastest accurate option on CPU. We pin cpu_threads to the 8 physical cores.

Model size, compute type, language, beam size and VAD are now selectable per
request from the UI. Defaults below are the combo that works best on THIS PC.
"""

from __future__ import annotations

import gc
import threading
from dataclasses import dataclass

from faster_whisper import WhisperModel

# --- Defaults tuned for this machine ----------------------------------------
DEFAULT_MODEL = "large-v3"
DEFAULT_COMPUTE_TYPE = "int8"   # leverages AVX512-VNNI on the 8840U
DEFAULT_LANGUAGE = "en"         # "auto" lets faster-whisper detect it
DEFAULT_BEAM_SIZE = 5
DEFAULT_VAD = True
CPU_THREADS = 8                 # physical cores
DEVICE = "cpu"
NUM_WORKERS = 1

# --- Catalog: metadata shown in the UI / docs page --------------------------
MODELS: dict[str, dict] = {
    "tiny": {
        "params": "39M", "ram": "~0.4 GB", "rel_speed": "~10x",
        "blurb": "Fastest, lowest accuracy. Good for quick drafts or testing.",
    },
    "base": {
        "params": "74M", "ram": "~0.6 GB", "rel_speed": "~7x",
        "blurb": "A small step up from tiny; still very fast, modest accuracy.",
    },
    "small": {
        "params": "244M", "ram": "~1.2 GB", "rel_speed": "~4x",
        "blurb": "Balanced speed/quality for clean audio in major languages.",
    },
    "medium": {
        "params": "769M", "ram": "~2.6 GB", "rel_speed": "~2x",
        "blurb": "Strong accuracy, noticeably slower. Solid all-rounder.",
    },
    "large-v2": {
        "params": "1550M", "ram": "~4.7 GB", "rel_speed": "1x",
        "blurb": "Previous flagship. Very accurate; large-v3 usually beats it.",
    },
    "large-v3": {
        "params": "1550M", "ram": "~4.7 GB", "rel_speed": "1x",
        "blurb": "Best accuracy, including accents/noise. The default here.",
    },
    "distil-large-v3": {
        "params": "756M", "ram": "~2.6 GB", "rel_speed": "~4x",
        "blurb": "Distilled large-v3: near-large accuracy, much faster. English-focused.",
    },
}

COMPUTE_TYPES: dict[str, str] = {
    "int8": "8-bit quantized. Fastest on this CPU (uses AVX512-VNNI), lowest RAM. Default.",
    "int8_float32": "int8 weights with float32 compute. Slightly more accurate, a bit slower.",
    "float32": "Full precision. Most accurate, slowest, highest RAM.",
}

LANGUAGES: dict[str, str] = {
    "auto": "Auto-detect", "en": "English", "es": "Spanish", "fr": "French",
    "de": "German", "pt": "Portuguese", "it": "Italian", "ja": "Japanese",
}

ALLOWED_MODELS = set(MODELS)
ALLOWED_COMPUTE = set(COMPUTE_TYPES)
ALLOWED_LANGS = set(LANGUAGES)


@dataclass
class Segment:
    start: float
    end: float
    text: str


# --- Single-slot model cache (one model in RAM at a time -> no OOM) ----------
_model: WhisperModel | None = None
_model_key: tuple | None = None
_model_lock = threading.Lock()
_transcribe_lock = threading.Lock()  # CPU is the bottleneck: one job at a time


def get_model(model_size: str, compute_type: str) -> WhisperModel:
    """Load (and cache) the requested model. Evicts the previous one to save RAM."""
    global _model, _model_key
    key = (model_size, compute_type, CPU_THREADS)
    if _model_key == key and _model is not None:
        return _model
    with _model_lock:
        if _model_key == key and _model is not None:
            return _model
        # Drop the old model before loading a new one.
        _model = None
        _model_key = None
        gc.collect()
        _model = WhisperModel(
            model_size,
            device=DEVICE,
            compute_type=compute_type,
            cpu_threads=CPU_THREADS,
            num_workers=NUM_WORKERS,
        )
        _model_key = key
    return _model


def _fmt_ts(seconds: float) -> str:
    """Format seconds as [mm:ss] (or [hh:mm:ss] past one hour)."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"[{h:02d}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"


def transcribe(
    audio_path: str,
    *,
    model_size: str = DEFAULT_MODEL,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    language: str = DEFAULT_LANGUAGE,
    beam_size: int = DEFAULT_BEAM_SIZE,
    vad: bool = DEFAULT_VAD,
    progress=None,
) -> dict:
    """Transcribe an audio/video file with the selected options.

    Returns a dict with:
      - segments: list of {start, end, text}
      - block: copy/paste string, one "[mm:ss] text" line per segment
      - info: {language, language_probability, duration} + the options used
    """
    # Validate / clamp inputs.
    if model_size not in ALLOWED_MODELS:
        raise ValueError(f"unknown model '{model_size}'")
    if compute_type not in ALLOWED_COMPUTE:
        raise ValueError(f"unknown compute_type '{compute_type}'")
    if language not in ALLOWED_LANGS:
        raise ValueError(f"unsupported language '{language}'")
    beam_size = max(1, min(int(beam_size), 10))
    lang_arg = None if language == "auto" else language

    model = get_model(model_size, compute_type)

    with _transcribe_lock:
        segments_iter, info = model.transcribe(
            audio_path,
            language=lang_arg,
            beam_size=beam_size,
            vad_filter=vad,
        )

        segments: list[Segment] = []
        lines: list[str] = []
        for seg in segments_iter:
            text = seg.text.strip()
            segments.append(Segment(seg.start, seg.end, text))
            lines.append(f"{_fmt_ts(seg.start)} {text}")
            if progress is not None:
                progress(seg.end, info.duration)

    return {
        "segments": [s.__dict__ for s in segments],
        "block": "\n".join(lines),
        "info": {
            "model": model_size,
            "compute_type": compute_type,
            "beam_size": beam_size,
            "vad": vad,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
        },
    }
