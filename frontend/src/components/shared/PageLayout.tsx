type PageLayoutType = {
  children: React.ReactNode;
};
const PageLayout = ({ children }: PageLayoutType) => {
  return <div className="flex min-w-0 flex-col w-full gap-4 sm:p-2">{children}</div>;
};

export default PageLayout;
