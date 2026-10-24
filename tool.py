"""TurnLens: inspect paired speech intervals without uploading recordings."""
import argparse
import html
import json
import math
from pathlib import Path
import statistics
import sys


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('turns'), list) or not data['turns']:
        raise ValueError('Expected an object with a nonempty turns array')
    ids = set()
    for turn in data['turns']:
        if not isinstance(turn, dict) or not isinstance(turn.get('id'), str) or not turn['id'].strip():
            raise ValueError('Each turn needs a nonempty string id')
        if turn['id'] in ids:
            raise ValueError('Turn IDs must be unique')
        ids.add(turn['id'])
        for role in ('user', 'assistant'):
            interval = turn.get(role)
            if not isinstance(interval, dict):
                raise ValueError(f'Each turn needs a {role} interval')
            start, end = interval.get('start_ms'), interval.get('end_ms')
            if type(start) is not int or type(end) is not int or start < 0 or end <= start:
                raise ValueError('Intervals need nonnegative integer timestamps and end_ms > start_ms')
        if turn.get('overlap_label', 'unlabeled') not in ('unlabeled', 'intended', 'unwanted'):
            raise ValueError('overlap_label must be unlabeled, intended, or unwanted')
    # Reject duplicate/overlapping intervals for one speaker so duration totals
    # cannot silently double count. Cross-speaker overlap is valid input.
    for role in ('user', 'assistant'):
        spans = sorted((t[role]['start_ms'], t[role]['end_ms']) for t in data['turns'])
        if any(b[0] < a[1] for a, b in zip(spans, spans[1:])):
            raise ValueError(f'Overlapping {role} intervals; merge segmentation before analysis')
    return data['turns']


def analyze(data, budget_ms=800):
    if type(budget_ms) is not int or budget_ms < 0:
        raise ValueError('Latency budget must be a nonnegative integer')
    turns = validate(data)
    rows = []
    gaps = []
    for turn in turns:
        user, assistant = turn['user'], turn['assistant']
        gap = assistant['start_ms']-user['end_ms']
        gaps.append(gap)
        rows.append({'id': turn['id'], 'response_gap_ms': gap,
                     'over_budget': gap > budget_ms,
                     'overlap_label': turn.get('overlap_label', 'unlabeled'),
                     'user': user, 'assistant': assistant})
    users = [t['user'] for t in turns]
    assistants = [t['assistant'] for t in turns]
    overlap = sum(max(0, min(u['end_ms'], a['end_ms'])-max(u['start_ms'], a['start_ms']))
                  for u in users for a in assistants)
    spans = sorted((t[r]['start_ms'], t[r]['end_ms']) for t in turns for r in ('user', 'assistant'))
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    dead_air = sum(b[0]-a[1] for a, b in zip(merged, merged[1:]))
    return {'summary': {'turns': len(turns), 'budget_ms': budget_ms,
                        'over_budget_turns': sum(t['over_budget'] for t in rows),
                        'median_response_gap_ms': statistics.median(gaps),
                        'p95_response_gap_ms': sorted(gaps)[math.ceil(.95*len(gaps))-1],
                        'cross_speaker_overlap_ms': overlap, 'internal_dead_air_ms': dead_air},
            'turns': rows}


def report_html(result):
    s = result['summary']
    end = max(t[r]['end_ms'] for t in result['turns'] for r in ('user', 'assistant'))
    cards = []
    for turn in result['turns']:
        bars = []
        for role in ('user', 'assistant'):
            span = turn[role]
            left = span['start_ms']/end*100
            width = (span['end_ms']-span['start_ms'])/end*100
            bars.append(f'<div class="lane"><span class="{role}" style="left:{left:.3f}%;width:{width:.3f}%">{role}</span></div>')
        cards.append(f'<details open><summary>{html.escape(turn["id"])} <b>{turn["response_gap_ms"]} ms</b></summary>'
                     f'<p>{"Over latency budget" if turn["over_budget"] else "Within configured latency budget"} · Overlap intent: {turn["overlap_label"]}</p>{"".join(bars)}</details>')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TurnLens · conversation timing</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#0c1420;color:#edf2fa;font:16px/1.6 system-ui}}main{{max-width:1080px;margin:auto;padding:48px 24px}}.label{{color:#6de4c5;font-size:12px;letter-spacing:.15em}}h1{{font-size:clamp(36px,6vw,64px);line-height:1.05}}p{{color:#aebed3}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.metric,details{{background:#152339;border:1px solid #30465f;padding:22px;border-radius:12px;margin:16px 0}}strong{{display:block;font-size:30px}}summary{{cursor:pointer}}summary b{{float:right;color:#6de4c5}}.lane{{height:30px;position:relative;margin:10px 0;background:#0c1420;border-radius:5px;overflow:hidden}}.lane span{{position:absolute;height:100%;font-size:12px;padding:4px;color:#0c1420;min-width:4px}}.user{{background:#75aaff}}.assistant{{background:#6de4c5}}footer{{border-top:1px solid #30465f;padding-top:20px;margin-top:28px;color:#aebed3}}@media(max-width:650px){{.metrics{{grid-template-columns:1fr}}}}</style>
<main><div class="label">TURNLENS / VOICE EXPERIENCE DEBUGGER</div><h1>Make the pause<br>worth listening to.</h1><p>Inspect a synthetic conversation, locate slow responses and review overlapping speech.<br>Blue: user · Green: assistant. All lanes share the same session time scale.</p>
<div class="metrics"><div class="metric">Median response gap<strong>{s['median_response_gap_ms']} ms</strong></div><div class="metric">Over budget<strong>{s['over_budget_turns']} / {s['turns']}</strong>{s['budget_ms']} ms limit</div><div class="metric">Cross-speaker overlap<strong>{s['cross_speaker_overlap_ms']} ms</strong></div></div>
{''.join(cards)}<footer>Synthetic timing fixture, not recorded audio. No ASR, model calls, audio uploads or inferred user intent. Negative response gaps mean an assistant began before its paired user segment ended. Overlap is not automatically a defect. Internal dead air: {s['internal_dead_air_ms']} ms.</footer></main></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('--budget-ms', type=int, default=800)
    parser.add_argument('--html', type=Path)
    parser.add_argument('--fail-on-budget', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = analyze(json.loads(args.session.read_text(encoding='utf-8')), args.budget_ms)
        if args.html:
            args.html.write_text(report_html(result), encoding='utf-8')
        print(json.dumps(result, indent=2))
        return int(args.fail_on_budget and result['summary']['over_budget_turns'] > 0)
    except (OSError, ValueError) as error:
        print(f'TurnLens: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
