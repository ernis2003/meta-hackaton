import csv
import ipaddress
import json
import re
from src.ai.common import ROOT, digest, load_json, save_json


def metrics(response, case):
    report = response.get('parsed_json')
    text = response['raw_response'].lower()
    grounding = sum(token.lower() in text for token in case['expected_evidence']) / max(len(case['expected_evidence']), 1)
    limitations = sum(token.lower() in text for token in case['expected_limitations']) / max(len(case['expected_limitations']), 1)
    evidence = json.dumps(case['network_evidence'])
    candidates = []
    for identifier in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text):
        try:
            ipaddress.ip_address(identifier)
            if identifier not in evidence:
                candidates.append(identifier)
        except ValueError:
            pass
    return dict(json_valid=report is not None, evidence_token_coverage=grounding,
                limitation_token_coverage=limitations,
                nonempty_sections=sum(bool(v) for v in report.values()) if report else 0,
                recommendations_present=bool(report and report['recommended_actions']),
                unsupported_identifier_candidates=sorted(set(candidates)),
                inference_seconds=response['duration_seconds'],
                human_review_required=True)


def compare():
    before = load_json(ROOT / 'results' / 'before_training.json')
    after = load_json(ROOT / 'results' / 'after_training.json')
    if not before['complete'] or not after['complete'] or before['protocol_hash'] != after['protocol_hash'] or before['model_version'] != after['model_version']:
        raise ValueError('Cannot compare incomplete evaluations or different protocols/base revisions')
    cases = {c['id']: c for c in before['protocol']['cases']}
    b = {r['test_id']: r for r in before['responses']}
    a = {r['test_id']: r for r in after['responses']}
    if set(b) != set(a) or set(a) != set(cases):
        raise ValueError('Evaluation cases differ')
    rows = [dict(test_id=key, before=b[key], after=a[key], before_metrics=metrics(b[key], cases[key]),
                 after_metrics=metrics(a[key], cases[key])) for key in cases]
    result = dict(protocol_hash=before['protocol_hash'], comparisons=rows,
        interpretation='Automatic token coverage and structural checks are proxies, not semantic grades. Unsupported claims, explanation quality and recommendation quality require human review. No improvement is asserted.')
    path = ROOT / 'results' / 'comparison.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['test_id', 'before_answer', 'after_answer', 'before_metrics', 'after_metrics',
                                                   'review_grounding', 'review_unsupported_claims', 'review_completeness', 'review_uncertainty', 'review_recommendations'])
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(test_id=row['test_id'], before_answer=row['before']['raw_response'],
                                 after_answer=row['after']['raw_response'], before_metrics=json.dumps(row['before_metrics']),
                                 after_metrics=json.dumps(row['after_metrics'])))
    def cell(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', '<br>')
    totals = {}
    for stage in ('before', 'after'):
        values = [r[stage + '_metrics'] for r in rows]
        totals[stage] = dict(json_valid=sum(v['json_valid'] for v in values), cases=len(values),
            mean_evidence_token_coverage=sum(v['evidence_token_coverage'] for v in values) / len(values),
            mean_limitation_token_coverage=sum(v['limitation_token_coverage'] for v in values) / len(values),
            unsupported_identifier_candidates=sum(len(v['unsupported_identifier_candidates']) for v in values))
    result['aggregate_metrics'] = totals
    save_json(ROOT / 'results' / 'comparison.json', result)
    markdown = ['# Before / after comparison', result['interpretation'],
        '## Measured structural and grounding proxies', '```json\n' + json.dumps(totals, indent=2) + '\n```',
        'Correctness: requires semantic review against the supplied evidence. Token overlap is not an accuracy grade.',
        'Evidence grounding: coverage above measures literal expected-token mentions only.',
        'Hallucinations: unsupported IP candidates are a narrow check; invented metrics, intent and mechanisms require review.',
        'JSON validity: strict validation of the complete response, allowing a single enclosing code fence.',
        'Explanation quality: section completeness and recommendations are structural proxies; concise but irrelevant answers can still score well.',
        '## Actual responses', '| Test | Base Llama | Fine-tuned Llama |', '| --- | --- | --- |']
    markdown.extend(f"| {r['test_id']} | {cell(r['before']['raw_response'])} | {cell(r['after']['raw_response'])} |" for r in rows)
    (ROOT / 'results' / 'comparison.md').write_text('\n\n'.join(markdown), encoding='utf-8')


if __name__ == '__main__':
    compare()
