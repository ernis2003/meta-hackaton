import type { ReactNode } from 'react';

type ModalSize = 's' | 'md' | 'lg' | 'xxl';

type ModalViewProps = {
  modalSize?: ModalSize;
  modalTitle: string;
  subText: string;
  children: ReactNode;
  onClose?: () => void;
};

const modalSizes: Record<ModalSize, string> = {
  s: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xxl: 'max-w-5xl',
};

const ModalView = ({
  modalSize = 'md',
  modalTitle,
  subText,
  children,
  onClose,
}: ModalViewProps) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={modalTitle}
        className={`flex w-full ${modalSizes[modalSize]} max-h-[calc(100dvh-2rem)] flex-col overflow-hidden rounded-xl border border-gray-700 bg-[#151515] text-white shadow-xl`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-gray-700 px-4 py-3 sm:px-6 sm:py-4">
          <h2 className="text-lg font-semibold">{modalTitle}</h2>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close modal"
              className="min-h-11 min-w-11 shrink-0 cursor-pointer text-gray-400 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-y-auto w-full flex flex-col">
          <label className="text-center px-4 mx-auto pt-2">{subText}</label>
          {children}
        </div>
      </div>
    </div>
  );
};

export default ModalView;
