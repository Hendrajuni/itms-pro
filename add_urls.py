import re

with open('assets/urls.py', 'r', encoding='utf-8') as f:
    content = f.read()

url_patterns = '''
    path('<int:pk>/inspection/print/', views.AssetInspectionPrintView.as_view(), name='asset_inspection_print'),
    path('<int:asset_id>/document/add/', views.AssetDocumentUploadView.as_view(), name='asset_document_upload'),
    path('document/<int:pk>/delete/', views.AssetDocumentDeleteView.as_view(), name='asset_document_delete'),
'''

content = re.sub(r'(path\(\'<int:pk>/print-label/\',)', url_patterns + r'    \1', content)

with open('assets/urls.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("URLs added successfully.")
