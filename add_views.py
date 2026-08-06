from textwrap import dedent

with open('assets/views.py', 'a', encoding='utf-8') as f:
    f.write(dedent('''
    
    # --- Asset Inspection and Document Management ---
    
    class AssetInspectionPrintView(LoginRequiredMixin, DetailView):
        model = Asset
        template_name = 'assets/asset_inspection_print.html'
        context_object_name = 'asset'
    
    class AssetDocumentUploadView(LoginRequiredMixin, CreateView):
        model = AssetDocument
        form_class = AssetDocumentForm
        template_name = 'assets/document_upload_modal.html'
        
        def form_valid(self, form):
            form.instance.asset_id = self.kwargs['asset_id']
            form.instance.uploaded_by = self.request.user
            messages.success(self.request, 'Document uploaded successfully.')
            return super().form_valid(form)
            
        def get_success_url(self):
            return reverse('asset_detail', kwargs={'pk': self.kwargs['asset_id']}) + '#documents'

    class AssetDocumentDeleteView(LoginRequiredMixin, DeleteView):
        model = AssetDocument
        
        def get_success_url(self):
            messages.success(self.request, 'Document deleted successfully.')
            return reverse('asset_detail', kwargs={'pk': self.object.asset_id}) + '#documents'
    '''))
print("Views added successfully.")
