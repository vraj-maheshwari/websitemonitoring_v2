import React, { useState } from 'react';
import { Mail, Lock, ChevronRight, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../lib/api';

interface LoginProps {
  onLogin: () => void;
}

export const Login = ({ onLogin }: LoginProps) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post('/auth/login', { email, password });
      onLogin();
    } catch (err: any) {
      console.error("Login Error:", err.response?.data);
      // @ts-ignore
      window.__debug_error_data = err.response?.data;
      
      const errorMessage = err.response?.data?.message || err.response?.data?.error || "Invalid email or password";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-primary p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-accent rounded-2xl mb-6 shadow-xl shadow-accent/20">
            <span className="text-3xl font-black text-white">P</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">Welcome back</h1>
          <p className="text-text-secondary mt-2">Sign in to your Pulse account</p>
        </div>

        <div className="bg-background-card border border-border p-8 rounded-card shadow-premium">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="space-y-2">
                <div className="p-3 bg-error/10 border border-error/20 text-error text-sm rounded-lg text-center font-semibold">
                  {error}
                </div>
                {/* @ts-ignore */}
                {window.__debug_error_data?.traceback && (
                  <pre className="p-4 bg-black/40 text-[10px] text-error/80 rounded-lg overflow-auto max-h-40 font-mono">
                    {/* @ts-ignore */}
                    {window.__debug_error_data.traceback}
                  </pre>
                )}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">Email Address</label>
                <div className="relative">
                  <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                  <input 
                    type="email" 
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="w-full bg-white/5 border border-border rounded-lg pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-accent transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">Password</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                  <input 
                    type="password" 
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-white/5 border border-border rounded-lg pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-accent transition-all"
                  />
                </div>
              </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full btn btn-primary py-3 rounded-lg flex items-center justify-center gap-2 group"
            >
              {loading ? (
                <RefreshCw size={20} className="animate-spin" />
              ) : (
                <>
                  <span>Sign In</span>
                  <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>
          
          <div className="mt-8 pt-6 border-t border-border text-center">
            <p className="text-sm text-text-muted">
              Don't have an account? <Link to="/register" className="text-accent hover:underline">Sign up</Link>
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-text-muted">
          &copy; 2026 Pulse SaaS Intelligence. All rights reserved.
        </p>
      </div>
    </div>
  );
};
