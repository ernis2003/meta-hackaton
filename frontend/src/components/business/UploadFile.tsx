import { faFileArrowUp, faCloudArrowUp, faFolderOpen } from '@fortawesome/free-solid-svg-icons';
import Card from '../shared/Card';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import PageHeader from '../shared/PageHeader';
import PageLayout from '../shared/PageLayout';

type CardInfo = {
  Subtitle: string;
  Color: string;
};

type CardsInfo = Record<string, CardInfo>;

const UploadFile = () => {
  const handleBrowse = (): void => {
    const inputEl = document.getElementById('dropzone-file-2');
    if (inputEl) {
      inputEl.click();
    }
  };
  const cardsInfo: CardsInfo = {
    'Normal Traffic': { Subtitle: 'Clean network traffic example', Color: '#6D98E3' },
    'Suspicious Traffic': { Subtitle: 'Contains known suspicious patterns', Color: '#F16668' },
    'Mixed Traffic': { Subtitle: 'Realistic enterprice traffic sample', Color: '#9462F1' },
  };

  return (
    <PageLayout>
      {/* Upload */}
      <div className="flex flex-col">
        <PageHeader
          icon={faFileArrowUp}
          title="Upload PCAP File"
          subtitle="Upload a network capture file to extract JA4 fingerptints analyze network behaviour and detect potential threats"
        />
        <div
          className="mx-auto border border-dashed border-[gray] w-full my-5 rounded-3xl max-w-[1000px] min-h-64 sm:min-h-80 p-5 flex hover:bg-[#1C2633] hover:cursor-pointer"
          onClick={handleBrowse}
        >
          <div className="mx-auto flex flex-col items-center justify-center gap-6 w-full">
            <FontAwesomeIcon
              icon={faCloudArrowUp}
              className="text-6xl sm:text-8xl mx-auto"
              fill="#3FDDBB"
            />
            <label className="text-[gray] mx-auto hover:cursor-pointer">or click to browse</label>
            <button
              type="button"
              className="inline-flex items-center text-black bg-[#3FDDBB] focus:ring-4 shadow-xs font-medium leading-5 rounded-lg text-sm px-4 py-3 focus:outline-none hover:cursor-pointer hover:text-white"
            >
              <FontAwesomeIcon icon={faFolderOpen} className="hover:text-white" />
              Choose PCAP File
            </button>
            <input id="dropzone-file-2" type="file" accept=".pcap,.pcapng" className="hidden" />
          </div>
        </div>
      </div>

      {/* File examples */}
      <h3>Try an exapmle file</h3>
      <label className="text-[gray]">
        Not sure where to start? Use one of our sample PCAP files to explore the analysis features
      </label>
      <div className="grid grid-cols-1 gap-3 w-full xl:grid-cols-3">
        {Object.entries(cardsInfo).map(([title, info]) => {
          return (
            <Card key={title} fillColor={info.Color}>
              <div className="flex flex-col ms-3">
                <div className="text-xl text-bold">{title}</div>
                <div className="text-md text-thin mt-3">{info.Subtitle}</div>
              </div>
            </Card>
          );
        })}
      </div>
      {/* Recent uploads */}
      <div></div>
    </PageLayout>
  );
};

export default UploadFile;
