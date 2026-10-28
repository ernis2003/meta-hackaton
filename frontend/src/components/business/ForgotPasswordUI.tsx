import Alert from '../shared/Alert';
import { useState } from 'react';

type ForgotPasswordUIType = {
  onClose?: () => void;
};
type eventType = React.MouseEvent<HTMLButtonElement, MouseEvent>;

const ForgotPasswordUI = ({ onClose }: ForgotPasswordUIType) => {
  const [Submit, setSubmit] = useState(false);

  function handleSubmit(e: eventType) {
    e.preventDefault();
    setSubmit(true);
  }
  return (
    <div className="p-3 flex flex-col w-full h-full">
      {Submit && (
        <Alert
          alertType="info"
          alertInfo="Please check your email for a restore link"
          alertTitle="We got your request"
          onClose={() => setSubmit(false)}
        />
      )}
      <div className="flex !flex-col !gap-4">
        <form className="w-full sm:w-3/4 mx-auto flex flex-col !gap-5 my-4">
          <label htmlFor="input-group-1" className="block mb-1.5 text-sm font-medium text-heading">
            Your Email
          </label>
          <div className="relative w-full">
            <div className="absolute inset-y-0 start-0 flex items-center ps-3 pointer-events-none">
              <svg
                className="w-4 h-4 text-body"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                fill="none"
                viewBox="0 0 24 24"
              >
                <path
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeWidth="2"
                  d="m3.5 5.5 7.893 6.036a1 1 0 0 0 1.214 0L20.5 5.5M4 19h16a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1Z"
                />
              </svg>
            </div>
            <input
              type="text"
              id="input-group-1"
              className="block !w-full ps-9 pe-3 py-2.5 bg-neutral-secondary-medium border border-default-medium text-heading text-sm !rounded-lg focus:ring-brand focus:border-brand shadow-xs placeholder:text-body"
              placeholder="name@flowbite.com"
            ></input>
          </div>
          <button
            className="!bg-[#3FDDBB]
                        text-white
                        rounded-lg
                        py-2 w-[50%]
                        mx-auto hover:cursor-pointer
                        hover:bg-[#2FC9A8]!
                        font-semibold"
            onClick={(e) => {
              handleSubmit(e);
            }}
          >
            Submit
          </button>
        </form>
        <div className="text-center">
          <a
            className="text-[#3FDDBB]
                              hover:text-[#2FC9A8]
                              hover:cursor-pointer
                              font-semibold"
            onClick={() => {
              onClose?.();
            }}
          >
            Back To Sign In
          </a>
        </div>
      </div>
    </div>
  );
};
export default ForgotPasswordUI;
