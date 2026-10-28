import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import type { IconDefinition } from '@fortawesome/free-solid-svg-icons';

type PageHeaderType = {
  title: string;
  subtitle: string;
  icon: IconDefinition;
};

const PageHeader = ({ title, subtitle, icon }: PageHeaderType) => {
  return (
    <div className="flex items-start gap-3 sm:gap-4">
      <FontAwesomeIcon icon={icon} fill="gray" className="shrink-0 text-3xl sm:text-5xl" />
      <div className="min-w-0 flex flex-col gap-2">
        <h1 className="text-2xl font-bold sm:text-4xl">{title}</h1>
        <label className="text-[gray]">{subtitle}</label>
      </div>
    </div>
  );
};

export default PageHeader;
