import { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import { 
  ChevronRight,
  Plus,
  Search,
  RefreshCw
} from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './components/Dashboard';
import { SiteDetail } from './components/SiteDetail';
import { AddMonitorModal } from './components/AddMonitorModal';
import { Login } from './components/Login';
import { Register } from './components/Register';

import { sitesApi, setAuthErrorHandler } from './lib/api';
import { FleetAnalytics } from './components/FleetAnalytics';
import { IncidentsLog } from './components/IncidentsLog';
import { SecurityDashboard } from './components/SecurityDashboard';
import { GlobalSettings } from './components/GlobalSettings';

function App() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    // Check initial auth
    sitesApi.list()
      .then(() => setIsAuthenticated(true))
      .catch((err) => {
        if (err.response?.status === 401) {
          setIsAuthenticated(false);
        }
      });

    setAuthErrorHandler(() => {
      setIsAuthenticated(false);
    });
  }, [refreshTrigger]);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-background-primary flex items-center justify-center">
        <RefreshCw className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={() => setIsAuthenticated(true)} />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Login onLogin={() => setIsAuthenticated(true)} />} />
      </Routes>
    );
  }

  return (
    <div className="flex min-h-screen bg-background-primary text-text-primary overflow-hidden">
      <Sidebar onAddClick={() => setShowAddModal(true)} />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Topbar */}
        <header className="h-16 border-b border-border flex items-center justify-between px-8 sticky top-0 bg-background-primary/80 backdrop-blur-xl z-20">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">Fleet</span>
            <ChevronRight size={14} className="text-text-muted" />
            <span className="font-medium">Overview</span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="relative group">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-accent transition-colors" />
              <input 
                type="text" 
                placeholder="Search sites..." 
                className="bg-white/5 border border-border rounded-full pl-10 pr-4 py-1.5 text-sm focus:outline-none focus:border-accent/50 focus:ring-4 focus:ring-accent/10 transition-all w-64"
              />
            </div>
            <button 
              onClick={() => setShowAddModal(true)}
              className="btn btn-primary btn-sm rounded-full h-9 px-5"
            >
              <Plus size={16} />
              <span>Add Monitor</span>
            </button>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Dashboard onAddClick={() => setShowAddModal(true)} key={refreshTrigger} />} />
          <Route path="/site/:id" element={<SiteDetail />} />
          <Route path="/analytics" element={<FleetAnalytics />} />
          <Route path="/incidents" element={<IncidentsLog />} />
          <Route path="/security" element={<SecurityDashboard />} />
          <Route path="/settings" element={<GlobalSettings onLogout={() => setIsAuthenticated(false)} />} />
        </Routes>

        {showAddModal && (
          <AddMonitorModal 
            isOpen={showAddModal}
            onClose={() => setShowAddModal(false)} 
            onSuccess={() => setRefreshTrigger(prev => prev + 1)} 
          />
        )}
      </main>
    </div>
  );
}

export default App;
