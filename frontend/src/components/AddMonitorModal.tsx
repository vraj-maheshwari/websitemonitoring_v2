import React, { useState } from 'react';
import { X, Globe, Clock, ChevronRight } from 'lucide-react';
import { sitesApi } from '../lib/api';

interface AddMonitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AddMonitorModal = ({ isOpen, onClose, onSuccess }: AddMonitorModalProps) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [interval, setInterval] = useState(60);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await sitesApi.create({ name, url, check_interval: interval });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to add site");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background-primary/60 backdrop-blur-md">
      <div className="bg-background-card border border-border w-full max-w-md rounded-card shadow-premium animate-in fade-in zoom-in duration-200">
        <div className="flex justify-between items-center p-6 border-b border-border">
          <h2 className="text-xl font-bold">Add New Monitor</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary p-1 rounded-md hover:bg-white/5 transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="p-3 bg-error/10 border border-error/20 text-error text-sm rounded-lg">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">Display Name (Optional)</label>
              <input 
                type="text" 
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Awesome App"
                className="w-full bg-white/5 border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-accent transition-all"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">Website URL</label>
              <div className="relative">
                <Globe size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input 
                  type="text" 
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full bg-white/5 border border-border rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">Check Interval (Seconds)</label>
              <div className="relative">
                <Clock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <select 
                  value={interval}
                  onChange={(e) => setInterval(parseInt(e.target.value))}
                  className="w-full bg-white/5 border border-border rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent transition-all appearance-none"
                >
                  <option value={30}>30 Seconds</option>
                  <option value={60}>1 Minute</option>
                  <option value={300}>5 Minutes</option>
                  <option value={3600}>1 Hour</option>
                </select>
              </div>
            </div>
          </div>

          <div className="pt-4 flex gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">
              {loading ? "Adding..." : "Start Monitoring"}
              <ChevronRight size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
