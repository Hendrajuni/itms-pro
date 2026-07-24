import re

file_path = 'd:/webdev/itms-pro/assets/templates/assets/asset_list.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Main Header wrap
content = content.replace(
    '<div class="d-flex justify-content-between align-items-center mb-4">',
    '<div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 mb-4">'
)

# 2. Dropdown buttons wrap
content = content.replace(
    '<div class="d-flex gap-2">',
    '<div class="d-flex flex-wrap gap-2 w-100 w-md-auto">'
)

# 3. Filter form wrap
content = content.replace(
    '<form method="get" id="filterForm" class="d-flex position-relative me-2 align-items-center">',
    '<form method="get" id="filterForm" class="d-flex flex-wrap gap-2 position-relative align-items-center flex-grow-1 flex-md-grow-0">'
)

# 4. Search input style
content = content.replace(
    'style="width: 200px; background-color: #f8f9fa;"',
    'style="min-width: 150px; flex: 1; background-color: #f8f9fa;"'
)

# 5. Non-Admin Search Form wrap
content = content.replace(
    '<form method="get" class="d-flex position-relative me-2 align-items-center">',
    '<form method="get" class="d-flex flex-wrap position-relative gap-2 align-items-center w-100 w-md-auto">'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced toolbar classes')
