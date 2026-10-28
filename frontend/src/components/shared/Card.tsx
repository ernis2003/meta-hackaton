import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileArrowUp } from '@fortawesome/free-solid-svg-icons';

type CardType = {
  fillColor: string;
  children: React.ReactNode;
};

const Card = ({ fillColor, children }: CardType) => {
  return (
    <div className="min-w-0 min-h-44 bg-[#1C2633] flex flex-col gap-4 p-5 rounded-xl">
      <div className="flex">
        <FontAwesomeIcon icon={faFileArrowUp} fill={fillColor} className="shrink-0 text-3xl" />
        {children}
      </div>
      <div className="mt-auto ml-auto">
        <button className="text-center py-2 px-3 !rounded-md bg-[#2B3849] hover:cursor-pointer hover:bg-[#283545]">
          Use Example
        </button>
      </div>
    </div>
  );
};

export default Card;
