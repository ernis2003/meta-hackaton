import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { faFileArrowUp, faCloudArrowUp, faFolderOpen } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import Card from '../shared/Card';
import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';
import { api, selectAnalysis, type Analysis } from '../../utils/analyses';

const cardsInfo = {
  'Normal Traffic': { Subtitle: 'Clean network traffic example', Color: '#6D98E3', filename: 'normal.pcap' },
  'Suspicious Traffic': { Subtitle: 'Contains known suspicious patterns', Color: '#F16668', filename: 'suspicious.pcap' },
  'Mixed Traffic': { Subtitle: 'Realistic enterprice traffic sample', Color: '#9462F1', filename: 'mixed.pcap' },
};

export default function UploadFile() {
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  function openResults(result: Analysis) {
    selectAnalysis(result.id);
    setStatus(result.status);
    if (result.status === 'completed') navigate(`/user/networkSubjects?analysis=${encodeURIComponent(result.id)}`);
  }

  async function example(name: string) {
    if (busy) return;
    setBusy(true);
    setStatus('Processing example with Zeek...');
    try {
      openResults(await api<Analysis>(`/examples/${encodeURIComponent(name)}`, { method: 'POST' }));
    } catch (error) { setStatus((error as Error).message); }
    finally { setBusy(false); }
  }

  async function upload(file?: File) {
    if (!file || busy) return;
    if (file.size > 100 * 1024 * 1024) { setStatus('Maximum file size is 100 MiB.'); return; }
    setBusy(true);
    setStatus('Uploading and processing with Zeek...');
    const body = new FormData();
    body.append('file', file);
    try { openResults(await api<Analysis>('', { method: 'POST', body })); }
    catch (error) { setStatus((error as Error).message); }
    finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <PageLayout>
      <div className="flex flex-col">
        <PageHeader
          icon={faFileArrowUp}
          title="Upload PCAP File"
          subtitle="Upload a network capture file to extract JA4 fingerptints analyze network behaviour and detect potential threats"
        />
        <div
          className="mx-auto border border-dashed border-[gray] w-full my-5 rounded-3xl max-w-[1000px] min-h-64 sm:min-h-80 p-5 flex hover:bg-[#1C2633] hover:cursor-pointer"
          onClick={() => { if (!busy) input.current?.click(); }}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); void upload(e.dataTransfer.files[0]); }}
          aria-busy={busy}
        >
          <div className="mx-auto flex flex-col items-center justify-center gap-6 w-full">
            <FontAwesomeIcon icon={faCloudArrowUp} className="text-6xl sm:text-8xl mx-auto" fill="#3FDDBB" />
            <label className="text-[gray] mx-auto hover:cursor-pointer">or click to browse</label>
            <button
              type="button"
              disabled={busy}
              className="inline-flex items-center text-black bg-[#3FDDBB] focus:ring-4 shadow-xs font-medium leading-5 rounded-lg text-sm px-4 py-3 focus:outline-none hover:cursor-pointer hover:text-white"
            >
              <FontAwesomeIcon icon={faFolderOpen} className="hover:text-white" />
              Choose PCAP File
            </button>
            <input
              ref={input}
              id="dropzone-file-2"
              aria-label="PCAP file"
              type="file"
              accept=".pcap,.pcapng"
              className="hidden"
              disabled={busy}
              onClick={e => e.stopPropagation()}
              onChange={e => void upload(e.target.files?.[0])}
            />
          </div>
        </div>
        {status && <p role="status" aria-live="polite">{status}</p>}
      </div>

      <h3>Try an exapmle file</h3>
      <label className="text-[gray]">
        Not sure where to start? Use one of our sample PCAP files to explore the analysis features
      </label>
      <div className="grid grid-cols-1 gap-3 w-full xl:grid-cols-3">
        {Object.entries(cardsInfo).map(([title, info]) => (
          <Card key={title} fillColor={info.Color} disabled={busy} onUseExample={() => void example(info.filename)}>
            <div className="flex flex-col ms-3">
              <div className="text-xl text-bold">{title}</div>
              <div className="text-md text-thin mt-3">{info.Subtitle}</div>
            </div>
          </Card>
        ))}
      </div>
      <div></div>
    </PageLayout>
  );
}
