import { useEffect, useState } from 'react';
import { AlertCircle, Clock, ExternalLink, RefreshCw } from 'lucide-react';
import { dashboardApi } from '../lib/api';
import { Link } from 'react-router-dom';
import { cn } from '../lib/utils';
import { motion } from 'framer-motion';

export const IncidentsLog = () => {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchIncidents = async () => {
    try {
      const data = await dashboardApi.getGlobalIncidents();
      setIncidents(data);
    } catch (error) {
      console.error("Failed to fetch incidents:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 md:p-10 max-w-[1400px] mx-auto w-full"
    >
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold tracking-tight mb-2">Incidents Log</h1>
        <p className="text-text-muted">Real-time status of critical issues across your fleet.</p>
      </div>

      <div className="space-y-4">
        {incidents.length > 0 ? (
          incidents.map((incident) => (
            <div key={incident.id} className="glass-panel p-6 flex flex-col md:flex-row items-center justify-between gap-6 hover:border-error/30 transition-all group">
              <div className="flex items-center gap-5">
                <div className={cn(
                  "p-3 rounded-2xl",
                  incident.status === 'OPEN' ? "bg-error/10 text-error" : "bg-success/10 text-success"
                )}>
                  <AlertCircle size={24} />
                </div>
                <div>
                  <h3 className="text-lg font-bold group-hover:text-accent transition-colors">{incident.site_name}</h3>
                  <div className="flex items-center gap-3 mt-1 text-sm text-text-muted">
                    <span className="flex items-center gap-1">
                      <Clock size={14} /> 
                      {incident.status === 'OPEN' ? 'Active since' : 'Resolved at'} {new Date(incident.status === 'OPEN' ? incident.opened_at : incident.resolved_at).toLocaleString()}
                    </span>
                    <span>·</span>
                    <span className={cn("font-medium", incident.status === 'OPEN' ? "text-error" : "text-success")}>
                      {incident.error_message}
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-4 w-full md:w-auto">
                <Link 
                  to={`/site/${incident.site_id}`}
                  className="btn btn-secondary flex-1 md:flex-none rounded-full px-6 text-xs"
                >
                  View RCA
                </Link>
                <a 
                  href={incident.site_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="p-3 bg-white/5 rounded-full text-text-muted hover:text-accent hover:bg-accent/10 transition-all"
                >
                  <ExternalLink size={18} />
                </a>
              </div>
            </div>
          ))
        ) : (
          <div className="glass-panel p-20 text-center text-text-muted">
            <div className="w-20 h-20 bg-success/10 text-success rounded-full flex items-center justify-center mx-auto mb-6">
              <AlertCircle size={40} />
            </div>
            <h2 className="text-2xl font-bold text-text-primary mb-2">Clear Skies</h2>
            <p>No active incidents detected across your {incidents.length} monitored sites.</p>
          </div>
        )}
      </div>
    </motion.div>
  );
};
