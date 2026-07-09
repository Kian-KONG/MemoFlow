# Model Download Progress Design

## Goal

Add a dedicated model download experience in the settings page that:

- keeps model download fully decoupled from meeting processing
- prefers `ModelScope` as the primary upstream when practical
- falls back to `HuggingFace` only where required, such as `pyannote`
- shows stable, user-visible progress during download and load
- preserves the current rule that processing never auto-downloads models

## Scope

This design covers:

- model source selection and resolution
- download task lifecycle and progress reporting
- settings page UI behavior
- integration points with current model preload and processing preflight checks

This design does not cover:

- resumable byte-range downloads
- parallel multi-model downloads with bandwidth scheduling
- background daemon or queue persistence across app restarts

## Source Strategy

### Recommended source policy

Each model gets an explicit preferred source:

- `SenseVoice ASR`: prefer `ModelScope`
- `Embedding`: prefer `ModelScope`
- `Qwen MLX`: prefer `ModelScope` when a compatible package exists, otherwise use the current supported upstream
- `pyannote diarization`: use `HuggingFace`

The system should not infer the source dynamically from whatever library happens to do by default. Instead, MemoFlow should decide the source in its own configuration layer and surface that choice in the UI.

### Why this approach

- Users get predictable behavior and can see which upstream is being used.
- China-mainland friendly flows improve for models that are available on `ModelScope`.
- `pyannote` remains on `HuggingFace`, which matches its access-control and token workflow.

## Download Lifecycle

Every model download should report a shared lifecycle:

1. `queued`
2. `resolving_source`
3. `downloading`
4. `loading`
5. `completed`
6. `failed`

These states are stable across all model types, even when byte-level progress is unavailable.

### Optional byte progress

If the chosen upstream or helper can expose downloaded bytes and total bytes reliably, MemoFlow should show:

- downloaded bytes
- total bytes
- percentage

If a model source cannot expose byte progress, the UI should still show:

- current lifecycle stage
- active source
- recent log lines

This keeps the progress experience consistent without overpromising exact percentages everywhere.

## Data Model

Add a runtime download status record per model, owned by the model service.

Suggested fields:

- `key`
- `role`
- `source`
- `stage`
- `loaded`
- `ready`
- `downloading`
- `downloaded_bytes`
- `total_bytes`
- `percent`
- `message`
- `recent_logs`
- `error`
- `started_at`
- `updated_at`

This state is in-memory for now. On restart, the service recomputes readiness from local cache / successful load state instead of trying to resume old download sessions.

## Architecture

### 1. Source resolver

Introduce a small source-resolution layer that maps model keys to upstreams and upstream-specific identifiers.

Responsibilities:

- choose preferred source per model
- expose the chosen source to the UI
- keep source selection out of individual page code

### 2. Download adapter layer

Add source-specific download helpers:

- `ModelScopeDownloadAdapter`
- `HuggingFaceDownloadAdapter`

Responsibilities:

- download files or snapshots to local cache
- report lifecycle transitions and optional byte progress
- emit plain progress events into a shared reporter

### 3. Progress reporter

Add a reusable progress reporter abstraction used by all downloads.

Responsibilities:

- store current stage
- append recent logs
- update byte progress if known
- expose immutable snapshots for the settings UI and API

### 4. Model service integration

Extend the existing model service so that `download_model()` becomes:

1. resolve source
2. update progress to `resolving_source`
3. run source-specific download
4. update progress to `loading`
5. call the model adapter preload
6. update progress to `completed`

The processing pipeline keeps using `ensure_processing_models_ready()` and should still fail fast if a model has not been prepared in settings.

## UI Design

The settings page remains the single place for model preparation.

Each model card should show:

- model role
- model identifier
- source badge: `ModelScope` or `HuggingFace`
- readiness badge: `已就绪 / 下载中 / 未下载 / 不可用 / 失败`
- current stage text
- optional progress bar if percentage is known
- recent logs area
- actionable error text when failed
- `下载模型` button when eligible

The page-level action `下载全部可用模型` should iterate models in a deterministic order:

1. ASR
2. diarization
3. LLM
4. embedding

This ordering prioritizes the shortest path to a usable meeting-processing flow.

## Error Handling

### Network issues

If network errors occur:

- mark stage as `failed`
- preserve recent logs
- show readable error text in the card
- allow retry without restarting the app

### Permission / token issues

If `HuggingFace` authorization fails for `pyannote`:

- show source as `HuggingFace`
- show failure reason clearly
- tell the user that read-only token is acceptable
- remind the user to accept the model license

### Startup safety

No UI page should dereference the app container during route registration. All service access must happen at render or action time, so settings remains safe under startup and reload behavior.

## Testing

Add or update tests for:

- source selection per model
- lifecycle stage transitions
- progress state updates
- retry after failed download
- settings page service access remaining lazy
- processing preflight still rejecting not-yet-downloaded models

## Recommendation

Implement the hybrid approach:

- always show shared stage progress
- show byte progress only when reliably available
- prefer `ModelScope` wherever stable
- keep `HuggingFace` for `pyannote`

This gives a noticeably better user experience now without forcing a fragile, fully custom downloader for every model family.
