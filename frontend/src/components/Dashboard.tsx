import { useEffect, useState } from 'react';
import { 
  ChevronRight, Plus, Search, RefreshCw, Activity, 
  Zap, Lock, Globe2, AlertCircle, CheckCircle2 
} from 'lucide-react';
import { MetricCard } from './MetricCard';
import { StatusBadge } from './StatusBadge';
import { sitesApi, dashboardApi } from '../lib/api';
import type { Site, DashboardMetrics, DashboardActivity } from '../types';
import { cn } from '../lib/utils';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';

interface DashboardProps {
  onAddClick: () => void;
}

export const Dashboard = ({ onAddClick }: DashboardProps) => {
  const [sites, setSites] = useState<Site[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [activities, setActivities] = useState<DashboardActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchData = async () => {
    try {
      const [sitesData, metricsData, activityData] = await Promise.all([
        sitesApi.list(),
        dashboardApi.getMetrics(),
        dashboardApi.getActivity()
      ]);
      setSites(sitesData);
      setMetrics(metricsData);
      setActivities(activityData);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Auto refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const filteredSites = sites.filter(s => 
    s.url.toLowerCase().includes(searchQuery.toLowerCase()) || 
    (s.name && s.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const incidents = sites.filter(s => 
    s.current_status === 'DOWN' || 
    (s.ssl_days_remaining !== null && s.ssl_days_remaining < 14) ||
    s.dns_status === 'failed' ||
    s.dns_hijack_suspected ||
    s.dns_ns_changed
  );

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  const healthScore = metrics?.health_score || 0;
  const healthLabel = healthScore >= 90 ? 'All Systems Healthy' : healthScore >= 60 ? 'Degraded Performance' : 'Critical Action Required';
  const healthColor = healthScore >= 90 ? 'text-success' : healthScore >= 60 ? 'text-warning' : 'text-error';

  return (
    <div className="p-6 md:p-10 max-w-[1400px] mx-auto w-full space-y-10">
      {/* Health Hero Section */}
      <section className="glass-panel p-10 overflow-hidden relative group">
        <div className="absolute top-0 right-0 -mt-20 -mr-20 w-64 h-64 bg-accent/10 rounded-full blur-3xl group-hover:bg-accent/20 transition-all duration-700" />
        <div className="relative z-10 flex flex-col md:flex-row items-center gap-10">
          <div className="relative">
            <div className={cn(
              "w-32 h-32 rounded-full border-8 flex items-center justify-center text-4xl font-black shadow-2xl",
              healthScore >= 90 ? "border-success bg-success/5 text-success" : 
              healthScore >= 60 ? "border-warning bg-warning/5 text-warning" : "border-error bg-error/5 text-error"
            )}>
              {healthScore}
            </div>
            <div className="absolute -bottom-2 -right-2 bg-background-card p-1.5 rounded-full border border-border">
              <Activity size={16} className={healthColor} />
            </div>
          </div>
          <div className="text-center md:text-left flex-1">
            <h1 className={cn("text-4xl font-black tracking-tight mb-2", healthColor)}>
              {healthLabel}
            </h1>
            <p className="text-text-secondary font-medium">
              <span className={cn("inline-block w-2 h-2 rounded-full mr-2", healthScore >= 90 ? "bg-success" : "bg-warning")} />
              {metrics?.sites_up} of {metrics?.monitored_sites} sites operational
              {metrics?.sites_down ? <span className="ml-2 text-error">· {metrics.sites_down} critical failures</span> : null}
            </p>
          </div>
          <button 
            onClick={onAddClick}
            className="btn btn-primary px-8 py-4 rounded-full shadow-lg shadow-accent/20 flex items-center gap-2 group"
          >
            <Plus size={18} className="group-hover:rotate-90 transition-transform" />
            Add New Monitor
          </button>
        </div>
      </section>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard label="Fleet Uptime" value={`${Math.round((metrics?.sites_up || 0) / (metrics?.monitored_sites || 1) * 100)}%`} icon={Activity} />
        <MetricCard 
          label="DNS Health" 
          value={metrics?.dns_issue_count === 0 ? "Healthy" : `${metrics?.dns_issue_count} Issues`} 
          icon={Globe2}
          trend={metrics?.dns_issue_count === 0 ? 'up' : 'down'}
        />
        <MetricCard label="Avg Latency" value={metrics?.avg_response ? `${Math.round(metrics.avg_response * 1000)}ms` : '—'} icon={Zap} />
        <MetricCard 
          label="SSL Security" 
          value={metrics?.ssl_critical_count === 0 ? "All Valid" : `${metrics?.ssl_critical_count} Expiring`} 
          icon={Lock}
          trend={metrics?.ssl_critical_count === 0 ? 'up' : 'down'}
        />
        <MetricCard label="SEO Health" value={metrics?.seo_avg_score ? `${metrics.seo_avg_score}/100` : '—'} icon={Globe2} />
      </div>

      {/* Active Incidents */}
      {incidents.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-error font-bold text-sm uppercase tracking-widest">
            <AlertCircle size={16} />
            <span>{incidents.length} Active Issues Requiring Attention</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {incidents.map(site => (
              <Link to={`/site/${site.id}`} key={site.id} className="glass-panel p-5 flex items-center justify-between hover:border-error/30 transition-all group">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    site.current_status === 'DOWN' ? "bg-error animate-pulse" : "bg-warning"
                  )} />
                  <div>
                    <h3 className="font-bold text-sm text-text-primary group-hover:text-accent transition-colors">{site.name || site.url}</h3>
                    <p className="text-xs text-text-muted">
                      {site.current_status === 'DOWN' ? 'Site is unreachable' : 
                       site.ssl_days_remaining !== null && site.ssl_days_remaining < 14 ? `SSL expiring in ${site.ssl_days_remaining}d` :
                       site.dns_hijack_suspected ? 'DNS Hijack Suspected!' :
                       site.dns_ns_changed ? 'Nameservers Changed' :
                       'DNS configuration issue detected'}
                    </p>
                  </div>
                </div>
                <ChevronRight size={16} className="text-text-muted group-hover:translate-x-1 transition-transform" />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Fleet Table Section */}
      <section className="glass-panel overflow-hidden">
        <div className="p-8 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h2 className="text-2xl font-extrabold tracking-tight">Fleet Status</h2>
            <p className="text-text-muted text-sm">Monitored properties and real-time performance</p>
          </div>
          <div className="relative w-full md:w-80">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" size={16} />
            <input 
              type="text" 
              placeholder="Search domains..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-border rounded-full pl-12 pr-4 py-2.5 text-sm focus:border-accent outline-none transition-colors"
            />
          </div>
        </div>
        
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto custom-scrollbar">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] font-black text-text-muted uppercase tracking-widest border-b border-border">
                <th className="px-8 py-4">Site</th>
                <th className="px-8 py-4">Status</th>
                <th className="px-8 py-4">Response</th>
                <th className="px-8 py-4">SSL</th>
                <th className="px-8 py-4">SEO</th>
                <th className="px-8 py-4">Last Checked</th>
                <th className="px-8 py-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {filteredSites.map((site) => (
                <tr key={site.id} className="group hover:bg-white/[0.02] transition-colors">
                  <td className="px-8 py-6">
                    <div>
                      <Link to={`/site/${site.id}`} className="font-bold text-text-primary hover:text-accent transition-colors">
                        {site.name || site.url.replace(/^https?:\/\//, '')}
                      </Link>
                      <p className="text-xs text-text-muted font-mono mt-1">{site.url}</p>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <StatusBadge status={site.current_status.toLowerCase() as any} />
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-2 font-mono text-sm">
                      <Zap size={12} className="text-accent" />
                      {site.last_response_time ? `${Math.round(site.last_response_time * 1000)}ms` : '—'}
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex flex-col gap-1">
                      <span className={cn(
                        "text-[10px] font-bold px-2 py-0.5 rounded-full w-fit",
                        site.ssl_state === 'VALID' ? "bg-success/10 text-success" : "bg-error/10 text-error"
                      )}>
                        {site.ssl_state}
                      </span>
                      {site.ssl_issuer && (
                        <span className="text-[10px] text-text-muted truncate max-w-[100px]" title={site.ssl_issuer}>
                          {site.ssl_issuer}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 w-12 bg-white/5 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            "h-full rounded-full",
                            site.seo_score >= 80 ? "bg-success" : site.seo_score >= 60 ? "bg-warning" : "bg-error"
                          )} 
                          style={{ width: `${site.seo_score}%` }} 
                        />
                      </div>
                      <span className="text-xs font-bold">{site.seo_score}</span>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <p className="text-xs text-text-muted">
                      {site.last_uptime_check_at ? formatDistanceToNow(new Date(site.last_uptime_check_at), { addSuffix: true }) : '—'}
                    </p>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <Link 
                      to={`/site/${site.id}`}
                      className="p-2 text-text-muted hover:text-accent transition-colors"
                    >
                      <ChevronRight size={20} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredSites.length === 0 && (
            <div className="p-20 text-center text-text-muted">
              <Globe2 size={48} className="mx-auto mb-4 opacity-20" />
              <p>No sites found matching your search.</p>
            </div>
          )}
        </div>
      </section>
      
      {/* Activity Feed Section */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-10">
        <div className="lg:col-span-2 glass-panel p-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold">Recent Activity</h2>
              <p className="text-text-muted text-xs">System events and performance anomalies</p>
            </div>
            <Activity size={20} className="text-text-muted opacity-50" />
          </div>
          <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
            {activities.length > 0 ? (
              activities.map((activity) => (
                <div key={activity.id} className="flex items-start gap-4 p-4 bg-white/5 rounded-xl border border-border/50 group hover:border-error/30 transition-all">
                  <div className="mt-1 w-2 h-2 rounded-full bg-error animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                      <h4 className="font-bold text-sm truncate">{activity.site_name}</h4>
                      <span className="text-[10px] text-text-muted font-mono whitespace-nowrap ml-2">
                        {formatDistanceToNow(new Date(activity.checked_at), { addSuffix: true })}
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary truncate">{activity.error_message}</p>
                  </div>
                  <Link 
                    to={`/site/${activity.site_id}`}
                    className="p-1.5 text-text-muted hover:text-accent transition-colors self-center opacity-0 group-hover:opacity-100"
                  >
                    <ChevronRight size={16} />
                  </Link>
                </div>
              ))
            ) : (
              <div className="py-10 text-center text-text-muted">
                <CheckCircle2 size={32} className="mx-auto mb-3 opacity-20 text-success" />
                <p className="text-sm font-medium">All systems stable. No recent anomalies detected.</p>
              </div>
            )}
          </div>
        </div>
        
        <div className="glass-panel p-8">
          <h3 className="font-bold text-sm mb-6 text-text-muted uppercase tracking-widest">Fleet Composition</h3>
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Healthy Sites</span>
              <span className="text-sm font-bold text-success">{metrics?.sites_up}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Critical Failures</span>
              <span className="text-sm font-bold text-error">{metrics?.sites_down}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Encrypted Fleet</span>
              <span className="text-sm font-bold text-success">{metrics?.sites_with_ssl} / {metrics?.monitored_sites}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">DNS Checked</span>
              <span className="text-sm font-bold text-accent">{metrics?.dns_checked_count}</span>
            </div>
            <div className="pt-4 border-t border-border">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-text-muted">OVERALL HEALTH</span>
                <span className="text-xs font-bold text-accent">{metrics?.health_score}%</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-accent rounded-full transition-all duration-1000" 
                  style={{ width: `${metrics?.health_score}%` }} 
                />
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
};
