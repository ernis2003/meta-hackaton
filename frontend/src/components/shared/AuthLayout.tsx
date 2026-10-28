import type { ReactNode } from 'react';

type AuthType = {
  title: string;
  children: ReactNode;
  isloginAdmin: boolean;
  subtitle?: string;
};

const AuthLayout = ({ title, isloginAdmin, children, subtitle }: AuthType) => {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-8 px-4 py-8 sm:px-6 lg:flex-row lg:gap-12 lg:px-10">
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
  );
};

export default AuthLayout;
