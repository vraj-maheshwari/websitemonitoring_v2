import React, { useEffect, useState } from 'react';
import { BarChart3, TrendingUp, Zap, Clock, RefreshCw, Activity } from 'lucide-react';
import { sitesApi, dashboardApi } from '../lib/api';
import { MetricCard } from './MetricCard';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { motion } from 'framer-motion';

export const FleetAnalytics = () => {
  const [sites, setSites] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      sitesApi.list(),
      dashboardApi.getFleetAnalytics(7)
    ]).then(([sitesData, analyticsData]) => {
      setSites(sitesData);
      setAnalytics(analyticsData);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  const avgLatency = sites.reduce((acc, s) => acc + (s.last_response_time || 0), 0) / (sites.length || 1);
  const upSites = sites.filter(s => s.current_status === 'UP').length;

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 md:p-10 max-w-[1400px] mx-auto w-full space-y-10"
    >
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold tracking-tight mb-2">Fleet Analytics</h1>
        <p className="text-text-muted">Performance aggregation and trend analysis for your monitoring network.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard label="Global Availability" value={`${Math.round((upSites / (sites.length || 1)) * 100)}%`} icon={Activity} trend="up" trendValue="99.9%" />
        <MetricCard label="Fleet Avg Latency" value={`${Math.round(avgLatency * 1000)}ms`} icon={Zap} trend="up" trendValue="Stable" />
        <MetricCard label="Checks / Hour" value={(sites.length * 60).toString()} icon={Clock} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="glass-panel p-8">
          <h3 className="font-bold text-lg mb-8 flex items-center gap-2">
            <TrendingUp size={20} className="text-accent" />
            Response Time Distribution
          </h3>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sites.map(s => ({ name: (s.name || s.url).substring(0, 10), val: Math.round((s.last_response_time || 0) * 1000) }))}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} />
                <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: '#0F172A', border: 'none', borderRadius: '12px'}} />
                <Bar dataKey="val" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-panel p-8">
          <h3 className="font-bold text-lg mb-8 flex items-center gap-2">
            <Activity size={20} className="text-success" />
            Fleet Uptime Trend (Last 7 Days)
          </h3>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics?.uptime_trend || []}>
                <defs>
                  <linearGradient id="colorUp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} domain={[0, 100]} />
                <Tooltip contentStyle={{backgroundColor: '#0F172A', border: 'none', borderRadius: '12px'}} />
                <Area type="monotone" dataKey="up" stroke="#10B981" fillOpacity={1} fill="url(#colorUp)" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
