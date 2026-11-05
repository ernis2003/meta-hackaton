import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Position,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import '@xyflow/react/dist/style.css';
import AnalysisList from './AnalysisList';
import { api, type Page, type Result } from '../../utils/analyses';
import EvidenceDetails from './EvidenceDetails';
import SubjectActivity, { bytes, Metric } from './SubjectActivity';
import { Link } from 'react-router-dom';

type GraphNode = {
  id: string;
  type: string;
  label: string;
  metadata: Record<string, unknown>;
  risk_score: number;
  anomaly_count: number;
};
type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  metadata: Record<string, unknown>;
};
type Graph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  truncated: boolean;
};
const colors: Record<string, string> = {
  host: '#6D98E3',
  domain: '#9462F1',
  ja4: '#3FDDBB',
  ja4s: '#3FDDBB',
  ja4h: '#3FDDBB',
};
export default function NetworkSubjects() {
  return (
    <AnalysisList title="Network Subjects">
      {(analysis) => <NetworkGraph key={analysis.id} id={analysis.id} />}
    </AnalysisList>
  );
}
function NetworkGraph({ id }: { id: string }) {
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');
  const [scope, setScope] = useState('neighborhood');
  const [center, setCenter] = useState(params.get('focus') || '');
  const [focus, setFocus] = useState(params.get('focus') || '');
  const [data, setData] = useState<Graph>();
  const [selected, setSelected] = useState<GraphNode | GraphEdge>();
  const [anomalies, setAnomalies] = useState<Result[]>([]);
  const [anomalyTotal, setAnomalyTotal] = useState(0);
  const [anomalyOffset, setAnomalyOffset] = useState(0);
  const selectionRequest = useRef(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [flow, setFlow] = useState<ReactFlowInstance>();
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    if (id) {
      setLoading(true);
      api<Graph>(
        `/${id}/graph?limit=300&search=${encodeURIComponent(query)}&focus=${encodeURIComponent(focus)}`,
      )
        .then((value) => {
          if (active) {
            setData(value);
            setSelected(undefined);
            setError('');
          }
        })
        .catch((e) => {
          if (active) {
            setData(undefined);
            setNodes([]);
            setEdges([]);
            setError(e.message);
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, [id, query, focus, setNodes, setEdges]);
  const layout = useCallback(() => {
    if (!data) return;
    const root = data.nodes.some((n) => n.id === center)
      ? center
      : data.nodes.find((n) => n.type === 'host')?.id || data.nodes[0]?.id;
    const neighborhood = new Set([
      root,
      ...data.edges
        .filter((e) => e.source === root || e.target === root)
        .flatMap((e) => [e.source, e.target]),
    ]);
    const visible = data.nodes.filter(
      (n) =>
        (scope === 'all' || neighborhood.has(n.id)) &&
        (type === 'all' || n.type === type || (type !== 'host' && n.type === 'host')),
    );
    const ids = new Set(visible.map((n) => n.id));
    const links = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'LR', nodesep: 30, ranksep: 150 });
    visible.forEach((n) => g.setNode(n.id, { width: 240, height: 104 }));
    links.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);
    setNodes(
      visible.map((n) => ({
        id: n.id,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        position: { x: g.node(n.id).x - 120, y: g.node(n.id).y - 52 },
        data: {
          label: (
            <div className="text-left">
              <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-400">
                <span>
                  {n.type === 'host'
                    ? '◉ IP subject'
                    : n.type === 'domain'
                      ? '◎ Domain'
                      : '◇ ' + n.type}
                </span>
                {n.anomaly_count > 0 && (
                  <span className="text-amber-300">{n.anomaly_count} indicators</span>
                )}
              </div>
              <div className="truncate font-mono text-sm font-semibold" title={n.label}>
                {n.label}
              </div>
              <div className="mt-2 text-[11px] text-slate-400">
                {n.type === 'host'
                  ? `${Number(n.metadata.total_connections || 0)} sessions · ${bytes(Number(n.metadata.bytes_sent || 0) + Number(n.metadata.bytes_received || 0))}`
                  : 'Observed in capture'}
                {n.risk_score > 0 && (
                  <span className="ml-2 text-amber-300">Risk {n.risk_score}</span>
                )}
              </div>
            </div>
          ),
        },
        style: {
          width: 240,
          height: 104,
          padding: 14,
          background: '#142033',
          color: '#F9FAFB',
          border: `1px solid ${n.risk_score >= 60 ? '#F16668' : n.anomaly_count ? '#F59E0B' : colors[n.type]}`,
          borderRadius: 14,
          overflowWrap: 'anywhere',
        },
      })),
    );
    setEdges(
      links.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: `${Number(e.metadata.connection_count || 0)} sessions${Number(e.metadata.total_bytes) ? ' · ' + bytes(e.metadata.total_bytes) : ''}`,
        interactionWidth: 24,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
          strokeWidth: Math.min(4, 1 + Math.log10(Number(e.metadata.connection_count || 1))),
          stroke: (e.metadata.anomalies as string[])?.length ? '#F59E0B' : '#6D98E3',
        },
        labelStyle: { fill: '#CBD5E1' },
        labelBgStyle: { fill: '#142033' },
      })),
    );
    window.setTimeout(() => void flow?.fitView({ padding: 0.2 }), 50);
  }, [data, type, scope, center, flow, setNodes, setEdges]);
  useEffect(() => {
    layout();
  }, [layout]);
  async function inspect(item: GraphNode | GraphEdge, offset = 0) {
    const request = ++selectionRequest.current;
    if (!('source' in item) && item.type === 'host') setCenter(item.id);
    setError('');
    setSelected(item);
    setAnomalies([]);
    setAnomalyOffset(offset);
    setAnomalyTotal(0);
    try {
      const filter =
        'source' in item
          ? `anomaly_ids=${encodeURIComponent(((item.metadata.anomalies as string[]) || []).join(','))}`
          : `subject_id=${encodeURIComponent(item.id)}`;
      const page = await api<Page<Result>>(`/${id}/anomalies?limit=25&offset=${offset}&${filter}`);
      if (selectionRequest.current === request) {
        setAnomalies(page.items);
        setAnomalyTotal(page.total);
      }
    } catch (e) {
      if (selectionRequest.current === request) setError((e as Error).message);
    }
  }
  const related = selected
    ? new Set(
        'source' in selected
          ? [selected.source, selected.target]
          : [
              selected.id,
              ...(data?.edges
                .filter((e) => e.source === selected.id || e.target === selected.id)
                .flatMap((e) => [e.source, e.target]) || []),
            ],
      )
    : undefined;
  return (
    <div className="flex min-w-0 flex-col gap-4">
      {data && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric
            label="IP subjects"
            value={data.nodes.filter((n) => n.type === 'host').length}
            accent="text-blue-300"
          />
          <Metric label="Relationships" value={data.edges.length} />
          <Metric
            label="Domains"
            value={data.nodes.filter((n) => n.type === 'domain').length}
            accent="text-purple-300"
          />
          <Metric
            label="Flagged subjects"
            value={data.nodes.filter((n) => n.type === 'host' && n.anomaly_count > 0).length}
            accent="text-amber-300"
          />
        </div>
      )}
      <p>
        Subjects represent observed IP addresses; shared IPs and NAT do not establish device
        identity.
      </p>
      <form
        className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-700 bg-[#131e2c] p-3 [&_button]:rounded-lg [&_button]:bg-slate-700/60 [&_button]:px-3 [&_button]:py-2 [&_button]:text-sm [&_button:disabled]:opacity-40"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(search);
        }}
      >
        <input
          className="bg-slate-800 p-2 rounded"
          aria-label="Search IP, domain or JA4"
          placeholder="Search IP, domain or JA4"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="submit">Search</button>
        <select
          aria-label="Node type filter"
          className="bg-slate-800"
          value={type}
          onChange={(e) => setType(e.target.value)}
        >
          {['all', 'host', 'domain', 'ja4', 'ja4s', 'ja4h'].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <select
          aria-label="Graph scope"
          className="rounded bg-slate-800 p-2 text-sm"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
        >
          <option value="neighborhood">Subject neighborhood</option>
          <option value="all">Entire network</option>
        </select>
        <button type="button" onClick={layout}>
          Auto layout
        </button>
        <button
          type="button"
          onClick={() => {
            setSearch('');
            setQuery('');
            setFocus('');
            setType('all');
            setScope('neighborhood');
            setCenter('');
            setSelected(undefined);
          }}
        >
          Reset view
        </button>
        <button
          type="button"
          disabled={!selected || 'source' in selected}
          onClick={() => setFocus(selected?.id || '')}
        >
          Hide unrelated
        </button>
        <button
          type="button"
          onClick={() => {
            void container.current?.requestFullscreen().catch((e) => setError(e.message));
          }}
        >
          Fullscreen
        </button>
      </form>
      <p className="text-sm">
        Legend: HOST blue | DOMAIN purple | JA4/JA4S/JA4H teal | ! indicator orange | risk 60+ red.
        Arrows show direction.
      </p>
      {!id && <p>Select or upload an analysis.</p>}
      {loading && <p role="status">Loading graph…</p>}
      {error && (
        <p role="alert" className="text-red-300">
          {error}
        </p>
      )}
      {data && (
        <p className="text-xs text-slate-400">
          Showing {nodes.length} subjects and entities · {edges.length} relationships
          {scope === 'neighborhood'
            ? ' · Select a subject from the explorer to center its neighborhood.'
            : ' · Entire loaded network.'}{' '}
          {data.truncated && 'Display limited: refine search or focus on a host.'}
        </p>
      )}
      <div
        ref={container}
        className="flex flex-col xl:flex-row gap-3 bg-[#101827] p-2 rounded-xl"
        style={{ minHeight: 650 }}
      >
        <div className="flex-1" style={{ height: 650, minWidth: 0 }}>
          <ReactFlow
            colorMode="dark"
            nodes={nodes.map((n) => ({
              ...n,
              style: {
                ...n.style,
                boxShadow: selected?.id === n.id ? '0 0 0 3px white' : undefined,
                opacity: related && !related.has(n.id) ? 0.25 : 1,
              },
            }))}
            edges={edges.map((e) => ({
              ...e,
              animated: selected?.id === e.id,
              style: {
                ...e.style,
                opacity:
                  selected &&
                  (('source' in selected && selected.id !== e.id) ||
                    (!('source' in selected) &&
                      e.source !== selected.id &&
                      e.target !== selected.id))
                    ? 0.15
                    : 1,
                strokeWidth: selected?.id === e.id ? 4 : e.style?.strokeWidth,
              },
            }))}
            minZoom={0.1}
            maxZoom={2}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={setFlow}
            onNodeClick={(_, n) => {
              const item = data?.nodes.find((x) => x.id === n.id);
              if (item) void inspect(item);
            }}
            onEdgeClick={(_, e) => {
              const item = data?.edges.find((x) => x.id === e.id);
              if (item) void inspect(item);
            }}
            onPaneClick={() => setSelected(undefined)}
            fitView
            onlyRenderVisibleElements
          >
            <Background />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>
        <aside
          className="xl:w-[420px] xl:shrink-0 p-4 max-h-[650px] overflow-auto border border-slate-700 rounded-lg"
          aria-label="Selection details"
        >
          <h2 className="text-lg font-semibold">
            {selected
              ? 'source' in selected
                ? 'Relationship overview'
                : selected.label
              : 'Explore the network'}
          </h2>
          {!selected && (
            <>
              <p className="mt-2 text-sm text-slate-400">
                Select a subject to see traffic and activity. Select a connection line to inspect
                its endpoints, volume and evidence.
              </p>
              <h3 className="mb-3 mt-6 text-xs uppercase tracking-wider text-slate-400">
                Subjects in this view
              </h3>
              <div className="space-y-2">
                {data?.nodes
                  .filter((n) => n.type === 'host')
                  .map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        void inspect(n);
                        flow?.fitView({ nodes: [{ id: n.id }], maxZoom: 1, duration: 500 });
                      }}
                      className="flex w-full items-center justify-between rounded-lg border border-slate-700 bg-slate-800/60 p-3 text-left"
                    >
                      <span className="font-mono text-sm">{n.label}</span>
                      <span
                        className={`text-xs ${n.anomaly_count ? 'text-amber-300' : 'text-slate-400'}`}
                      >
                        {n.anomaly_count
                          ? `${n.anomaly_count} indicators`
                          : `${Number(n.metadata.total_connections || 0)} sessions`}
                      </span>
                    </button>
                  ))}
              </div>
            </>
          )}
          {selected && (
            <>
              <button onClick={() => setSelected(undefined)}>Close details</button>
              {'source' in selected ? (
                <div className="my-4 space-y-4">
                  <div className="rounded-xl border border-blue-400/20 bg-blue-400/5 p-4">
                    <p className="text-xs uppercase tracking-wider text-slate-400">
                      {selected.type.replaceAll('_', ' ')}
                    </p>
                    {[selected.source, selected.target].map((endpoint, i) => (
                      <div key={`${endpoint}:${i}`} className="mt-3">
                        {i === 1 && <p className="mb-2 text-teal-300">↓</p>}
                        <button
                          className="break-all font-mono text-sm text-blue-200 hover:underline"
                          onClick={() => {
                            const node = data?.nodes.find((n) => n.id === endpoint);
                            if (node) void inspect(node);
                          }}
                        >
                          {data?.nodes.find((n) => n.id === endpoint)?.label || endpoint}
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Metric
                      label="Sessions"
                      value={Number(selected.metadata.connection_count || 0)}
                    />
                    <Metric
                      label="Total transferred"
                      value={bytes(selected.metadata.total_bytes)}
                      accent="text-teal-300"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {['protocols', 'ports'].flatMap((k) =>
                      ((selected.metadata[k] as (string | number)[]) || []).map((v) => (
                        <span
                          key={`${k}:${v}`}
                          className="rounded-md bg-slate-700 px-2 py-1 text-xs text-slate-300"
                        >
                          {k === 'ports' ? 'Port ' : ''}
                          {v}
                        </span>
                      )),
                    )}
                  </div>
                </div>
              ) : selected.type === 'host' ? (
                <div className="my-4 space-y-3">
                  <SubjectActivity analysisId={id} subjectId={selected.id} compact />
                  <Link
                    className="inline-block text-sm text-teal-300"
                    to={`/user/behaviorChanges?analysis=${id}`}
                  >
                    Open full activity explorer ↗
                  </Link>
                </div>
              ) : (
                <p className="my-4 break-all rounded-lg bg-slate-800 p-4 text-sm">
                  {selected.type.toUpperCase()} · {selected.label}
                </p>
              )}
              <details className="my-4 rounded-lg border border-slate-700 p-3">
                <summary className="cursor-pointer text-sm text-slate-400">
                  Raw recorded evidence
                </summary>
                <EvidenceDetails record={selected.metadata} />
              </details>
              <h3 className="mt-4 font-medium">Associated anomaly evidence</h3>
              {anomalies.length ? (
                anomalies.map((a) => (
                  <details key={a.id} className="my-2 rounded-lg border border-amber-400/20 p-3">
                    <summary className="cursor-pointer text-sm text-amber-200">
                      {String(a.type || 'Indicator').replaceAll('_', ' ')}
                    </summary>
                    <EvidenceDetails record={a} />
                  </details>
                ))
              ) : (
                <p className="my-3 text-sm text-slate-400">
                  No indicators found for this selection.
                </p>
              )}
              <div className="flex gap-3">
                <button
                  disabled={!anomalyOffset}
                  onClick={() => void inspect(selected, Math.max(0, anomalyOffset - 25))}
                >
                  Previous indicators
                </button>
                <button
                  disabled={anomalyOffset + 25 >= anomalyTotal}
                  onClick={() => void inspect(selected, anomalyOffset + 25)}
                >
                  More indicators
                </button>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
