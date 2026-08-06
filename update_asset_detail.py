import re

with open('assets/templates/assets/asset_detail.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Print Inspection button
btn_html = '''        {% endif %}
        <a href="{% url 'asset_inspection_print' asset.pk %}" target="_blank" class="btn btn-outline-secondary me-2">
            <i class="fas fa-file-signature me-1"></i> Print Inspection
        </a>'''
content = content.replace('        {% endif %}\n        <a href="{% url \'asset_update\'', btn_html + '\n        <a href="{% url \'asset_update\'')

# 2. Add Documents tab in Nav
nav_html = '''                            <li class="nav-item">
                                <a class="nav-link text-dark" data-bs-toggle="tab" href="#documents">
                                    Documents <span class="badge bg-secondary ms-1">{{ asset.documents.count }}</span>
                                </a>
                            </li>'''
content = re.sub(r'(<a class="nav-link text-dark" data-bs-toggle="tab" href="#notes">.*?</a>\s*</li>)', r'\1\n' + nav_html, content, flags=re.DOTALL)

# 3. Add Documents tab content
doc_html = '''
                    <!-- Documents Tab -->
                    <div class="tab-pane fade" id="documents">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h6 class="fw-bold mb-0">Attached Documents</h6>
                            <button type="button" class="btn btn-sm btn-primary" data-bs-toggle="modal" data-bs-target="#uploadDocumentModal">
                                <i class="fas fa-upload me-1"></i> Upload Document
                            </button>
                        </div>
                        
                        {% if asset.documents.exists %}
                        <div class="table-responsive">
                            <table class="table table-sm table-hover align-middle">
                                <thead>
                                    <tr>
                                        <th>Document Title</th>
                                        <th>Date Uploaded</th>
                                        <th>Uploaded By</th>
                                        <th>Notes</th>
                                        <th class="text-end">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for doc in asset.documents.all %}
                                    <tr>
                                        <td>
                                            <a href="{{ doc.document.url }}" target="_blank" class="fw-bold text-decoration-none">
                                                <i class="fas fa-file-pdf text-danger me-2"></i>{{ doc.title }}
                                            </a>
                                        </td>
                                        <td>{{ doc.uploaded_at|date:"d M Y, H:i" }}</td>
                                        <td>{{ doc.uploaded_by.username|default:"-" }}</td>
                                        <td><span class="text-muted small">{{ doc.notes|truncatechars:50|default:"-" }}</span></td>
                                        <td class="text-end">
                                            <a href="{{ doc.document.url }}" target="_blank" class="btn btn-sm btn-light" title="View/Download">
                                                <i class="fas fa-external-link-alt"></i>
                                            </a>
                                            <form action="{% url 'asset_document_delete' doc.id %}" method="post" class="d-inline">
                                                {% csrf_token %}
                                                <button type="submit" class="btn btn-sm btn-outline-danger border-0" onclick="return confirm('Delete this document?')" title="Delete">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                        {% else %}
                        <div class="text-center text-muted py-5">
                            <i class="fas fa-folder-open fa-3x opacity-25 mb-3"></i>
                            <p>No documents uploaded yet.</p>
                        </div>
                        {% endif %}
                    </div>
'''
content = re.sub(r'(<!-- Notes Tab -->.*?</div>\s*<!-- End Notes -->)', r'\1\n' + doc_html, content, flags=re.DOTALL)

# 4. Add modal include at the bottom
content = content.replace('{% endblock %}', '{% include "assets/document_upload_modal.html" %}\n{% endblock %}')

with open('assets/templates/assets/asset_detail.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Asset Detail updated.")
