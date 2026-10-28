type AlertTypesList = 'danger' | 'warning' | 'info';

type AlertType = {
  alertType: AlertTypesList;
  alertTitle: string;
  alertInfo: string;
  onClose?: () => void;
};

const colors = {
  danger: {
    title: 'bg-red-500',
    body: 'border-red-400 bg-red-100 text-red-700',
  },
  warning: {
    title: 'bg-yellow-500',
    body: 'border-yellow-400 bg-yellow-100 text-yellow-700',
  },
  info: {
    title: 'bg-green-500',
    body: 'border-green-400 bg-green-100 text-green-700',
  },
};

const Alert = ({ alertType, alertTitle, alertInfo, onClose }: AlertType) => {
  return (
    <div
      role="alert"
      className="fixed z-[60] inset-x-4 top-4 sm:left-auto sm:right-5 sm:w-full sm:max-w-[350px]"
    >
      <div
        className={`${colors[alertType].title} text-white font-bold rounded-t pl-4 pr-2 py-1 break-words flex items-center justify-between gap-3`}
      >
        <span className="min-w-0">{alertTitle}</span>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close alert"
            className="min-h-11 min-w-11 shrink-0 cursor-pointer rounded hover:bg-black/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        )}
      </div>
      <div
        className={`${colors[alertType].body} border border-t-0 rounded-b px-4 py-3 break-words`}
      >
        {alertInfo}
      </div>
    </div>
  );
};

export default Alert;
