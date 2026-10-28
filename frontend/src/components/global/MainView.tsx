type MainViewType = {
  children: React.ReactNode | null;
};

const MainView = ({ children }: MainViewType) => {
  return <main className="min-w-0 flex-1 px-3 py-4 sm:px-5 md:px-6">{children}</main>;
};

export default MainView;
