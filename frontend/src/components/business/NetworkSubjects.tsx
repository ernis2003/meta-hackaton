import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ReactFlow, Background, Controls, MiniMap, MarkerType, Position, useNodesState, useEdgesState, type Node, type Edge, type ReactFlowInstance } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import '@xyflow/react/dist/style.css';
import AnalysisList from './AnalysisList';
import { api, type Page, type Result } from '../../utils/analyses';
import EvidenceDetails from './EvidenceDetails';

type GraphNode = { id: string; type: string; label: string; metadata: Record<string, unknown>; risk_score: number; anomaly_count: number };
type GraphEdge = { id: string; source: string; target: string; type: string; metadata: Record<string, unknown> };
type Graph = {nodes: GraphNode[]; edges: GraphEdge[]; total_nodes: number; total_edges: number; truncated: boolean};
const colors: Record<string, string> = { host: '#6D98E3', domain: '#9462F1', ja4: '#3FDDBB', ja4s: '#3FDDBB', ja4h: '#3FDDBB' };
export default function NetworkSubjects() {
  return <AnalysisList title="Network Subjects">{analysis => <NetworkGraph key={analysis.id} id={analysis.id} />}</AnalysisList>;
}
function NetworkGraph({id}: {id: string}) {
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');
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
      api<Graph>(`/${id}/graph?limit=300&search=${encodeURIComponent(query)}&focus=${encodeURIComponent(focus)}`)
        .then(value => { if (active) { setData(value); setSelected(undefined); setError(''); } })
        .catch(e => { if (active) { setData(undefined); setNodes([]); setEdges([]); setError(e.message); } })
        .finally(() => { if (active) setLoading(false); });
    }
    return () => { active = false; };
  }, [id, query, focus, setNodes, setEdges]);
  const layout = useCallback(() => {
    if (!data) return;
    const visible = data.nodes.filter(n => type === 'all' || n.type === type || (type !== 'host' && n.type === 'host'));
    const ids = new Set(visible.map(n => n.id));
    const links = data.edges.filter(e => ids.has(e.source) && ids.has(e.target));
    const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    g.setGraph({rankdir: 'LR', nodesep: 45, ranksep: 110});
    visible.forEach(n => g.setNode(n.id, {width: 210, height: 85}));
    links.forEach(e => g.setEdge(e.source, e.target));
    dagre.layout(g);
    setNodes(visible.map(n => ({id: n.id, sourcePosition: Position.Right, targetPosition: Position.Left, position: {x: g.node(n.id).x, y: g.node(n.id).y},
      data: {label: `${n.type.toUpperCase()} | ${n.label}${n.anomaly_count ? ` | ! ${n.anomaly_count} indicators, risk ${n.risk_score}` : ''}`},
      style: {width: 210, background: '#142033', color: '#F9FAFB', border: `2px solid ${n.risk_score >= 60 ? '#F16668' : n.anomaly_count ? '#F59E0B' : colors[n.type]}`, borderRadius: 12, overflowWrap: 'anywhere'}})));
    setEdges(links.map(e => ({id: e.id, source: e.source, target: e.target, label: e.type,
      markerEnd: {type: MarkerType.ArrowClosed}, style: {stroke: (e.metadata.anomalies as string[])?.length ? '#F59E0B' : '#6D98E3'},
      labelStyle: {fill: '#CBD5E1'}, labelBgStyle: {fill: '#142033'}})));
    window.setTimeout(() => void flow?.fitView({padding: .2}), 50);
  }, [data, type, flow, setNodes, setEdges]);
  useEffect(() => { layout(); }, [layout]);
  async function inspect(item: GraphNode | GraphEdge, offset = 0) {
    const request = ++selectionRequest.current;
    setSelected(item); setAnomalies([]);
    setAnomalyOffset(offset); setAnomalyTotal(0);
    try {
      const filter = 'source' in item ? `anomaly_ids=${encodeURIComponent((item.metadata.anomalies as string[] || []).join(','))}` : `subject_id=${encodeURIComponent(item.id)}`;
      const page = await api<Page<Result>>(`/${id}/anomalies?limit=25&offset=${offset}&${filter}`);
      if (selectionRequest.current === request) { setAnomalies(page.items); setAnomalyTotal(page.total); }
    } catch (e) { setError((e as Error).message); }
  }
  const related = selected ? new Set('source' in selected ? [selected.source, selected.target] : [selected.id, ...(data?.edges.filter(e => e.source === selected.id || e.target === selected.id).flatMap(e => [e.source, e.target]) || [])]) : undefined;
  return <div className="flex min-w-0 flex-col gap-4">
    <p>Subjects represent observed IP addresses; shared IPs and NAT do not establish device identity.</p>
    <form className="flex flex-wrap gap-3" onSubmit={e => { e.preventDefault(); setQuery(search); }}>
      <input className="bg-slate-800 p-2 rounded" aria-label="Search IP, domain or JA4" placeholder="Search IP, domain or JA4" value={search} onChange={e => setSearch(e.target.value)} />
      <button type="submit">Search</button>
      <select aria-label="Node type filter" className="bg-slate-800" value={type} onChange={e => setType(e.target.value)}>
        {['all', 'host', 'domain', 'ja4', 'ja4s', 'ja4h'].map(t => <option key={t}>{t}</option>)}
      </select>
      <button type="button" onClick={layout}>Auto layout</button>
      <button type="button" onClick={() => { setSearch(''); setQuery(''); setFocus(''); setType('all'); setSelected(undefined); layout(); }}>Reset view</button>
      <button type="button" disabled={!selected || 'source' in selected} onClick={() => setFocus(selected?.id || '')}>Hide unrelated</button>
      <button type="button" onClick={() => { void container.current?.requestFullscreen().catch(e => setError(e.message)); }}>Fullscreen</button>
    </form>
    <p className="text-sm">Legend: HOST blue | DOMAIN purple | JA4/JA4S/JA4H teal | ! indicator orange | risk 60+ red. Arrows show direction.</p>
    {!id && <p>Select or upload an analysis.</p>}{loading && <p role="status">Loading graph…</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {data && <p>{data.nodes.length} / {data.total_nodes} matching nodes. {data.edges.length} edges. {data.truncated && 'Display limited: refine search or focus on a host.'}</p>}
    <div ref={container} className="flex flex-col xl:flex-row gap-3 bg-[#101827] p-2 rounded-xl" style={{minHeight: 650}}>
      <div className="flex-1" style={{height: 650, minWidth: 0}}>
        <ReactFlow colorMode="dark" nodes={nodes.map(n => ({...n, style: {...n.style, boxShadow: selected?.id === n.id ? '0 0 0 3px white' : undefined, opacity: related && !related.has(n.id) ? .25 : 1}}))}
          edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onInit={setFlow}
          onNodeClick={(_, n) => { const item = data?.nodes.find(x => x.id === n.id); if (item) void inspect(item); }}
          onEdgeClick={(_, e) => { const item = data?.edges.find(x => x.id === e.id); if (item) void inspect(item); }}
          onPaneClick={() => setSelected(undefined)} fitView onlyRenderVisibleElements>
          <Background /><Controls /><MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      <aside className="xl:w-96 p-4 max-h-[650px] overflow-auto border border-slate-700 rounded-lg" aria-label="Selection details">
        <h2 className="text-lg">{selected ? 'Evidence details' : 'Select a host or relationship'}</h2>
        {selected && <><button onClick={() => setSelected(undefined)}>Close details</button>
          <EvidenceDetails record={{...('source' in selected ? {source: selected.source, destination: selected.target, relationship: selected.type} : {label: selected.label, type: selected.type, risk_score: selected.risk_score}), ...selected.metadata}} />
          <h3>Associated anomaly evidence</h3>
          {anomalies.length ? anomalies.map(a => <EvidenceDetails key={a.id} record={a} />) : <p>No indicators found.</p>}
          <div className="flex gap-3"><button disabled={!anomalyOffset} onClick={() => void inspect(selected, Math.max(0, anomalyOffset - 25))}>Previous indicators</button>
            <button disabled={anomalyOffset + 25 >= anomalyTotal} onClick={() => void inspect(selected, anomalyOffset + 25)}>More indicators</button></div></>}
      </aside>
    </div>
  </div>;
}
