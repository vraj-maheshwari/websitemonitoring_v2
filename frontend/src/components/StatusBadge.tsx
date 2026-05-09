import React from 'react';
import { cn } from '../lib/utils';

interface StatusBadgeProps {
  status: 'up' | 'down' | 'degraded' | 'checking' | 'pending';
}

export const StatusBadge = ({ status }: StatusBadgeProps) => {
  const configs = {
    up: { label: 'Operational', dot: 'bg-success', text: 'text-success' },
    down: { label: 'Down', dot: 'bg-error', text: 'text-error' },
    degraded: { label: 'Degraded', dot: 'bg-warning', text: 'text-warning' },
    checking: { label: 'Checking', dot: 'bg-accent animate-pulse', text: 'text-accent' },
    pending: { label: 'Pending', dot: 'bg-text-muted', text: 'text-text-muted' },
  };
  
  const config = configs[status] || configs.pending;
  
  return (
    <div className="flex items-center gap-2">
      <span className={cn("w-1.5 h-1.5 rounded-full", config.dot)} />
      <span className={cn("text-[13px] font-medium", config.text)}>{config.label}</span>
    </div>
  );
};
