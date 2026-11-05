"""Local evidence-only preparation with capture-disjoint evaluation splits."""
import argparse
import csv
import json
import math
import random
import re
from pathlib import Path
from src.ai.common import ROOT, digest, now, save_json
from src.ai.llm.prompts import SYSTEM_PROMPT


def example(row):
    aliases = dict(zip(('Dst Port', 'Tot Fwd Pkts', 'Tot Bwd Pkts', 'TotLen Fwd Pkts', 'TotLen Bwd Pkts'),
        ('Destination Port', 'Total Fwd Packets', 'Total Backward Packets', 'Total Length of Fwd Packets', 'Total Length of Bwd Packets')))
    row = {aliases.get(k.strip(), k.strip()): v for k, v in row.items()}
    label = str(row.get('Label', row.get('label', ''))).strip()
    if not label or label.lower() == 'label':
        return None
    fields = {}
    for k in ('Flow Duration', 'Total Fwd Packets', 'Total Backward Packets', 'Total Length of Fwd Packets',
              'Total Length of Bwd Packets', 'Destination Port', 'Protocol', 'dur', 'tot_pkts', 'tot_bytes', 'src_bytes'):
        try:
            v = float(row[k])
            if math.isfinite(v) and v >= 0:
                fields[k] = int(v) if v.is_integer() else round(v, 6)
        except (KeyError, ValueError, TypeError):
            pass
    if 'proto' in row:
        fields['proto'] = str(row['proto']).strip()
    if len(fields) < 3:
        return None
    report = dict(summary=f'Corpus label: {label}. Flow features alone do not confirm intent.',
        observations=[f'{k}: {v}' for k, v in fields.items()], supporting_evidence=[f'Corpus label: {label}'],
        possible_threats=[], benign_explanations=[], recommended_actions=['Review capture context and endpoint logs.'],
        confidence='low', limitations=['No JA4, payload or process evidence. Corpus labels are not independent verification.'])
    return [dict(role='system', content=SYSTEM_PROMPT), dict(role='user', content=json.dumps(dict(
        task='Explain this labeled research flow using only supplied evidence.', features=fields, corpus_label=label), separators=(',', ':'))),
        dict(role='assistant', content=json.dumps(report, separators=(',', ':')))]


def prepare(args):
    import pyarrow as pa
    import pyarrow.csv as pc
    import pyarrow.parquet as pq
    root, out = Path(args.input), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if any((out / (s + '.jsonl')).exists() and (out / (s + '.jsonl')).stat().st_size for s in ('train', 'validation', 'test')):
        raise ValueError('Refusing to overwrite nonempty prepared artifacts; choose another output directory')
    rng = random.Random(args.seed)
    controls = json.loads((ROOT / 'evaluation' / 'control_questions.json').read_text())
    provenance = dict(timestamp=now(), seed=args.seed, sources=[],
        policy='Local-only; capture/day-disjoint splits; identical feature evidence deduplicated globally. Labels are supplied evidence, not inferred mechanisms.',
        limitations=['Folder names are unverified dataset identities. No JA4 supervision. Feature units remain as recorded.',
                    'Labeled-flow explanation training does not establish anomaly classification accuracy.'])
    pools = {s: [] for s in ('validation', 'test', 'train')}
    seen = set()
    for folder in sorted(root.iterdir()):
        files = sorted([*folder.rglob('*.csv'), *folder.rglob('*.parquet')])
        if not files:
            provenance['sources'].append(dict(folder=folder.name, status='excluded',
                reason='PCAPs have no inspected per-flow ground truth; folder names are insufficient labels.',
                files=[str(f.relative_to(root)) for f in folder.rglob('*.pcap')]))
            continue
        def group(f):
            m = re.search(r'(2011[0-9]{4})', f.name)
            return m.group(1) if m else f.name.lower().split('-workinghours')[0]
        groups = sorted({group(f) for f in files})
        rng.shuffle(groups)
        assignment = {g: ('validation' if i == 0 else 'test' if i == 1 else 'train') for i, g in enumerate(groups)}
        for file in files:
            split = assignment[group(file)]
            info = dict(file=str(file.relative_to(root)), split=split, capture_group=group(file),
                        bytes=file.stat().st_size, labels={}, scanned=0)
            provenance['sources'].append(info)
            if file.suffix == '.parquet':
                reader = pq.ParquetFile(file)
                info['schema'] = str(reader.schema_arrow)
                batches = reader.iter_batches(batch_size=65536)
            else:
                with file.open(encoding='latin1', newline='') as stream:
                    names = next(csv.reader(stream))
                reader = pc.open_csv(file, read_options=pc.ReadOptions(encoding='latin1', block_size=8 * 1024 * 1024),
                    convert_options=pc.ConvertOptions(column_types={k: pa.string() for k in names}))
                info['schema'] = str(reader.schema)
                batches = reader
            buckets = {}
            for batch in batches:
                columns = batch.schema.names
                label_key = next(k for k in columns if k.strip().lower() == 'label')
                positions = {}
                for i, label in enumerate(batch.column(columns.index(label_key)).to_pylist()):
                    label = str(label).strip()
                    info['labels'][label] = info['labels'].get(label, 0) + 1
                    positions.setdefault(label, []).append(i)
                for label, indices in positions.items():
                    bucket = buckets.setdefault(label, [])
                    for i in rng.sample(indices, min(12, len(indices))):
                        messages = example({k: batch.column(j)[i].as_py() for j, k in enumerate(columns)})
                        if not messages:
                            continue
                        key = digest(json.loads(messages[1]['content'])['features'])
                        if key in seen:
                            continue
                        seen.add(key)
                        record = dict(id=key, messages=messages, source=folder.name,
                            source_row=f'{info["file"]}:{info["scanned"] + i}', metadata=dict(label=label, capture_group=group(file)))
                        if len(bucket) < 180:
                            bucket.append(record)
                        else:
                            bucket[rng.randrange(len(bucket))] = record
                info['scanned'] += batch.num_rows
            for bucket in buckets.values():
                pools[split].extend(bucket)
            print(info['file'], split, 'rows:', info['scanned'], 'labels:', len(info['labels']), flush=True)
    partitions = {}
    for split, count in (('validation', 250), ('test', 250), ('train', 2000)):
        strata = {}
        for row in pools[split]:
            label = row['metadata']['label']
            if row['source'] == 'CTU-13':
                label = 'Botnet' if 'Botnet' in label else 'Normal' if 'Normal' in label else 'Background'
            strata.setdefault((row['source'], label), []).append(row)
        for rows in strata.values():
            rng.shuffle(rows)
        selected = []
        while len(selected) < count and any(strata.values()):
            for rows in strata.values():
                if rows and len(selected) < count:
                    selected.append(rows.pop())
        rng.shuffle(selected)
        partitions[split] = selected
        (out / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in selected), encoding='utf-8')
    records = [r for s in ('validation', 'test', 'train') for r in partitions[s]]
    provenance.update(total=len(records), splits={k: len(v) for k, v in partitions.items()},
        dataset_hash=digest(records), controls_hash=digest(controls),
        records=[{k: r[k] for k in ('id', 'source', 'source_row', 'metadata')} for r in records])
    save_json(out / 'provenance.json', provenance)
    if len(records) != 2500:
        raise RuntimeError('Insufficient suitable records; inspect provenance')
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=str(ROOT / 'datasets' / 'training_data'))
    parser.add_argument('--output', default=str(ROOT / 'datasets' / 'prepared'))
    parser.add_argument('--seed', type=int, default=42)
    print(json.dumps(prepare(parser.parse_args())['splits'], indent=2))


if __name__ == '__main__':
    main()
