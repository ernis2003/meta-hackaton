import { useState } from 'react';
import { clearAuth } from '../../utils/auth';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faRightFromBracket, faFingerprint } from '@fortawesome/free-solid-svg-icons';

import { useNavigate } from 'react-router-dom';
import { userSideBarStructure, adminSideBarStructure } from '../../data/sidebar';

type SideBarType = {
  targetUser: string;
  activeTab: string;
};

const SideBar = ({ targetUser, activeTab }: SideBarType) => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);

  const targetDict = targetUser == 'admin' ? adminSideBarStructure : userSideBarStructure;

  return (
    <aside className="w-full shrink-0 md:w-64 md:sticky md:top-0 md:h-dvh flex flex-col shadow-[5px_0px_11px_2px_rgba(62,_220,_188,_0.5)]">
      <div className="w-full p-3 !pb-5 text-xl color-[#F9FAFB] text-center flex gap-3">
        <FontAwesomeIcon icon={faFingerprint} className="pt-2" fill="#3EDCBC" />
        Forensics Analysis
        <button
          type="button"
          className="ml-auto min-h-11 px-3 rounded-md bg-[#1E3A5F] text-sm md:hidden"
          aria-expanded={isOpen}
          aria-controls="sidebar-navigation"
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? 'Close' : 'Menu'}
        </button>
      </div>
      <nav
        id="sidebar-navigation"
        aria-label="Main navigation"
        className={`${isOpen ? 'flex' : 'hidden'} md:flex flex-col w-full min-h-0 flex-1 overflow-y-auto px-3 pb-3`}
      >
        {Object.entries(targetDict).map(([item, [itemIcon, path]]) => {
          return (
            <div
              key={item}
              className={`w-full flex min-h-12 rounded-md hover:bg-[#1E3A5F]
                                            hover:text-[#F9FAFB] hover:cursor-pointer
                                            transition-colors !ps-3`}
            >
              <div className="pt-3">
                <FontAwesomeIcon icon={itemIcon} />
              </div>
              <button
                className="w-full px-4 py-3 text-left
                                            bg-transparent
                                            text-[#9CA3AF]
                                            hover:cursor-pointer hover:text-white"
                onClick={() => {
                  navigate(path);
                  setIsOpen(false);
                }}
              >
                {item}
              </button>
              {activeTab == item ? (
                <span className="bg-[#3FDDBB] w-[5px] h-[5px] rounded-xl !h-full"></span>
              ) : (
                <></>
              )}
            </div>
          );
        })}
        <div
          className={`!mt-auto w-full min-h-12 flex rounded-md hover:bg-[#1E3A5F]
                                            hover:text-[#F9FAFB] hover:cursor-pointer
                                            transition-colors !ps-3`}
        >
          <div className="pt-3">
            <FontAwesomeIcon icon={faRightFromBracket} />
          </div>
          <button
            className="w-full px-4 py-3 text-left
                                    bg-transparent
                                    text-[#9CA3AF]
                                    hover:cursor-pointer hover:text-white text-center"
            onClick={() => {
              navigate('/');
              clearAuth();
            }}
          >
            Log out
          </button>
        </div>
      </nav>
    </aside>
  );
};

export default SideBar;
