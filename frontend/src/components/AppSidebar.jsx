import React from 'react';
import { motion } from 'framer-motion';
import { Activity, ChevronRight, LogOut, Menu, Shield, Upload, User, Users } from 'lucide-react';

const NavItem = ({
  icon: Icon,
  label,
  active,
  sidebarOpen,
  onClick,
  disabled = false,
  showChevron = false,
  rightAdornment = null,
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`w-full flex items-center ${sidebarOpen ? 'justify-between px-3 py-2' : 'justify-center px-2 py-3'} rounded-md border-l-[3px] ${active ? 'bg-indigo-50 text-slate-900 shadow-sm ring-1 ring-indigo-200 border-l-indigo-600' : 'text-slate-600 hover:bg-slate-100/80 disabled:opacity-30 border-l-transparent'}`}
  >
    <div className="flex items-center min-w-0">
      <Icon className="w-4 h-4 shrink-0" />
      <span className={`ml-2 text-sm font-medium ${sidebarOpen ? '' : 'sr-only'}`}>{label}</span>
    </div>
    {sidebarOpen && rightAdornment}
    {sidebarOpen && showChevron && <ChevronRight className="w-4 h-4" />}
  </button>
);

const AppSidebar = ({
  sidebarOpen,
  setSidebarOpen,
  currentUser,
  activeView,
  onNavigate,
  onRequestLogout,
  onOpenAccountSwitcher,
  medsLength,
  profileRequired,
  profileNudgeVisible,
}) => {
  const displayName = currentUser?.profile?.patient_name || currentUser?.name || 'User';
  const initials = displayName
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'U';

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarOpen ? 256 : 72 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="relative shrink-0 h-screen border-r border-slate-200/70 bg-white/90 backdrop-blur overflow-hidden"
    >
      <div className={`h-full ${sidebarOpen ? 'p-4 pb-16' : 'p-3 pb-16'} space-y-3 overflow-hidden`}>
        {sidebarOpen ? (
          <div className="bg-white rounded-lg shadow-sm ring-1 ring-slate-900/5 p-3">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold text-sm shrink-0">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-slate-900 text-sm font-semibold leading-tight wrap-break-word">{displayName}</h3>
                <p className="text-[11px] text-slate-500 mt-1 break-all leading-tight">{currentUser?.email || ''}</p>
              </div>
            </div>
            <button
              onClick={onOpenAccountSwitcher}
              className="w-full mb-2 text-xs text-indigo-600 hover:text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition-all font-medium inline-flex items-center justify-center gap-1"
            >
              <Users className="w-3.5 h-3.5" /> Switch Account
            </button>
            <button
              onClick={onRequestLogout}
              className="w-full text-xs text-red-500 hover:text-red-600 border border-red-200 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-all font-medium"
            >
              Logout
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-2">
            <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold text-sm shrink-0">
              {initials}
            </div>
            <button
              onClick={onRequestLogout}
              className="p-2 hover:bg-red-50 rounded-lg text-red-500 hover:text-red-600 border border-red-200 transition-colors"
              aria-label="Logout"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}

        <nav className="space-y-1">
          <NavItem
            icon={Activity}
            label="Dashboard"
            active={activeView === 'dashboard'}
            sidebarOpen={sidebarOpen}
            onClick={() => onNavigate('dashboard')}
            showChevron={activeView === 'dashboard'}
          />
          <NavItem
            icon={Shield}
            label="Safety Analysis"
            active={activeView === 'safety'}
            sidebarOpen={sidebarOpen}
            onClick={() => medsLength >= 2 && onNavigate('safety')}
            disabled={medsLength < 2}
            showChevron={activeView === 'safety'}
          />
          <NavItem
            icon={Upload}
            label="Prescriptions"
            active={activeView === 'history'}
            sidebarOpen={sidebarOpen}
            onClick={() => onNavigate('history')}
            showChevron={activeView === 'history'}
          />
          <NavItem
            icon={User}
            label="Profile"
            active={activeView === 'profile'}
            sidebarOpen={sidebarOpen}
            onClick={() => onNavigate('profile')}
            rightAdornment={profileNudgeVisible && profileRequired ? (
              <span className="ml-2 rounded-full bg-amber-100 text-amber-700 border border-amber-200 px-2 py-0.5 text-[10px] font-semibold animate-pulse">
                Complete
              </span>
            ) : null}
            showChevron={activeView === 'profile'}
          />
        </nav>

        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute bottom-4 left-4 inline-flex items-center justify-center w-10 h-10 rounded-lg border border-slate-200 bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-sm"
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>
    </motion.aside>
  );
};

export default AppSidebar;
