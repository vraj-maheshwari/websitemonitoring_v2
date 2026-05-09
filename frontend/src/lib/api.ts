import axios from 'axios';
import type { Site, DashboardMetrics, SEOLog, DashboardActivity } from '../types';

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // For session-based auth
});

// Interceptor will be configured by App.tsx to handle redirects
export const setAuthErrorHandler = (handler: () => void) => {
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        handler();
      }
      return Promise.reject(error);
    }
  );
};

export const authApi = {
  login: async (credentials: any) => {
    const { data } = await api.post('/auth/login', credentials);
    return data;
  },
  register: async (data: any) => {
    const { data: response } = await api.post('/auth/register', data);
    return response;
  }
};

export default api;

export const sitesApi = {
  list: async () => {
    const { data } = await api.get<Site[]>('/sites');
    return data;
  },
  get: async (id: number) => {
    const { data } = await api.get<Site>(`/sites/${id}`);
    return data;
  },
  create: async (siteData: { name?: string; url: string; check_interval?: number }) => {
    const { data } = await api.post<Site>('/sites', siteData);
    return data;
  },
  update: async (id: number, siteData: any) => {
    const { data } = await api.put<Site>(`/sites/${id}`, siteData);
    return data;
  },
  delete: async (id: number) => {
    await api.delete(`/sites/${id}`);
  },
  getAnalytics: async (id: number) => {
    const { data } = await api.get(`/sites/${id}/analytics`);
    return data;
  },
  getSEOLogs: async (id: number) => {
    const { data } = await api.get<SEOLog[]>(`/seo-logs/${id}`);
    return data;
  },
  getBrokenLinks: async (id: number) => {
    const { data } = await api.get(`/sites/${id}/broken-links`);
    return data;
  },
  getUptimeHistory: async (id: number, days: number = 7) => {
    const { data } = await api.get(`/sites/${id}/history/uptime?days=${days}`);
    return data;
  },
  runCheck: async (id: number, type: 'uptime' | 'ssl' | 'seo' | 'security' | 'dns' | 'all') => {
    const { data } = await api.post(`/sites/${id}/check`, { type });
    return data;
  }
};

export const dashboardApi = {
  getMetrics: async () => {
    const { data } = await api.get<DashboardMetrics>('/dashboard/metrics');
    return data;
  },
  getFleetAnalytics: async (days: number = 7) => {
    const { data } = await api.get(`/dashboard/analytics?days=${days}`);
    return data;
  },
  getActivity: async () => {
    const { data } = await api.get<DashboardActivity[]>('/dashboard/activity');
    return data;
  },
  getGlobalIncidents: async () => {
    const { data } = await api.get<any[]>('/incidents');
    return data;
  }
};
