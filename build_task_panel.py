import re

with open('d:/webdev/itms-pro/maintenance/templates/maintenance/maintenance_dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Get CSS
css_match = re.search(r'/\* Side Panel \*/.*?(?=/\* Sidebar Widgets \*/)', text, re.DOTALL)
css_content = css_match.group(0) if css_match else ''

# Get HTML
html_match = re.search(r'<!-- Task Detail Side Panel -->.*?(?=<!-- Complete Task Modal -->)', text, re.DOTALL)
html_content = html_match.group(0) if html_match else ''

# Get JS
js_match = re.search(r'// ====== SIDE PANEL ======.*?(?=// Checkbox)', text, re.DOTALL)
js_content = js_match.group(0) if js_match else ''

output = f"""<style>
{css_content}
@media (max-width: 767.98px) {{
    .task-panel {{ width: 100vw !important; right: -100vw; }}
    .task-panel.show {{ right: 0; }}
}}
</style>

{html_content}

<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
{js_content}
</script>
"""

import os
os.makedirs('d:/webdev/itms-pro/maintenance/templates/maintenance/components', exist_ok=True)
with open('d:/webdev/itms-pro/maintenance/templates/maintenance/components/task_panel.html', 'w', encoding='utf-8') as fw:
    fw.write(output)
