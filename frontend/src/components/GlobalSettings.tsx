import React from 'react';
import { Settings, User, Bell, Shield, Database, LogOut, ChevronRight } from 'lucide-react';
import { motion } from 'framer-motion';

export const GlobalSettings = ({ onLogout }: { onLogout: () => void }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="p-6 md:p-10 max-w-[1000px] mx-auto w-full space-y-10"
    >
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold tracking-tight mb-2">Platform Settings</h1>
        <p className="text-text-muted">Manage your profile, notification preferences, and global monitoring defaults.</p>
      </div>

      <div className="space-y-6">
        <section className="glass-panel overflow-hidden">
          <div className="p-8 border-b border-border flex items-center gap-4">
            <div className="p-3 bg-accent/10 text-accent rounded-2xl"><User size={24} /></div>
            <div>
              <h3 className="font-bold text-lg">Account Profile</h3>
              <p className="text-xs text-text-muted">Update your personal information and email address</p>
            </div>
          </div>
          <div className="p-8 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-text-muted uppercase tracking-widest">Email Address</label>
                <input type="email" value="dev@localhost.test" disabled className="w-full bg-white/5 border border-border rounded-xl px-4 py-3 text-sm opacity-50" />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-text-muted uppercase tracking-widest">Organization</label>
                <input type="text" value="Default Workspace" className="w-full bg-white/5 border border-border rounded-xl px-4 py-3 text-sm focus:border-accent outline-none" />
              </div>
            </div>
          </div>
        </section>

        <section className="glass-panel overflow-hidden">
          <div className="p-8 border-b border-border flex items-center gap-4">
            <div className="p-3 bg-warning/10 text-warning rounded-2xl"><Bell size={24} /></div>
            <div>
              <h3 className="font-bold text-lg">Notifications</h3>
              <p className="text-xs text-text-muted">Configure how and when you want to be alerted</p>
            </div>
          </div>
          <div className="p-8 space-y-4">
            {[
              { label: 'Slack Integration', desc: 'Send critical alerts to your #ops channel', active: true },
              { label: 'Email Digests', desc: 'Daily summary of fleet health and performance', active: false },
              { label: 'Webhooks', desc: 'Push incident events to your custom endpoint', active: true }
            ].map((item, i) => (
              <div key={i} className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-border/50">
                <div>
                  <p className="font-bold text-sm">{item.label}</p>
                  <p className="text-xs text-text-muted">{item.desc}</p>
                </div>
                <div className={cn(
                  "w-12 h-6 rounded-full relative transition-colors cursor-pointer",
                  item.active ? "bg-accent" : "bg-white/10"
                )}>
                  <div className={cn(
                    "absolute top-1 w-4 h-4 bg-white rounded-full transition-all",
                    item.active ? "right-1" : "left-1"
                  )} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <button 
          onClick={onLogout}
          className="btn btn-secondary w-full py-4 text-error border-error/20 hover:bg-error/5 hover:border-error/40 flex items-center justify-center gap-2 rounded-2xl"
        >
          <LogOut size={18} />
          <span>Sign Out of Instance</span>
        </button>
      </div>
    </motion.div>
  );
};

// Simple utility for CN if not available in context
const cn = (...classes: any[]) => classes.filter(Boolean).join(' ');
