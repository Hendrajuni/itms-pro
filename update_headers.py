import re

with open('assets/templates/assets/asset_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

def replace_header(content, col_name, sort_key):
    pattern = r'<th[^>]*>\s*<a href="\?\{% param_replace sort=\'' + sort_key + r'\' order=\'(?:asc|desc)\' %\}"[^>]*>\s*(' + col_name + r')\s*(?:\{% if current_sort == \'' + sort_key + r'\' %\}[\s\S]*?\{% endif %\})?\s*</a>\s*</th>'
    
    # Simpler pattern just finding the TH block that contains the param_replace
    pattern = re.compile(
        r'<th[^>]*>\s*<a href="\?\{% param_replace sort=\'' + sort_key + r'\'[^\}]*%\}".*?>.*?</a>\s*</th>',
        re.DOTALL
    )
    
    replacement = f'''<th>
                                    <a href="?{{% if current_sort == '{sort_key}' and current_order == 'asc' %}}{{% param_replace sort='{sort_key}' order='desc' %}}{{% else %}}{{% param_replace sort='{sort_key}' order='asc' %}}{{% endif %}}" class="text-dark text-decoration-none text-nowrap">
                                        {col_name} 
                                        {{% if current_sort == '{sort_key}' %}}
                                            {{% if current_order == 'asc' %}}<i class="fas fa-sort-up text-primary ms-1"></i>{{% else %}}<i class="fas fa-sort-down text-primary ms-1"></i>{{% endif %}}
                                        {{% else %}}
                                            <i class="fas fa-sort text-muted opacity-25 ms-1"></i>
                                        {{% endif %}}
                                    </a>
                                </th>'''
    
    return re.sub(pattern, replacement, content)

content = replace_header(content, 'Asset', 'name')
content = replace_header(content, 'Category', 'category')
content = replace_header(content, 'Purchase Price', 'price')
content = replace_header(content, 'Purchase Date', 'purchase_date')
content = replace_header(content, 'Status', 'status')

with open('assets/templates/assets/asset_list.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Headers updated successfully!")
