import { useEffect, useState } from 'react';
import { api } from '../../utils/analyses';

type Report = {
  summary: string; observations: string[]; supporting_evidence: string[]; possible_threats: string[];
  benign_explanations: string[]; recommended_actions: string[]; confidence: 'low' | 'medium' | 'high'; limitations: string[];
};
type Explanation = { report: Report; model_identifier: string; model_version: string;
  adapter_identifier: string | null; fine_tuned: boolean; generated_at: string; duration_seconds: number; evidence?: unknown };
type Muse = { report: {verdict: string; summary: string; verified_observations: string[]; unsupported_claims: string[];
  benign_explanations: string[]; recommended_actions: string[]; confidence: string}; model_identifier: string;
  generated_at: string; duration_seconds: number; evidence: unknown; tool_calls: unknown[] };
type State = {status: string; explanation?: Explanation | null; error?: string | null};

export default function AIInvestigation({analysisId, anomalyId}: {analysisId: string; anomalyId: string}) {
  const [expanded, setExpanded] = useState(false);
  return <details className="mt-4 rounded-lg border border-slate-600" onToggle={e => setExpanded(e.currentTarget.open)}>
    <summary className="cursor-pointer px-4 py-3 text-teal-300">AI Investigation</summary>
    {expanded && <InvestigationPanel key={`${analysisId}:${anomalyId}`} analysisId={analysisId} anomalyId={anomalyId} />}
  </details>;
}

function InvestigationPanel({analysisId, anomalyId}: {analysisId: string; anomalyId: string}) {
  const [state, setState] = useState<State>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const path = `/${encodeURIComponent(analysisId)}/anomalies/${encodeURIComponent(anomalyId)}`;
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const saved = await api<State>(path + '/explanation');
        if (active) {
          setState(saved); setError('');
          if (saved.status === 'processing') timer = setTimeout(() => void load(), 3000);
        }
      } catch (e) { if (active) setError((e as Error).message); }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [path]);

  async function generate(regenerate = false) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const explanation = await api<Explanation>(path + `/explain?regenerate=${regenerate}`, {method: 'POST'});
      setState({status: 'completed', explanation});
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const explanation = state?.explanation;
  return <div className="flex flex-col gap-4 border-t border-slate-600 p-4">
    {loading && <p role="status">Checking saved investigation...</p>}
    {(error || state?.error) && <p role="alert" className="text-red-300">{error || state?.error}</p>}
    {(busy || state?.status === 'processing') && <p role="status" aria-live="polite">Generating an explanation with the local model...</p>}
    {!loading && <button type="button" disabled={busy || state?.status === 'processing'}
      onClick={() => void generate(Boolean(explanation))}
      className="self-start rounded-md bg-[#2B3849] px-4 py-2 text-sm hover:bg-[#35465B] disabled:opacity-40">
      {explanation ? 'Analyze with Llama again' : 'Analyze with Llama'}
    </button>}
    {explanation && <>
      <p className="text-sm text-teal-300">{explanation.fine_tuned ? 'Fine-tuned model' : 'Baseline model — not fine-tuned'}</p>
      <p>{explanation.report.summary}</p>
      {([
        ['Observations', 'observations'], ['Supporting evidence', 'supporting_evidence'],
        ['Possible threats (hypotheses)', 'possible_threats'], ['Benign explanations', 'benign_explanations'],
        ['Recommended investigation actions', 'recommended_actions'], ['Limitations', 'limitations'],
      ] as const).map(([title, key]) => <section key={key}>
        <h3 className="mb-1 font-medium">{title}</h3>
        {explanation.report[key].length ? <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
          {explanation.report[key].map((text, i) => <li key={i}>{text}</li>)}
        </ul> : <p className="text-sm text-slate-400">None provided by the model.</p>}
      </section>)}
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-xs text-slate-400">
        <dt>Model confidence</dt><dd>{explanation.report.confidence} (self-reported, not attack probability)</dd>
        <dt>Model</dt><dd className="break-all">{explanation.model_identifier}</dd>
        <dt>Version</dt><dd className="break-all">{explanation.model_version}</dd>
        {explanation.adapter_identifier && <><dt>Adapter</dt><dd className="break-all">{explanation.adapter_identifier}</dd></>}
        <dt>Generated</dt><dd>{new Date(explanation.generated_at).toLocaleString()}</dd>
        <dt>Duration</dt><dd>{explanation.duration_seconds.toFixed(2)} s</dd>
      </dl>
      <p className="text-xs text-slate-500">Built with Llama. AI-generated investigation; verify conclusions against the recorded evidence.</p>
      <details><summary className="cursor-pointer text-sm text-teal-300">Llama evidence snapshot</summary>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(explanation.evidence, null, 2)}</pre></details>
    </>}
    <MusePanel key={`${path}:${explanation?.generated_at ?? ''}`} path={path} hasLlama={Boolean(explanation)} />
  </div>;
}

function MusePanel({path, hasLlama}: {path: string; hasLlama: boolean}) {
  const [saved, setSaved] = useState<{status: string; investigation?: Muse | null; error?: string; stale?: boolean}>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await api<NonNullable<typeof saved>>(path + '/review');
        if (active) {
          setSaved(value);
          if (value.status === 'processing') timer = setTimeout(() => void load(), 3000);
        }
      } catch (e) { if (active) setError((e as Error).message); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [path]);
  async function investigate() {
    setBusy(true); setError('');
    try {
      const investigation = await api<Muse>(path + `/investigate?regenerate=${Boolean(saved?.investigation)}`, {method: 'POST'});
      setSaved({status: 'completed', investigation});
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const value = saved?.investigation;
  return <section className="space-y-3 border-t border-slate-600 pt-4">
    <h3 className="font-medium text-teal-300">Independent Meta Muse review</h3>
    <p className="text-xs text-slate-400">Sends structured database evidence and the Llama explanation to Meta. Investigation tools only read this authorized analysis.</p>
    <button type="button" disabled={!hasLlama || busy || saved?.status === 'processing'} onClick={() => void investigate()}
      className="rounded-md bg-[#2B3849] px-4 py-2 text-sm hover:bg-[#35465B] disabled:opacity-40">Investigate with Meta Muse</button>
    {!hasLlama && <p className="text-sm text-slate-400">Analyze with Llama first.</p>}
    {(busy || saved?.status === 'processing') && <p role="status">Muse is reviewing the evidence...</p>}
    {(error || saved?.error) && <p role="alert" className="text-red-300">{error || saved?.error}</p>}
    {saved?.stale && <p className="text-amber-300">This saved review refers to an earlier Llama explanation. Investigate again to update it.</p>}
    {value && <>
      <p className="font-medium">Verdict: {value.report.verdict}</p><p>{value.report.summary}</p>
      {(['verified_observations', 'unsupported_claims', 'benign_explanations', 'recommended_actions'] as const).map(key =>
        <section key={key}><h4 className="font-medium">{key.replaceAll('_', ' ')}</h4>
          {value.report[key].length ? <ul className="list-disc pl-5 text-sm text-slate-300">{value.report[key].map((text, i) => <li key={i}>{text}</li>)}</ul>
            : <p className="text-sm text-slate-400">None reported.</p>}</section>)}
      <p className="break-all text-xs text-slate-400">Model: {value.model_identifier} · Confidence: {value.report.confidence} (self-reported) · {new Date(value.generated_at).toLocaleString()} · {value.duration_seconds.toFixed(2)} s</p>
      <details><summary className="cursor-pointer text-sm text-teal-300">Muse evidence and investigation tool results</summary>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify({evidence: value.evidence, tools: value.tool_calls}, null, 2)}</pre></details>
    </>}
  </section>;
}
