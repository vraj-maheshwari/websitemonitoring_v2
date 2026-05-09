import React, { useEffect, useState } from 'react';
import { ShieldCheck, Lock, AlertTriangle, CheckCircle2, RefreshCw, Eye } from 'lucide-react';
import { sitesApi, dashboardApi } from '../lib/api';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';
import { Link } from 'react-router-dom';

export const SecurityDashboard = () => {
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

  const securedSites = sites.filter(s => s.ssl_state === 'VALID').length;
  const criticalIssues = sites.filter(s => s.ssl_state === 'EXPIRED' || s.dns_hijack_suspected).length;

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 md:p-10 max-w-[1400px] mx-auto w-full space-y-10"
    >
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold tracking-tight mb-2">Security Posture</h1>
        <p className="text-text-muted">Fleet-wide encryption, DNS integrity, and header hardening audit.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="glass-panel p-8 flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-success/10 flex items-center justify-center text-success">
            <ShieldCheck size={32} />
          </div>
          <div>
            <p className="text-xs font-bold text-text-muted uppercase tracking-widest mb-1">Encrypted Fleet</p>
            <p className="text-3xl font-black text-text-primary">{securedSites} / {sites.length}</p>
          </div>
        </div>

        <div className="glass-panel p-8 flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-warning/10 flex items-center justify-center text-warning">
            <Lock size={32} />
          </div>
          <div>
            <p className="text-xs font-bold text-text-muted uppercase tracking-widest mb-1">Avg SSL Life</p>
            <p className="text-3xl font-black text-text-primary">{analytics?.avg_ssl_life || 0} Days</p>
          </div>
        </div>

        <div className="glass-panel p-8 flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-error/10 flex items-center justify-center text-error">
            <AlertTriangle size={32} />
          </div>
          <div>
            <p className="text-xs font-bold text-text-muted uppercase tracking-widest mb-1">Critical Alerts</p>
            <p className="text-3xl font-black text-text-primary">{criticalIssues}</p>
          </div>
        </div>
      </div>

      <section className="glass-panel overflow-hidden">
        <div className="p-8 border-b border-border">
          <h2 className="text-xl font-bold">Domain Security Status</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] font-black text-text-muted uppercase tracking-widest border-b border-border">
                <th className="px-8 py-4">Target Site</th>
                <th className="px-8 py-4">SSL Certificate</th>
                <th className="px-8 py-4">DNS Integrity</th>
                <th className="px-8 py-4">Hardening</th>
                <th className="px-8 py-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {sites.map(site => (
                <tr key={site.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-8 py-6">
                    <span className="font-bold text-sm">{site.url}</span>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-2 h-2 rounded-full", site.ssl_state === 'VALID' ? "bg-success" : "bg-error")} />
                      <span className="text-xs">{site.ssl_issuer || 'Unknown Issuer'}</span>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <span className={cn(
                      "text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-tighter",
                      site.dns_resolved ? "bg-success/10 text-success" : "bg-error/10 text-error"
                    )}>
                      {site.dns_resolved ? 'Verified' : 'Unresolved'}
                    </span>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map(i => {
                        // Use security_headers object length or a mock count if not available
                        const headerCount = Object.keys(site.security_headers || {}).length || 0;
                        const filled = i <= Math.min(5, headerCount);
                        return <div key={i} className={cn("w-3 h-1 rounded-full", filled ? "bg-accent" : "bg-white/5")} />;
                      })}
                    </div>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <Link to={`/site/${site.id}`} className="text-text-muted hover:text-accent p-2">
                      <Eye size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </motion.div>
  );
};
