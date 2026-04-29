#!/usr/bin/env python
from app import create_app
from app.services.report_service import generate_site_report
import json

app = create_app()
ctx = app.app_context()
ctx.push()

report = generate_site_report(1)
json_str = json.dumps(report, indent=2, default=str)

print('✓ Report generated')
print('JSON size: ' + str(len(json_str)) + ' bytes')
print('\nSample keys present:')
for key in ['site', 'current_status', 'uptime', 'ssl', 'seo', 'configuration']:
    if key in report:
        print('  ✓ ' + key)

print('\nSample data:')
print('  Site: ' + report['site']['name'])
print('  Status: ' + report['current_status']['app_status'])
print('  Uptime: ' + str(report['uptime']['last_response_time']) + 's')
print('  SSL: ' + report['ssl']['issuer'])
print('  SEO: ' + str(report['seo']['score']) + '/100')
