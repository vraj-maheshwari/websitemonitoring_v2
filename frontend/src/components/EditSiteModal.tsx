import React, { useState } from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Site } from '../types';

interface EditSiteModalProps {
  site: Site;
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: any) => Promise<void>;
}

export const EditSiteModal = ({ site, isOpen, onClose, onSave }: EditSiteModalProps) => {
  const [formData, setFormData] = useState({
    name: site.name || '',
    uptime_check_interval: site.uptime_check_interval / 60,
    ssl_check_interval: site.ssl_check_interval / 3600,
    seo_check_interval: site.seo_check_interval / 3600,
  });

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-background-primary/80 backdrop-blur-sm"
        />
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative bg-background-card border border-border w-full max-w-md rounded-card shadow-premium p-8"
        >
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">Edit Site Config</h2>
            <button onClick={onClose} className="text-text-muted hover:text-text-primary">
              <X size={20} />
            </button>
          </div>

          <form onSubmit={(e) => {
            e.preventDefault();
            onSave({
              name: formData.name,
              uptime_check_interval: formData.uptime_check_interval * 60,
              ssl_check_interval: formData.ssl_check_interval * 3600,
              seo_check_interval: formData.seo_check_interval * 3600,
            });
          }} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-text-muted uppercase mb-2">Display Name</label>
              <input 
                type="text" 
                value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
                className="w-full bg-white/5 border border-border rounded-sm px-4 py-2 text-sm focus:border-accent outline-none transition-colors"
                placeholder="Auto-generated if empty"
              />
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase mb-2">Uptime Interval (min)</label>
                <input 
                  type="number" 
                  value={formData.uptime_check_interval}
                  onChange={e => setFormData({...formData, uptime_check_interval: parseInt(e.target.value)})}
                  className="w-full bg-white/5 border border-border rounded-sm px-4 py-2 text-sm focus:border-accent outline-none transition-colors"
                  min="1"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase mb-2">SSL Interval (hours)</label>
                <input 
                  type="number" 
                  value={formData.ssl_check_interval}
                  onChange={e => setFormData({...formData, ssl_check_interval: parseInt(e.target.value)})}
                  className="w-full bg-white/5 border border-border rounded-sm px-4 py-2 text-sm focus:border-accent outline-none transition-colors"
                  min="1"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase mb-2">SEO Interval (hours)</label>
                <input 
                  type="number" 
                  value={formData.seo_check_interval}
                  onChange={e => setFormData({...formData, seo_check_interval: parseInt(e.target.value)})}
                  className="w-full bg-white/5 border border-border rounded-sm px-4 py-2 text-sm focus:border-accent outline-none transition-colors"
                  min="1"
                />
              </div>
            </div>

            <div className="pt-4 flex gap-3">
              <button type="submit" className="flex-1 btn btn-primary py-3">Save Changes</button>
              <button type="button" onClick={onClose} className="flex-1 btn btn-secondary py-3">Cancel</button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
