import type { ReactNode } from 'react';

type AuthType = {
  title: string;
  children: ReactNode;
  isloginAdmin: boolean;
  subtitle?: string;
};

const AuthLayout = ({ title, isloginAdmin, children, subtitle }: AuthType) => {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-8 sm:px-6 lg:px-10">
      <div className="grid w-full max-w-5xl grid-cols-1 items-center justify-items-center gap-8 lg:grid-cols-2 lg:gap-12">
        <div className="w-full max-w-md text-center">
          <h1 className="!text-center text-3xl sm:text-5xl">{title}</h1>
          <div className="flex w-full mt-[15px]">
            <span className="ms-auto me-auto !text-[#3FDDBB]">
              {subtitle ?? `Login as ${isloginAdmin ? 'admin' : 'user'}!`}
            </span>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
};

export default AuthLayout;
