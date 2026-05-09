import { useEffect, useState } from 'react';
import { 
  ChevronLeft, Activity, ShieldCheck, RefreshCw, 
  Lock, Zap, Link as LinkIcon, Database, Cpu, Search, AlertTriangle, 
  CheckCircle2, Layout, Code2, Globe2, FileText,
  Trash2, Download, ExternalLink
} from 'lucide-react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { MetricCard } from './MetricCard';
import { StatusBadge } from './StatusBadge';
import { EditSiteModal } from './EditSiteModal';
import { cn } from '../lib/utils';
import { sitesApi } from '../lib/api';
import type { Site, SEOLog } from '../types';

export const SiteDetail = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [site, setSite] = useState<Site | null>(null);
  const [seoLogs, setSeoLogs] = useState<SEOLog[]>([]);
  const [uptimeHistory, setUptimeHistory] = useState<any[]>([]);
  const [brokenLinksData, setBrokenLinksData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'seo' | 'performance' | 'security' | 'tech' | 'links'>('overview');
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [checkingType, setCheckingType] = useState<string | null>(null);

  const fetchSiteData = async () => {
    if (!id) return;
    try {
      const siteId = parseInt(id);
      const [siteData, logsData, historyData, brokenData] = await Promise.all([
        sitesApi.get(siteId),
        sitesApi.getSEOLogs(siteId),
        sitesApi.getUptimeHistory(siteId),
        sitesApi.getBrokenLinks(siteId).catch(() => null)
      ]);
      setSite(siteData);
      setSeoLogs(logsData);
      setUptimeHistory(historyData.map((log: any) => ({
        time: new Date(log.checked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        value: Math.round(log.response_time * 1000)
      })).reverse());
      setBrokenLinksData(brokenData);
    } catch (error) {
      console.error("Failed to fetch site detail:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSiteData();
    const interval = setInterval(fetchSiteData, 30000);
    return () => clearInterval(interval);
  }, [id]);

  const runCheck = async (type: string) => {
    if (!site) return;
    setCheckingType(type);
    try {
      await sitesApi.runCheck(site.id, type as any);
      // Wait a bit for the worker to start then refresh
      setTimeout(fetchSiteData, 2000);
    } catch (e) {
      console.error("Check failed", e);
    } finally {
      setTimeout(() => setCheckingType(null), 3000);
    }
  };

  const updateSite = async (data: any) => {
    if (!site) return;
    try {
      await sitesApi.update(site.id, data);
      setShowEditModal(false);
      fetchSiteData();
    } catch (e) {
      console.error("Update failed", e);
    }
  };

  const handleDeleteSite = async () => {
    if (!site || !window.confirm("Are you sure you want to delete this site? This action cannot be undone.")) return;
    try {
      await sitesApi.delete(site.id);
      navigate('/');
    } catch (e) {
      console.error("Delete failed", e);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  if (!site) {
    return (
      <div className="p-8 text-center text-text-muted">
        <h1 className="text-xl font-bold mb-4">Site not found</h1>
        <Link to="/" className="text-accent underline">Back to Overview</Link>
      </div>
    );
  }

  const latestReport = seoLogs[0];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 md:p-10 max-w-[1400px] mx-auto w-full"
    >
      {/* Header Section */}
      <div className="mb-10">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <Link to="/" className="flex items-center gap-2 text-sm text-text-muted hover:text-text-primary transition-colors mb-4 group">
              <ChevronLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
              Back to Overview
            </Link>
            <div className="flex items-center gap-4">
              <h1 className="text-4xl font-extrabold tracking-tight text-text-primary">{site.name || site.url}</h1>
              <StatusBadge status={site.current_status.toLowerCase() as any} />
              {site.app_status === 'checking' && (
                <span className="flex items-center gap-2 px-3 py-1 bg-accent/10 text-accent rounded-full text-xs font-bold animate-pulse">
                  <RefreshCw size={12} className="animate-spin" />
                  SCANNING
                </span>
              )}
            </div>
            <p className="text-text-secondary font-mono text-sm">{site.url}</p>
          </div>
          
          <div className="flex flex-wrap gap-3">
            <div className="flex bg-white/5 p-1 rounded-full border border-border">
              {['uptime', 'ssl', 'seo', 'security', 'dns'].map((type) => (
                <button
                  key={type}
                  onClick={() => runCheck(type)}
                  className="px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest hover:bg-white/5 transition-colors"
                >
                  {type}
                </button>
              ))}
            </div>

            <div className="relative">
              <button 
                onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                className="btn btn-secondary px-6 rounded-full text-xs flex items-center gap-2"
              >
                <Download size={14} />
                Download
              </button>
              <AnimatePresence>
                {showDownloadMenu && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute right-0 mt-2 w-40 bg-background-card border border-border rounded-2xl shadow-2xl z-50 overflow-hidden"
                  >
                    {['JSON', 'CSV', 'PDF'].map((fmt) => (
                      <a 
                        key={fmt}
                        href={`/export/site/${site.id}?format=${fmt.toLowerCase()}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 px-4 py-3 text-xs font-bold hover:bg-white/5 transition-colors border-b border-border last:border-0"
                      >
                        <FileText size={14} className="text-text-muted" />
                        {fmt} Report
                      </a>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button 
              onClick={() => setShowEditModal(true)}
              className="btn btn-secondary px-6 rounded-full text-xs"
            >
              Config
            </button>
            <button 
              onClick={handleDeleteSite}
              className="btn btn-danger-outline p-2 px-3 rounded-full text-xs flex items-center gap-2"
            >
              <Trash2 size={14} />
            </button>
            <button 
              onClick={() => runCheck('all')}
              disabled={site.app_status === 'checking' || checkingType === 'all'}
              className="btn btn-primary px-6 rounded-full text-xs shadow-lg shadow-accent/20 flex items-center gap-2"
            >
              {(site.app_status === 'checking' || checkingType === 'all') ? <RefreshCw size={14} className="animate-spin" /> : null}
              Full Audit
            </button>
          </div>
        </div>
      </div>

      {/* Alert Banners */}
      <AnimatePresence>
        {!site.last_seo_fetch_valid && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="mb-4 overflow-hidden"
          >
            <div className="bg-warning/10 border border-warning/20 rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="flex items-start gap-4">
                <div className="p-2 bg-warning/20 rounded-lg text-warning mt-1"><AlertTriangle size={20} /></div>
                <div>
                  <h3 className="font-bold text-warning">SEO intelligence may be inaccurate</h3>
                  <p className="text-sm text-text-secondary">Last scan fetched a placeholder or empty page — possibly due to bot protection or server cold-start.</p>
                </div>
              </div>
              <button 
                onClick={() => runCheck('seo')} 
                disabled={checkingType === 'seo'}
                className="btn btn-secondary text-xs px-6 rounded-full whitespace-nowrap flex items-center gap-2"
              >
                {checkingType === 'seo' ? <RefreshCw size={14} className="animate-spin" /> : '↻'}
                Re-run SEO Audit
              </button>
            </div>
          </motion.div>
        )}

        {(site.dns_hijack_suspected || site.dns_ns_changed) && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="mb-4 overflow-hidden"
          >
            <div className="bg-error/10 border border-error/20 rounded-2xl p-6 flex items-start gap-4">
              <div className="p-2 bg-error/20 rounded-lg text-error mt-1"><AlertTriangle size={20} /></div>
              <div>
                <h3 className="font-bold text-error">
                  {site.dns_hijack_suspected ? 'CRITICAL: DNS Hijack Suspected' : 'Warning: Unauthorized Nameserver Change'}
                </h3>
                <p className="text-sm text-text-secondary">
                  {site.dns_hijack_suspected 
                    ? 'Your domain resolved to unexpected IP addresses. This could indicate a DNS takeover or hijacking.'
                    : 'We detected a change in your domain nameservers. Please verify this change is authorized.'}
                </p>
                <div className="mt-4 flex gap-4">
                  <div className="bg-black/20 rounded-lg p-3">
                    <p className="text-[10px] font-bold text-text-muted uppercase mb-1">Current IPs</p>
                    <p className="text-xs font-mono">{site.dns_last_ips?.join(', ') || 'None'}</p>
                  </div>
                  <div className="bg-black/20 rounded-lg p-3">
                    <p className="text-[10px] font-bold text-text-muted uppercase mb-1">Nameservers</p>
                    <p className="text-xs font-mono">{site.dns_last_ns?.join(', ') || 'None'}</p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {site.dns_status === 'failed' && !site.dns_hijack_suspected && !site.dns_ns_changed && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="mb-4 overflow-hidden"
          >
            <div className="bg-error/10 border border-error/20 rounded-2xl p-6 flex items-start gap-4">
              <div className="p-2 bg-error/20 rounded-lg text-error mt-1"><Globe2 size={20} /></div>
              <div>
                <h3 className="font-bold text-error">DNS Resolution Failure</h3>
                <p className="text-sm text-text-secondary">
                  We were unable to resolve your domain. This could be due to invalid DNS records or nameserver downtime.
                </p>
                {site.dns_last_error && (
                  <p className="mt-2 text-xs font-mono bg-black/20 p-2 rounded-lg text-error">
                    Error: {site.dns_last_error}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Primary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <MetricCard 
          label="Uptime Status" 
          value={site.current_status} 
          icon={Activity}
          trend={site.current_status === 'UP' ? 'up' : 'down'}
          trendValue={site.last_status_code?.toString()}
        />
        <MetricCard 
          label="Response Time" 
          value={site.last_response_time ? `${Math.round(site.last_response_time * 1000)}ms` : "—"} 
          icon={Zap}
          trend={site.last_response_time && site.last_response_time < 0.5 ? 'up' : undefined}
          trendValue="Fast"
        />
        <MetricCard 
          label="SSL Expiry" 
          value={site.ssl_days_remaining !== null ? `${site.ssl_days_remaining} Days` : "—"} 
          icon={Lock}
          trend={site.ssl_state === 'VALID' ? 'up' : 'down'}
          trendValue={site.ssl_state}
        />
        <MetricCard 
          label="SEO Score" 
          value={site.seo_score > 0 ? `${site.seo_score}/100` : "—"} 
          icon={Search}
          trend={site.seo_score >= 80 ? 'up' : undefined}
          trendValue={site.seo_state}
        />
      </div>

      {/* Tabs Navigation */}
      <div className="relative z-30 flex border-b border-border mb-8 overflow-x-auto no-scrollbar bg-background-primary/50 backdrop-blur-sm sticky top-16">
        {[
          { id: 'overview', label: 'Intelligence Overview', icon: Layout },
          { id: 'seo', label: 'SEO Audit', icon: Search },
          { id: 'performance', label: 'Performance (CWV)', icon: Zap },
          { id: 'security', label: 'Security Grade', icon: ShieldCheck },
          { id: 'tech', label: 'Tech Stack', icon: Database },
          { id: 'links', label: 'Broken Links', icon: LinkIcon },
        ].map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            onClick={() => {
              console.log(`Switching to tab: ${tab.id}`);
              setActiveTab(tab.id as any);
            }}
            className={cn(
              "flex items-center gap-2 px-6 py-4 text-sm font-semibold transition-all border-b-2 whitespace-nowrap relative",
              activeTab === tab.id 
                ? "border-accent text-accent bg-accent/10" 
                : "border-transparent text-text-secondary hover:text-text-primary hover:bg-white/5"
            )}
          >
            <tab.icon size={16} className={cn(activeTab === tab.id ? "text-accent" : "text-text-muted")} />
            {tab.label}
            {activeTab === tab.id && (
              <motion.div 
                layoutId="activeTab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent"
              />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[500px]">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-8">
              {/* Response Time Chart */}
              <div className="glass-panel p-8">
                <div className="flex justify-between items-center mb-8">
                  <h2 className="font-bold text-xl">Latency Analysis</h2>
                  <div className="flex items-center gap-2 text-text-muted text-xs font-mono">
                    <div className="w-2 h-2 rounded-full bg-accent" />
                    RESPONSE TIME (MS)
                  </div>
                </div>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={uptimeHistory.length > 0 ? uptimeHistory : [
                      { time: '00:00', value: 0 },
                      { time: '12:00', value: 0 },
                      { time: '23:59', value: 0 },
                    ]}>
                      <defs>
                        <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748B', fontSize: 10}} />
                      <Tooltip 
                        contentStyle={{backgroundColor: '#0F172A', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'}}
                        itemStyle={{color: '#3B82F6', fontWeight: 'bold'}}
                      />
                      <Area type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={3} fill="url(#latencyGradient)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* SEO Score Breakdown Tiles */}
              {latestReport && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {[
                    { label: 'On-Page', value: latestReport.score_breakdown?.on_page },
                    { label: 'Technical', value: latestReport.score_breakdown?.technical },
                    { label: 'Content', value: latestReport.score_breakdown?.content },
                    { label: 'Performance', value: latestReport.score_breakdown?.performance },
                  ].map((tile, i) => (
                    <div key={i} className="glass-panel p-6 text-center">
                      <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2">{tile.label}</p>
                      <p className={cn(
                        "text-2xl font-bold",
                        (tile.value || 0) >= 80 ? "text-success" : (tile.value || 0) >= 60 ? "text-warning" : "text-error"
                      )}>
                        {tile.value || 0}/100
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-6">
              {/* Sidebar Info */}
              <div className="glass-panel p-6">
                <h3 className="font-bold text-sm mb-6 text-text-muted uppercase tracking-widest">Network Intel</h3>
                <div className="space-y-6">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-white/5 rounded-lg text-text-secondary"><Globe2 size={16} /></div>
                      <span className="text-sm font-medium">DNS Status</span>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className={cn(
                        "text-xs font-bold px-2 py-1 rounded-full",
                        site.dns_status === 'done' ? "bg-success/10 text-success" : "bg-warning/10 text-warning"
                      )}>
                        {site.dns_status.toUpperCase()}
                      </span>
                      {site.dns_last_error && (
                        <span className="text-[10px] text-error font-medium max-w-[150px] truncate" title={site.dns_last_error}>
                          {site.dns_last_error}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-white/5 rounded-lg text-text-secondary"><Cpu size={16} /></div>
                      <span className="text-sm font-medium">Resolution Time</span>
                    </div>
                    <span className="text-sm font-mono font-bold">{site.dns_resolution_time_ms ? `${Math.round(site.dns_resolution_time_ms)}ms` : '—'}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-white/5 rounded-lg text-text-secondary"><Lock size={16} /></div>
                      <span className="text-sm font-medium">SSL Issuer</span>
                    </div>
                    <span className="text-xs font-bold text-text-muted truncate max-w-[120px]" title={site.ssl_issuer || "Unknown"}>
                      {site.ssl_issuer || "Unknown"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-white/5 rounded-lg text-text-secondary"><Database size={16} /></div>
                      <span className="text-sm font-medium">NS Changed</span>
                    </div>
                    <span className={cn("text-xs font-bold", site.dns_ns_changed ? "text-warning" : "text-text-muted")}>
                      {site.dns_ns_changed ? "YES" : "NO"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="glass-panel p-6">
                <h3 className="font-bold text-sm mb-6 text-text-muted uppercase tracking-widest">Quick Actions</h3>
                <div className="grid grid-cols-1 gap-3">
                  <button onClick={() => runCheck('uptime')} className="btn btn-secondary w-full justify-start text-xs py-3 rounded-xl">
                    <Activity size={14} /> Re-check Uptime
                  </button>
                  <button onClick={() => runCheck('ssl')} className="btn btn-secondary w-full justify-start text-xs py-3 rounded-xl">
                    <Lock size={14} /> Verify SSL Cert
                  </button>
                  <button onClick={() => runCheck('dns')} className="btn btn-secondary w-full justify-start text-xs py-3 rounded-xl">
                    <Globe2 size={14} /> Check DNS Propagation
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'seo' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            {latestReport ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="glass-panel p-8">
                    <h3 className="font-bold text-lg mb-6 flex items-center gap-2">
                      <FileText size={20} className="text-accent" />
                      Content Audit
                    </h3>
                    <div className="space-y-6">
                      <div className="pb-4 border-b border-border">
                        <p className="text-xs font-bold text-text-muted uppercase mb-1">Page Title</p>
                        <p className="text-lg font-medium">{latestReport.title}</p>
                        <span className="text-[10px] text-text-muted">{latestReport.title_length} characters</span>
                      </div>
                      <div className="pb-4 border-b border-border">
                        <p className="text-xs font-bold text-text-muted uppercase mb-1">Meta Description</p>
                        <p className="text-sm text-text-secondary italic">"{latestReport.meta_description}"</p>
                        <span className="text-[10px] text-text-muted">{latestReport.meta_length} characters</span>
                      </div>
                      <div className="grid grid-cols-2 gap-y-4 gap-x-8">
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">H1 Headers</span>
                          <span className={cn("text-sm font-bold", latestReport.h1_count === 1 ? "text-success" : "text-error")}>
                            {latestReport.h1_count}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">Word Count</span>
                          <span className="text-sm font-bold">{latestReport.word_count}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">H2 Headers</span>
                          <span className="text-sm font-bold">{latestReport.h2_count}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">Missing Alt Tags</span>
                          <span className={cn("text-sm font-bold", latestReport.missing_alt_count === 0 ? "text-success" : "text-warning")}>
                            {latestReport.missing_alt_count}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">H3 Headers</span>
                          <span className="text-sm font-bold">{latestReport.h3_count}</span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-white/5">
                          <span className="text-xs text-text-secondary font-medium">Total Images</span>
                          <span className="text-sm font-bold">{latestReport.image_count}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="glass-panel p-8">
                    <h3 className="font-bold text-lg mb-6 flex items-center gap-2">
                      <ShieldCheck size={20} className="text-success" />
                      Technical Signals
                    </h3>
                    <div className="space-y-4">
                      <div className="flex justify-between items-center p-3 bg-white/5 rounded-xl border border-border/50">
                        <span className="text-xs font-medium">Canonical Tag</span>
                        <span className={cn("text-[10px] font-bold px-2 py-1 rounded-full", latestReport.canonical ? "bg-success/10 text-success" : "bg-error/10 text-error")}>
                          {latestReport.canonical ? "PRESENT" : "MISSING"}
                        </span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-white/5 rounded-xl border border-border/50">
                        <span className="text-xs font-medium">Robots.txt</span>
                        <span className={cn("text-[10px] font-bold px-2 py-1 rounded-full", latestReport.has_robots ? "bg-success/10 text-success" : "bg-warning/10 text-warning")}>
                          {latestReport.has_robots ? "DETECTED" : "MISSING"}
                        </span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-white/5 rounded-xl border border-border/50">
                        <span className="text-xs font-medium">Sitemap.xml</span>
                        <span className={cn("text-[10px] font-bold px-2 py-1 rounded-full", latestReport.has_sitemap ? "bg-success/10 text-success" : "bg-warning/10 text-warning")}>
                          {latestReport.has_sitemap ? "DETECTED" : "MISSING"}
                        </span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-white/5 rounded-xl border border-border/50">
                        <span className="text-xs font-medium">Language Setting</span>
                        <span className="text-xs font-mono font-bold text-accent">{latestReport.html_lang || "Not Set"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="glass-panel p-8">
                    <h3 className="font-bold text-lg mb-6 flex items-center gap-2">
                      <AlertTriangle size={20} className="text-warning" />
                      Top Recommendations
                    </h3>
                    <div className="space-y-4">
                      {latestReport.recommendations.slice(0, 5).map((rec: any, i) => (
                        <div key={i} className="flex items-start gap-3 p-4 bg-white/5 rounded-xl border border-border/50">
                          <CheckCircle2 size={16} className="text-accent mt-0.5 shrink-0" />
                          <p className="text-sm text-text-secondary">
                            {typeof rec === 'string' ? rec : (rec.detail || rec.action || JSON.stringify(rec))}
                          </p>
                        </div>
                      ))}
                      {latestReport.recommendations.length === 0 && (
                        <p className="text-text-muted text-center py-10">No critical issues detected!</p>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="glass-panel p-8">
                  <h3 className="font-bold text-lg mb-6 flex items-center gap-2">
                    <LinkIcon size={20} className="text-accent" />
                    Link Analysis Waterfall
                  </h3>
                  <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-1">Total in HTML</p>
                      <p className="text-2xl font-black">{latestReport.broken_links?.total_found || (latestReport.internal_link_count + latestReport.external_link_count)}</p>
                    </div>
                    <div className="p-4 bg-accent/5 rounded-2xl border border-accent/20">
                      <p className="text-[10px] font-black text-accent uppercase tracking-widest mb-1">Unique (Processed)</p>
                      <p className="text-2xl font-black text-accent">{latestReport.links_checked}</p>
                    </div>
                    <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-1">Internal (Unique)</p>
                      <p className="text-2xl font-black">{latestReport.broken_links?.internal_count ?? latestReport.internal_link_count}</p>
                    </div>
                    <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-1">External (Unique)</p>
                      <p className="text-2xl font-black">{latestReport.broken_links?.external_count ?? latestReport.external_link_count}</p>
                    </div>
                    <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-[10px] font-black text-error uppercase tracking-widest mb-1">Broken</p>
                      <p className={cn("text-2xl font-black", latestReport.broken_link_count > 0 ? "text-error" : "text-success")}>
                        {latestReport.broken_link_count}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 p-3 bg-white/5 rounded-xl border border-white/5 flex items-center justify-center gap-6 text-[10px] font-bold text-text-muted uppercase">
                    <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-accent" /> Internal + External = Unique</div>
                    <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-success" /> Working + Broken = Unique</div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-20 glass-panel">
                <Search size={48} className="mx-auto text-text-muted mb-4 opacity-20" />
                <p className="text-text-muted">No SEO Audit data available. Run a Full Audit to see intelligence breakdown.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'performance' && (
          <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
            {latestReport?.lighthouse ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {Object.entries(latestReport.lighthouse.metrics).map(([key, data]) => (
                  <div key={key} className="glass-panel p-8 flex flex-col items-center text-center">
                    <div className={cn(
                      "w-20 h-20 rounded-full border-4 flex items-center justify-center text-xl font-bold mb-4",
                      data.rating === 'good' ? "border-success/50 text-success bg-success/5" : 
                      data.rating === 'needs_improvement' ? "border-warning/50 text-warning bg-warning/5" : "border-error/50 text-error bg-error/5"
                    )}>
                      {((data as any).value_ms !== undefined && (data as any).value_ms !== null) 
                        ? ((data as any).value_ms > 1000 ? `${((data as any).value_ms / 1000).toFixed(1)}s` : `${Math.round((data as any).value_ms)}ms`) 
                        : ((data as any).value !== undefined && (data as any).value !== null ? (data as any).value : '—')}
                    </div>
                    <p className="text-xs font-bold text-text-muted uppercase tracking-widest">{key.toUpperCase()}</p>
                    <p className="text-[10px] text-text-muted mt-2 capitalize">
                      {data.rating ? data.rating.replace('_', ' ') : 'N/A'}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-20 glass-panel">
                <Zap size={48} className="mx-auto text-text-muted mb-4 opacity-20" />
                <p className="text-text-muted">Real Core Web Vitals require a Headless Browser audit. Start a scan to collect lab data.</p>
              </div>
            )}
            
            <div className="glass-panel p-8">
              <h3 className="font-bold text-lg mb-6">Server Performance</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-accent/10 text-accent rounded-2xl"><Cpu size={24} /></div>
                  <div>
                    <p className="text-xs font-bold text-text-muted uppercase">TTFB (Network)</p>
                    <p className="text-2xl font-bold">{site.last_ttfb ? `${Math.round(site.last_ttfb * 1000)}ms` : '—'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-success/10 text-success rounded-2xl"><Database size={24} /></div>
                  <div>
                    <p className="text-xs font-bold text-text-muted uppercase">Page Weight</p>
                    <p className="text-2xl font-bold">{latestReport?.page_size_kb ? `${Math.round(latestReport.page_size_kb)} KB` : '—'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-warning/10 text-warning rounded-2xl"><Code2 size={24} /></div>
                  <div>
                    <p className="text-xs font-bold text-text-muted uppercase">Blocking Assets</p>
                    <p className="text-2xl font-bold">{latestReport ? (latestReport.js_blocking_count + latestReport.css_blocking_count) : '—'}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="glass-panel p-10 flex flex-col items-center justify-center text-center">
                <p className="text-xs font-bold text-text-muted uppercase tracking-widest mb-4">Security Grade</p>
                <div className={cn(
                  "w-32 h-32 rounded-full flex items-center justify-center text-6xl font-black mb-6 border-8 shadow-2xl shadow-accent/20",
                  latestReport?.security_grade === 'A' ? "border-success text-success bg-success/5" :
                  latestReport?.security_grade === 'B' ? "border-accent text-accent bg-accent/5" :
                  latestReport?.security_grade === 'C' ? "border-warning text-warning bg-warning/5" : "border-error text-error bg-error/5"
                )}>
                  {latestReport?.security_grade || '—'}
                </div>
                <p className="text-sm text-text-secondary font-medium">
                  {latestReport?.security_score || 0}% Hardened
                </p>
              </div>

              <div className="md:col-span-2 glass-panel p-8">
                <h3 className="font-bold text-lg mb-6">HTTP Security Headers</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {latestReport && Object.entries(latestReport.security_headers).map(([header, status]) => (
                    <div key={header} className="flex justify-between items-center p-3 bg-white/5 rounded-xl border border-border/50">
                      <span className="text-xs font-mono text-text-secondary">{header}</span>
                      {status ? (
                        <CheckCircle2 size={16} className="text-success" />
                      ) : (
                        <AlertTriangle size={16} className="text-error" />
                      )}
                    </div>
                  ))}
                  {!latestReport && <p className="text-text-muted col-span-2 py-20 text-center">No security headers analyzed yet.</p>}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tech' && (
          <div className="animate-in fade-in duration-500">
            <div className="glass-panel p-8">
              <h3 className="font-bold text-xl mb-8 flex items-center gap-2">
                <Code2 size={24} className="text-accent" />
                Technology Fingerprint
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {latestReport && Object.entries(latestReport.tech_stack).map(([category, techs]) => (
                  <div key={category} className="space-y-3">
                    <p className="text-[10px] font-black text-text-muted uppercase tracking-tighter">{category.replace(/_/g, ' ')}</p>
                    <div className="flex flex-wrap gap-2">
                      {techs.map((tech, i) => (
                        <span key={i} className="px-3 py-1 bg-accent/5 border border-accent/20 text-accent text-xs font-bold rounded-lg shadow-sm">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {!latestReport && <p className="text-text-muted col-span-4 py-20 text-center">Technology profiling requires a full audit scan.</p>}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'links' && (
          <div className="animate-in fade-in duration-500 space-y-8">
            <div className="glass-panel p-8">
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h3 className="text-xl font-bold">Broken Link Audit</h3>
                  <p className="text-text-muted text-sm">Detailed analysis of unreachable internal and external links</p>
                </div>
                <div className={cn(
                  "px-4 py-2 rounded-2xl font-black text-sm",
                  (brokenLinksData?.broken_link_count || 0) === 0 ? "bg-success/10 text-success" : "bg-error/10 text-error"
                )}>
                  {brokenLinksData?.broken_link_count || 0} ISSUES
                </div>
              </div>

              {brokenLinksData?.broken_links?.broken?.length > 0 ? (
                <div className="space-y-4">
                  {brokenLinksData.broken_links.broken.map((link: any, i: number) => (
                    <div key={i} className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 bg-white/5 rounded-2xl border border-border/50 group hover:border-error/30 transition-all">
                      <div className="flex items-start gap-4 min-w-0">
                        <div className={cn(
                          "w-12 h-12 rounded-xl flex items-center justify-center font-black text-sm shrink-0",
                          link.status_code >= 500 ? "bg-error/20 text-error" : "bg-warning/20 text-warning"
                        )}>
                          {link.status_code || 'ERR'}
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-sm truncate text-text-primary group-hover:text-accent transition-colors">{link.url}</p>
                          <p className="text-xs text-text-muted mt-1 italic">"{link.anchor_text || 'No anchor text'}"</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className={cn(
                          "text-[10px] font-black px-2 py-1 rounded-full uppercase tracking-tighter",
                          link.link_type === 'internal' ? "bg-accent/10 text-accent" : "bg-white/10 text-text-muted"
                        )}>
                          {link.link_type}
                        </span>
                        <a href={link.url} target="_blank" rel="noopener noreferrer" className="p-2 text-text-muted hover:text-text-primary transition-colors">
                          <ExternalLink size={16} />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-20">
                  <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckCircle2 size={32} className="text-success" />
                  </div>
                  <h4 className="font-bold text-lg">No broken links found</h4>
                  <p className="text-text-muted text-sm max-w-xs mx-auto mt-2">
                    Our crawler checked {brokenLinksData?.links_checked || 0} links and they all returned healthy status codes.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Edit Site Modal */}
      <EditSiteModal 
        site={site} 
        isOpen={showEditModal} 
        onClose={() => setShowEditModal(false)} 
        onSave={updateSite}
      />
    </motion.div>
  );
};
