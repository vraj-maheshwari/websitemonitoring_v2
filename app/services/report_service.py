"""
services/report_service.py
--------------------------
Report generation for site monitoring data.
"""

import json
from datetime import datetime, timezone
from app.extensions import db
from app.models.site import Site
from app.models.uptime_log import UptimeLog
from app.models.ssl_log import SSLLog
from app.models.seo_log import SEOLog


def generate_site_report(site_id: int) -> dict:
    """
    Generate a comprehensive report for a site including all monitoring data.
    """
    site = db.session.get(Site, site_id)
    if not site:
        return None

    # Latest logs
    latest_uptime = UptimeLog.query.filter_by(site_id=site_id).order_by(UptimeLog.checked_at.desc()).first()
    latest_ssl = SSLLog.query.filter_by(site_id=site_id).order_by(SSLLog.checked_at.desc()).first()
    latest_seo = SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).first()

    # Recent history (last 10 records)
    uptime_history = [log.to_dict() for log in UptimeLog.query.filter_by(site_id=site_id).order_by(UptimeLog.checked_at.desc()).limit(10).all()]
    ssl_history = [log.to_dict() for log in SSLLog.query.filter_by(site_id=site_id).order_by(SSLLog.checked_at.desc()).limit(10).all()]
    seo_history = [log.to_dict() for log in SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).limit(5).all()]
    from app.models.dns_log import DNSLog
    dns_history = [log.to_dict() for log in DNSLog.query.filter_by(site_id=site_id).order_by(DNSLog.checked_at.desc()).limit(10).all()]


    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "site": {
            "id": site.id,
            "name": site.display_name(),
            "url": site.url,
            "created_at": site.created_at.isoformat() if site.created_at else None,
        },
        "current_status": {
            "app_status": site.app_status,
            "uptime_status": site.uptime_status,
            "ssl_status": site.ssl_status,
            "seo_status": site.seo_status,
        },
        "uptime": {
            "current_status": site.current_status,
            "last_response_time": site.last_response_time,
            "last_status_code": site.last_status_code,
            "last_ttfb": site.last_ttfb,
            "last_error_message": site.last_error_message,
            "last_check_at": site.last_uptime_check_at.isoformat() if site.last_uptime_check_at else None,
            "latest_log": latest_uptime.to_dict() if latest_uptime else None,
            "recent_history": uptime_history,
        },
        "ssl": {
            "state": site.ssl_state,
            "issuer": site.ssl_issuer,
            "expiry_date": site.ssl_expiry_date.isoformat() if site.ssl_expiry_date else None,
            "days_remaining": site.ssl_days_remaining,
            "last_error": site.ssl_last_error,
            "last_check_at": site.last_ssl_check_at.isoformat() if site.last_ssl_check_at else None,
            "latest_log": latest_ssl.to_dict() if latest_ssl else None,
            "recent_history": ssl_history,
        },
        "seo": {
            "score": site.seo_score,
            "state": site.seo_state,
            "last_error": site.seo_last_error,
            "last_check_at": site.last_seo_check_at.isoformat() if site.last_seo_check_at else None,
            "latest_log": _seo_log_to_dict(latest_seo) if latest_seo else None,
            "recent_history": [_seo_log_to_dict(log) for log in SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).limit(5).all()],
        },
        "security": {
            "score": site.security_score,
            "grade": site.security_grade,
            "last_error": site.security_last_error,
            "headers": site.security_headers,
            "last_check_at": site.last_security_check_at.isoformat() if site.last_security_check_at else None,
        },
        "dns": {
            "resolved": site.dns_resolved,
            "resolution_time_ms": site.dns_resolution_time_ms,
            "status": site.dns_status,
            "last_ips": site.dns_last_ips,
            "last_error": site.dns_last_error,
            "last_check_at": site.last_dns_check_at.isoformat() if site.last_dns_check_at else None,
            "recent_history": dns_history,
        },
        "configuration": {
            "uptime_check_interval": site.uptime_check_interval,
            "ssl_check_interval": site.ssl_check_interval,
            "seo_check_interval": site.seo_check_interval,
            "security_check_interval": site.security_check_interval,
            "dns_check_interval": site.dns_check_interval,
            "next_uptime_check_at": site.next_uptime_check_at.isoformat() if site.next_uptime_check_at else None,
            "next_ssl_check_at": site.next_ssl_check_at.isoformat() if site.next_ssl_check_at else None,
            "next_seo_check_at": site.next_seo_check_at.isoformat() if site.next_seo_check_at else None,
        },
    }

    return report
    

def generate_site_pdf_report(site_id: int) -> bytes:
    """
    Generate a PDF report using reportlab.
    """
    site = db.session.get(Site, site_id)
    if not site:
        return b""

    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"Monitoring Report: {site.display_name()}", styles['Title']))
    elements.append(Paragraph(f"URL: {site.url}", styles['Normal']))
    elements.append(Paragraph(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Summary Table
    data = [
        ["Category", "Current Status", "Key Metric", "Last Check"],
        ["Uptime", site.current_status, f"{round(site.last_response_time*1000) if site.last_response_time else 0}ms", site.last_uptime_check_at.strftime('%Y-%m-%d %H:%M') if site.last_uptime_check_at else "N/A"],
        ["SSL Security", site.ssl_state, f"{site.ssl_days_remaining or 0} Days", site.last_ssl_check_at.strftime('%Y-%m-%d %H:%M') if site.last_ssl_check_at else "N/A"],
        ["SEO Health", f"{site.seo_score}/100", f"LCP: {site.lh_lcp_ms or 0}ms", site.last_seo_check_at.strftime('%Y-%m-%d %H:%M') if site.last_seo_check_at else "N/A"],
        ["Security", site.security_grade or "N/A", f"{site.security_score or 0}% Hardened", site.last_security_check_at.strftime('%Y-%m-%d %H:%M') if site.last_security_check_at else "N/A"],
        ["DNS Status", "Verified" if site.dns_resolved else "Issue", f"{site.dns_resolution_time_ms or 0}ms", site.last_dns_check_at.strftime('%Y-%m-%d %H:%M') if site.last_dns_check_at else "N/A"],
    ]
    
    t = Table(data, colWidths=[100, 100, 120, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 30))

    # SEO Performance (Sub-table)
    elements.append(Paragraph("SEO & Performance Metrics", styles['Heading2']))
    seo_perf_data = [
        ["Metric", "Value", "Rating"],
        ["Performance Score", f"{site.lh_performance_score or 0}/100", "—"],
        ["LCP (Largest Contentful Paint)", f"{site.lh_lcp_ms or 0}ms", "Good" if (site.lh_lcp_ms or 0) < 2500 else "Poor"],
        ["TBT (Total Blocking Time)", f"{site.lh_tbt_ms or 0}ms", "Good" if (site.lh_tbt_ms or 0) < 200 else "Poor"],
        ["CLS (Cumulative Layout Shift)", f"{site.lh_cls or 0}", "Good" if (site.lh_cls or 0) < 0.1 else "Poor"],
    ]
    pt = Table(seo_perf_data, colWidths=[180, 150, 120])
    pt.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(pt)
    elements.append(Spacer(1, 20))

    # On-Page SEO Details
    latest_seo = SEOLog.query.filter_by(site_id=site_id).order_by(SEOLog.checked_at.desc()).first()
    if latest_seo:
        elements.append(Paragraph("On-Page SEO Analysis", styles['Heading2']))
        onpage_data = [
            ["Metric", "Count / Value", "Metric", "Count / Value"],
            ["H1 Tags", latest_seo.h1_count, "Word Count", latest_seo.word_count],
            ["H2 Tags", latest_seo.h2_count, "Images", latest_seo.image_count],
            ["H3 Tags", latest_seo.h3_count, "Missing Alt Tags", latest_seo.missing_alt_count],
        ]
        opt = Table(onpage_data, colWidths=[112, 112, 112, 112])
        opt.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
            ('BACKGROUND', (2, 0), (2, -1), colors.whitesmoke),
        ]))
        elements.append(opt)
        elements.append(Spacer(1, 20))

        # Link Analysis
        elements.append(Paragraph("Link Integrity Analysis", styles['Heading2']))
        link_data = [
            ["Category", "Count"],
            ["Total Links Crawled", latest_seo.links_checked],
            ["Internal Links", latest_seo.internal_link_count],
            ["External Links", latest_seo.external_link_count],
            ["Broken Links Found", latest_seo.broken_link_count],
        ]
        lt = Table(link_data, colWidths=[200, 250])
        lt.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('TEXTCOLOR', (0, 4), (1, 4), colors.red if latest_seo.broken_link_count > 0 else colors.black),
        ]))
        elements.append(lt)
        elements.append(Spacer(1, 20))


    # Security Headers
    elements.append(Paragraph("Security Headers Check", styles['Heading2']))
    headers = site.security_headers or {}
    h_data = [["Header", "Status"]]
    for h, val in headers.items():
        h_data.append([h, "PASS" if val else "MISSING"])
    
    if len(h_data) > 1:
        ht = Table(h_data, colWidths=[250, 100])
        ht.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TEXTCOLOR', (1, 1), (1, -1), colors.green),
        ]))
        elements.append(ht)
    else:
        elements.append(Paragraph("No security header data available.", styles['Normal']))

    elements.append(Spacer(1, 20))

    # Recent Incidents
    elements.append(Paragraph("Recent Uptime Incidents (Last 10)", styles['Heading2']))
    logs = UptimeLog.query.filter_by(site_id=site_id, is_up=False).order_by(UptimeLog.checked_at.desc()).limit(10).all()
    
    if logs:
        inc_data = [["Timestamp", "Error", "Status Code"]]
        for log in logs:
            inc_data.append([
                log.checked_at.strftime('%Y-%m-%d %H:%M'),
                (log.error_message or "N/A")[:50],
                log.status_code or "—"
            ])
        it = Table(inc_data, colWidths=[120, 240, 60])
        it.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8)
        ]))
        elements.append(it)
    else:
        elements.append(Paragraph("No incidents recorded. Site has been stable.", styles['Normal']))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _seo_log_to_dict(log) -> dict:
    """Convert SEOLog to dictionary, handling JSON fields safely."""
    if not log:
        return None

    return {
        "id": log.id,
        "site_id": log.site_id,
        "score": log.score,
        "status": log.status,
        "checked_at": log.checked_at.isoformat() if log.checked_at else None,
        "on_page": {
            "title": log.title,
            "title_length": log.title_length,
            "meta_description": log.meta_description,
            "meta_length": log.meta_length,
            "h1_count": log.h1_count,
            "h2_count": log.h2_count,
            "h3_count": log.h3_count,
            "word_count": log.word_count,
        },
        "technical": {
            "has_robots": log.has_robots,
            "has_sitemap": log.has_sitemap,
            "canonical": log.canonical,
            "has_favicon": log.has_favicon,
            "has_hreflang": log.has_hreflang,
            "robots_meta": log.robots_meta,
            "html_lang": log.html_lang,
        },
        "content": {
            "image_count": log.image_count,
            "missing_alt_count": log.missing_alt_count,
            "internal_link_count": log.internal_link_count,
            "external_link_count": log.external_link_count,
        },
        "performance": {
            "page_size_kb": log.page_size_kb,
            "js_blocking_count": log.js_blocking_count,
            "css_blocking_count": log.css_blocking_count,
            "ttfb": log.ttfb,
        },
        "mobile_and_security": {
            "has_viewport": log.has_viewport,
            "mobile_friendly": log.mobile_friendly,
            "https_redirect": log.https_redirect,
            "mixed_content_count": log.mixed_content_count,
        },
        "score_breakdown": log.score_breakdown,
        "issues": log.issues,
        "recommendations": log.recommendations,
        "error_message": log.error_message,
    }
