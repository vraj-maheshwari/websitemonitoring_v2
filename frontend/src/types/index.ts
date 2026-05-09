export interface Site {
  id: number;
  url: string;
  name: string | null;
  current_status: 'UP' | 'DOWN' | 'DEGRADED' | 'UNKNOWN';
  last_status_code: number | null;
  last_response_time: number | null;
  last_ttfb: number | null;
  last_uptime_check_at: string | null;
  
  ssl_state: 'VALID' | 'EXPIRING' | 'EXPIRED' | 'ERROR' | 'UNKNOWN';
  ssl_issuer: string | null;
  ssl_days_remaining: number | null;
  
  seo_score: number;
  seo_status: string;
  seo_state: string;
  last_seo_fetch_valid: boolean;
  
  dns_status: 'pending' | 'running' | 'done' | 'failed';
  dns_resolved: boolean;
  dns_resolution_time_ms: number | null;
  dns_hijack_suspected: boolean;
  dns_ns_changed: boolean;
  dns_last_ips: string[];
  dns_last_ns: string[];
  dns_last_error: string | null;
  last_dns_check_at: string | null;
  
  app_status: 'idle' | 'checking';
  uptime_status: 'pending' | 'running' | 'done' | 'failed';
  ssl_status: 'pending' | 'running' | 'done' | 'failed';
  security_status: 'pending' | 'running' | 'done' | 'failed';
  
  security_score: number;
  security_grade: string | null;
  security_headers?: Record<string, boolean>;
  
  uptime_check_interval: number;
  ssl_check_interval: number;
  seo_check_interval: number;
}

export interface DashboardMetrics {
  monitored_sites: number;
  sites_up: number;
  sites_down: number;
  avg_response: number | null;
  health_score: number;
  dns_issue_count: number;
  ssl_critical_count: number;
  dns_checked_count: number;
  sites_with_ssl: number;
  seo_avg_score: number;
}

export interface DashboardActivity {
  id: number;
  site_id: number;
  site_name: string;
  error_message: string;
  checked_at: string;
  status_code: number | null;
}

export interface SEOLog {
  id: number;
  score: number | null;
  status: string;
  title: string;
  title_length: number;
  meta_description: string;
  meta_length: number;
  h1_count: number;
  h2_count: number;
  h3_count: number;
  word_count: number;
  image_count: number;
  missing_alt_count: number;
  internal_link_count: number;
  external_link_count: number;
  has_robots: boolean;
  has_sitemap: boolean;
  canonical: string | null;
  robots_meta: string | null;
  html_lang: string | null;
  has_favicon: boolean;
  has_hreflang: boolean;
  page_size_kb: number;
  ttfb: number | null;
  mobile_friendly: boolean;
  https_redirect: boolean;
  mixed_content_count: number;
  js_blocking_count: number;
  css_blocking_count: number;
  score_breakdown: {
    on_page?: number;
    technical?: number;
    content?: number;
    performance?: number;
    security_mobile?: number;
  } | null;
  issues: string[];
  recommendations: string[];
  tech_stack: Record<string, string[]>;
  tech_flat: string[];
  broken_link_count: number;
  links_checked: number;
  security_score: number | null;
  security_grade: string | null;
  security_headers: Record<string, boolean>;
  lighthouse?: {
    performance_score: number | null;
    metrics: {
      lcp: { value_ms: number | null; rating: string };
      fcp: { value_ms: number | null; rating: string };
      tbt: { value_ms: number | null; rating: string };
      cls: { value: number | null; rating: string };
      ttfb: { value_ms: number | null; rating: string };
    };
  };
  broken_links?: {
    total_found: number;
    total_checked: number;
    broken_count: number;
    internal_count: number;
    external_count: number;
    broken: any[];
  };
}
