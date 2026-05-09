import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

interface MetricCardProps {
  label: string;
  value: string;
  trend?: 'up' | 'down';
  trendValue?: string;
  icon: LucideIcon;
}

export const MetricCard = ({ label, value, trend, trendValue, icon: Icon }: MetricCardProps) => (
  <div className="bg-background-card border border-border p-6 rounded-card hover:border-border-strong transition-all duration-300 group">
    <div className="flex justify-between items-start mb-4">
      <div className="p-2 bg-white/5 rounded-lg group-hover:bg-accent/10 transition-colors">
        <Icon size={20} className="text-text-secondary group-hover:text-accent transition-colors" />
      </div>
      {trend && (
        <span className={cn(
          "flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full",
          trend === 'up' ? "bg-success/10 text-success" : "bg-error/10 text-error"
        )}>
          {trendValue}
          <ArrowUpRight size={12} className={trend === 'down' ? "rotate-90" : ""} />
        </span>
      )}
    </div>
    <div>
      <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <h3 className="text-2xl font-bold text-text-primary tracking-tight">{value}</h3>
    </div>
  </div>
);
