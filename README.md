# Vaaku

Indic speech bench. The measured comparison below is Whisper Small, the Vaakku LoRA on that checkpoint, and Meta MMS on the same clips.

## Results

Official **FLEURS Hindi test**, clean audio, **418** clips, **10,326** reference words. Micro-averaged word error, character error, and sentence error. Scored on an NVIDIA A10G. Lower is better. Whisper Small is the base model. Vaakku is a LoRA on that checkpoint (`rudra11/vaakku-whisper-small`). Meta MMS is a separate system.

![Hindi FLEURS word and character error for Whisper Small, Vaakku, and Meta MMS](results/hindi-fleurs-error.png)

| Model | Checkpoint | WER | Versus base | CER | Versus base | Sentence error |
|---|---|---:|---:|---:|---:|---:|
| Whisper Small | `openai/whisper-small` | 66.4% | base | 37.0% | base | 100% |
| Vaakku | `rudra11/vaakku-whisper-small` | 40.7% | −25.6 pp, 38.6% lower | 17.3% | −19.7 pp, 53.3% lower | 100% |
| Meta MMS | `facebook/mms-1b-all` | 19.7% | −46.7 pp, 70.3% lower | 6.8% | −30.3 pp, 81.7% lower | 96.9% |

“Versus base” is the change from Whisper Small on these same clips. Percentage points are the absolute gap. The percent beside them is the relative reduction. Sentence error is the share of clips that are not an exact match after normalization, so 100% means every sentence still had at least one edit.

Edits on those 10,326 words:

| Model | Substitutions | Deletions | Insertions |
|---|---:|---:|---:|
| Whisper Small | 4,975 | 743 | 1,135 |
| Vaakku | 3,535 | 416 | 256 |
| Meta MMS | 1,711 | 195 | 128 |

The row-level rates are in `results/fleurs_hi_test.csv`. Whisper Medium was not part of this run. IndicConformer is gated and was not scored. Telugu, Tamil, Kannada, and Malayalam are not in this table.

The page is a small web app. It is not Streamlit.

## Architecture

```mermaid
flowchart LR
  Browser[Bench in the browser]
  API[Starlette API]
  DB[(SQLite)]
  Worker[Experiment worker]
  Data[FLEURS test or a manifest]
  Audio[One audio transform]
  Model[One model at a time]

  Browser --> API
  API --> DB
  API -->|starts| Worker
  Worker --> Data
  Worker --> Audio
  Worker --> Model
  Model --> DB
  Browser -->|polls| API
```

The browser never loads a model. A run is a separate process, so the page stays usable. Status, predictions, and scores are in SQLite and survive a restart. Models are loaded one at a time and unloaded before the next one. If Whisper Medium does not fit in GPU memory, that model fails. It is not replaced by Whisper Small.

| Piece | Role |
|---|---|
| `web/` | The bench: room, run, scores, robustness, marks, tape, export |
| `app/server.py` | Token gate, JSON API, audio, downloads |
| `src/models/` | Whisper, IndicConformer, MMS |
| `src/datasets/` | FLEURS test, pipeline demo, custom manifest |
| `src/audio/` | Noise, speed, volume, reverb, MP3. Originals stay untouched |
| `src/evaluation/` | WER, CER, SER, edits, digits, code-mix |
| `src/experiments/` | Validation, worker, resume |
| `outputs/benchmark.db` | Runs and row-level results |

## What is scored

The headline set is the official **FLEURS test** split for Telugu, Tamil, Hindi, Kannada, and Malayalam. A run downloads only the number of rows you set.

Kathbath, IndicVoices, and Common Voice are listed and **not selectable**. Kathbath is reported training speech for Indic models. IndicVoices is gated and was used to train Indic ASR. Common Voice does not cover Telugu and Kannada evenly.

The English clips in `data/demo` only check that a run finishes. They are not an Indic score.

## Models

| Id | Checkpoint | Languages verified here |
|---|---|---|
| `whisper-small` | `openai/whisper-small` | te, ta, hi, kn, ml, plus en for the demo |
| `whisper-medium` | `openai/whisper-medium` | same as Small |
| `vaakku` | `rudra11/vaakku-whisper-small` on `openai/whisper-small` | te, ta, hi, kn, ml. Not English |
| `mms` | `facebook/mms-1b-all` | tel, tam, hin, kan, mal. CC-BY-NC weights |

`ai4bharat/indic-conformer-600m-multilingual` is gated and is not in this run. NVIDIA Canary and Parakeet checkpoints are public, and their language lists are European. They do not cover Telugu, Tamil, Hindi, Kannada, or Malayalam, so they are not selectable here.

Uploading a file to compare models is not implemented. The hook is `src/inference/upload.py`.

## Run it

```bash
python -m venv .venv
.venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
bash scripts/run_server.sh
```

Open `http://127.0.0.1:8787`.

On the GPU box, install the CUDA wheel that matches the driver instead of the CPU wheel, keep `DASHBOARD_HOST=127.0.0.1`, and open it from your laptop with:

```bash
export AWS_HOST=... AWS_USER=ubuntu AWS_PEM_PATH=/path/to/key.pem
bash scripts/tunnel.sh
```

Then use `http://127.0.0.1:8787` on the laptop. The process on the box is not exposed to the public internet.

```bash
# on the box
bash scripts/run_server.sh            # start
pkill -f "uvicorn app.server:app"     # stop
bash scripts/run_server.sh            # start again
tail -f outputs/logs/*.log            # experiment logs
```

## Custom data

CSV header:

```text
sample_id,audio_path,reference,language,speaker_id
```

`audio_path` is relative to the audio directory you enter on the Run page. JSON can add `license`, `provenance`, and `entities`. See `data/examples/custom_manifest.example.csv`. When `speaker_id` is present, the subset takes one clip per speaker.

## Tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src config app tests
```

CI does not download model weights or FLEURS.
