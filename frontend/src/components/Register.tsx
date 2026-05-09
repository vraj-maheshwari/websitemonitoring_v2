import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { authApi } from '../lib/api';

export const Register = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    setError('');
    try {
      await authApi.register({ email, password, confirm_password: confirmPassword });
      navigate('/login');
    } catch (err: any) {
      setError(err.response?.data?.error || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md p-10"
      >
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-gradient-to-br from-accent to-blue-600 rounded-xl flex items-center justify-center text-white text-xl font-bold mx-auto mb-4 shadow-lg shadow-accent/20">
            P
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight">Create Account</h1>
          <p className="text-text-secondary text-sm">Start monitoring your websites in minutes</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-error/10 border border-error/20 text-error text-xs rounded-xl text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-text-muted uppercase tracking-widest mb-2">Email Address</label>
            <input 
              type="email" 
              required 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-white/5 border border-border rounded-xl px-4 py-3 text-sm focus:border-accent outline-none transition-colors"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-text-muted uppercase tracking-widest mb-2">Password</label>
            <input 
              type="password" 
              required 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-white/5 border border-border rounded-xl px-4 py-3 text-sm focus:border-accent outline-none transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label className="block text-[10px] font-black text-text-muted uppercase tracking-widest mb-2">Confirm Password</label>
            <input 
              type="password" 
              required 
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full bg-white/5 border border-border rounded-xl px-4 py-3 text-sm focus:border-accent outline-none transition-colors"
              placeholder="••••••••"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full btn btn-primary py-4 rounded-xl font-bold shadow-lg shadow-accent/20 transition-all active:scale-95"
          >
            {loading ? "Creating Account..." : "Create Account →"}
          </button>
        </form>

        <p className="mt-8 text-center text-xs text-text-muted font-medium">
          Already have an account? <Link to="/login" className="text-accent hover:underline">Sign in</Link>
        </p>
      </motion.div>
    </div>
  );
};
