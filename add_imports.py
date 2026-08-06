import re

with open('assets/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add AssetDocument to models import
content = re.sub(r'from \.models import ([^\n]+)', r'from .models import \1, AssetDocument', content, count=1)

# Add AssetDocumentForm to forms import
content = re.sub(r'from \.forms import ([^\n]+)', r'from .forms import \1, AssetDocumentForm', content, count=1)

with open('assets/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Imports added successfully.")
