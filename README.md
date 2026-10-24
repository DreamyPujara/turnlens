# TurnLens

**Find the moment a voice conversation starts to feel awkward.**

TurnLens is a local timing debugger for people building voice products. Give it explicitly paired user/assistant speech intervals, inspect a shared timeline, and see which responses exceed your latency budget. It does not upload recordings or call models.

## Try the product

Requires Python 3.11+; no dependencies or credentials.

```sh
python tool.py examples/demo.json --html demo.html
python -m unittest discover -s tests -v
```

Open `demo.html` in a browser. Expand each turn to inspect its user and assistant intervals. The bundled fixture is synthetic: the median response gap is 500ms, one of three responses exceeds the 800ms budget, and the final exchange contains 200ms of explicitly labeled intentional overlap. These are fixture results, not production outcomes.

## Product decision

The primary user is a voice-product engineer deciding whether a timing change improves the experience. Overlap is shown as evidence rather than automatically marked as a defect: an acknowledgment or intentional interruption can be desirable. A supplied label is preserved; intent is never inferred from timing.

## Metrics, precisely

- **Response gap:** paired assistant start minus user end, in milliseconds. Negative values indicate the assistant started before that user segment ended. Pairing is supplied by the caller, not inferred.
- **Median and p95:** computed over signed gaps. P95 uses the nearest-rank method; a three-turn fixture is illustrative, not a population estimate.
- **Over budget:** gap strictly greater than `--budget-ms` (default 800). This threshold is a configurable product choice, not an industry standard.
- **Cross-speaker overlap:** total intersection duration of all user and assistant intervals, including across supplied pairs. Same-speaker overlaps are rejected to prevent double counting.
- **Internal dead air:** gaps in the union of speech intervals, between the first speech onset and last offset. Leading and trailing silence are excluded. Quiet time is not automatically a failure.

The timeline uses a shared session scale and displays supplied labels. It is descriptive, not a perceptual quality score.

## Input

A JSON object with a nonempty `turns` list. Each turn has a unique string `id`, `user` and `assistant` objects with nonnegative integer `start_ms` and greater `end_ms`. Optional `overlap_label`: `unlabeled`, `intended`, or `unwanted`.

```json
{"turns":[{"id":"hello","user":{"start_ms":0,"end_ms":1000},"assistant":{"start_ms":1400,"end_ms":2000}}]}
```

CLI JSON output includes the summary and each turn's evidence. `--fail-on-budget` returns 1 for latency violations; invalid inputs return 2. Normal analysis returns 0.

## Boundaries and next experiments

This first version analyzes event metadata, not raw audio. It includes no ASR, VAD, TTS, emotion recognition, or live voice agent. A report cannot prove that an agent sounds natural. Next experiments: paired baseline comparisons, cancellation-delay events, and user-supplied labels for false interruptions. Product feedback and user studies are not yet available.

Built with AI assistance. Bundled data is synthetic; no customer data or employer code is used. Reports include supplied IDs, so sanitize your own data before sharing.
