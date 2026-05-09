import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  Activity, 
  BarChart3, 
  Globe, 
  ShieldCheck, 
  Settings,
  Plus
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

interface SidebarLinkProps {
  to: string;
  icon: LucideIcon;
  label: string;
}

const SidebarLink = ({ to, icon: Icon, label }: SidebarLinkProps) => {
  const location = useLocation();
  const active = location.pathname === to;
  
  return (
    <NavLink to={to} className={cn(
      "flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group",
      active ? "bg-accent/10 text-accent" : "text-text-secondary hover:text-text-primary hover:bg-white/5"
    )}>
      <Icon size={18} className={cn(active ? "text-accent" : "text-text-muted group-hover:text-text-primary")} />
      <span className="text-sm font-semibold">{label}</span>
    </NavLink>
  );
};

interface SidebarProps {
  onAddClick: () => void;
}

export const Sidebar = ({ onAddClick }: SidebarProps) => {
  return (
    <aside className="w-72 border-r border-border flex flex-col p-6 shrink-0 bg-background-primary/50 backdrop-blur-xl sticky top-0 h-screen overflow-y-auto">
      <div className="flex items-center gap-3 px-3 mb-10">
        <div className="w-9 h-9 bg-accent rounded-xl flex items-center justify-center font-black text-white shadow-lg shadow-accent/20">P</div>
        <span className="font-bold text-xl tracking-tight">Pulse</span>
      </div>

      <nav className="flex flex-col gap-1.5 flex-1">
        <div className="text-[10px] font-bold text-text-muted uppercase tracking-[0.2em] px-4 mb-3">Monitor</div>
        <SidebarLink to="/" icon={Globe} label="Overview" />
        <SidebarLink to="/incidents" icon={Activity} label="Incidents" />
        <SidebarLink to="/analytics" icon={BarChart3} label="Analytics" />
        
        <div className="text-[10px] font-bold text-text-muted uppercase tracking-[0.2em] px-4 mb-3 mt-8">System</div>
        <SidebarLink to="/security" icon={ShieldCheck} label="Security Audit" />
        <SidebarLink to="/settings" icon={Settings} label="Global Settings" />

        <div className="mt-8 px-2">
          <button 
            onClick={onAddClick}
            className="w-full btn btn-primary py-3 rounded-xl shadow-lg shadow-accent/10 flex items-center justify-center gap-2 text-xs font-bold"
          >
            <Plus size={14} />
            Add Monitor
          </button>
        </div>
      </nav>

      <div className="mt-auto pt-6 border-t border-border">
        <div className="flex items-center gap-3 px-3 bg-white/5 p-3 rounded-2xl border border-border/50">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-accent to-blue-400 p-0.5">
             <div className="w-full h-full rounded-[10px] bg-background-primary flex items-center justify-center text-[10px] font-bold">DEV</div>
          </div>
          <div className="overflow-hidden">
            <p className="text-xs font-bold truncate text-text-primary">dev@localhost</p>
            <p className="text-[10px] text-text-muted truncate font-medium">Enterprise Access</p>
          </div>
        </div>
      </div>
    </aside>
  );
};
