from django import forms
from django.forms import inlineformset_factory
from .models import Asset, AssetSpecification, NetworkInterface, AssetLoan, Software, SoftwareAllocation, CloudAsset, Infrastructure, Contract, AssetStorage, Location, PartHistory

class AssetStorageForm(forms.ModelForm):
    class Meta:
        model = AssetStorage
        fields = ['device_type', 'brand', 'capacity', 'serial_number', 'purchase_date']
        widgets = {
             'device_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
             'brand': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
             'capacity': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
             'serial_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
             'purchase_date': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        }

AssetStorageFormSet = inlineformset_factory(
    Asset, AssetStorage,
    form=AssetStorageForm,
    extra=0,
    can_delete=True
)

class NetworkInterfaceForm(forms.ModelForm):
    class Meta:
        model = NetworkInterface
        fields = ['name', 'subnet', 'ip_address', 'mac_address', 'vlan_id', 'is_active']
        widgets = {
             'name': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. eth0'}),
             'subnet': forms.Select(attrs={'class': 'form-select form-select-sm'}),
             'ip_address': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '192.168.1.10'}),
             'mac_address': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '00:1A:...'}),
             'vlan_id': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '10'}),
             'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

NetworkInterfaceFormSet = inlineformset_factory(
    Asset, NetworkInterface,
    form=NetworkInterfaceForm,
    extra=0,
    can_delete=True
)

from governance.models import DailyLog, Project
from maintenance.models import AssetMaintenance, InfraMaintenance

class AssetForm(forms.ModelForm):
    # Specification Fields (manually added)
    cpu = forms.CharField(required=False, label="Processor (CPU)", widget=forms.TextInput(attrs={'class': 'form-control'}))
    ram = forms.CharField(required=False, label="Memory (RAM)", widget=forms.TextInput(attrs={'class': 'form-control'}))
    motherboard = forms.CharField(required=False, label="Motherboard", widget=forms.TextInput(attrs={'class': 'form-control'}))
    os = forms.CharField(required=False, label="Operating System", widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    # Note: IP and MAC are now handled by NetworkInterfaceFormSet, but we keep these for legacy/single-homed view if needed OR remove them.
    # User requested multi-interface. We should probably remove them from THIS form to avoid confusion, 
    # OR map the primary interface IP here. 
    # For now, I will keep them as "Primary Spec" but the robust way is the formset.
    
    # Let's keep them as "Management IP" / "Primary MAC" in spec for simplicity if user ignores the advanced table.
    ip_address = forms.GenericIPAddressField(required=False, label="Management IP", widget=forms.TextInput(attrs={'class': 'form-control'}))
    mac_address = forms.CharField(required=False, label="Primary MAC", widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Asset
        fields = [
            'category', 'name', 'status', 'assigned_to', 
            'brand', 'model', 'serial_number',
            'purchase_date', 'purchase_price', 'vendor', 
            'location', 'photo', 'warranty_end', 'invoice_number'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing an existing asset, populate spec fields
        if self.instance.pk and hasattr(self.instance, 'specification'):
            spec = self.instance.specification
            self.fields['cpu'].initial = spec.cpu
            self.fields['ram'].initial = spec.ram
            self.fields['motherboard'].initial = spec.motherboard
            self.fields['os'].initial = spec.os
            self.fields['ip_address'].initial = spec.ip_address
            self.fields['mac_address'].initial = spec.mac_address

    def save(self, commit=True):
        asset = super().save(commit=False)
        if commit:
            asset.save()
            
            # Save Specification
            spec, created = AssetSpecification.objects.get_or_create(asset=asset)
            spec.cpu = self.cleaned_data.get('cpu')
            spec.ram = self.cleaned_data.get('ram')
            spec.motherboard = self.cleaned_data.get('motherboard')
            spec.os = self.cleaned_data.get('os')
            spec.ip_address = self.cleaned_data.get('ip_address')
            spec.mac_address = self.cleaned_data.get('mac_address')
            spec.save()
            
        return asset

from network.models import Subnet

class NetworkInterfaceForm(forms.ModelForm):
    class Meta:
        model = NetworkInterface
        fields = ['name', 'subnet', 'ip_address', 'mac_address', 'vlan_id', 'is_active']
        widgets = {
             'name': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. eth0'}),
             'subnet': forms.Select(attrs={'class': 'form-select form-select-sm'}),
             'ip_address': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '192.168.1.10'}),
             'mac_address': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '00:1A:...'}),
             'vlan_id': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '10'}),
             'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Scoped Subnet dropdown for IT Support
        if self.user and not (self.user.is_superuser or self.user.groups.filter(name__in=['Administrator', 'Manager']).exists()):
             if self.user.groups.filter(name='IT Support').exists() and hasattr(self.user, 'location') and self.user.location:
                  # Filter subnets by user's location (including descendants)
                  descendants = self.user.location.get_descendants(include_self=True)
                  # descendants is a list, extract IDs
                  descendant_ids = [loc.id for loc in descendants]
                  self.fields['subnet'].queryset = Subnet.objects.filter(location_id__in=descendant_ids).order_by('name')

NetworkInterfaceFormSet = inlineformset_factory(
    Asset, NetworkInterface,
    form=NetworkInterfaceForm,
    extra=1,
    can_delete=True
)

class AssetNoteForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['notes']
        widgets = {
             'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class AssetLoanForm(forms.ModelForm):
    class Meta:
        model = AssetLoan
        fields = ['employee', 'loan_date', 'condition_out']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'loan_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'condition_out': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class AssetMaintenanceForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenance
        fields = ['asset', 'title', 'maintenance_type', 'scheduled_date', 'status', 'cost', 'technician', 'vendor', 'notes', 'maintenance_checklist']
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'technician': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'maintenance_checklist': forms.HiddenInput(),
        }

class InfraMaintenanceForm(forms.ModelForm):
    class Meta:
        model = InfraMaintenance
        fields = ['infrastructure', 'title', 'maintenance_type', 'scheduled_date', 'status', 'cost', 'technician', 'vendor', 'notes', 'maintenance_checklist']
        widgets = {
            'infrastructure': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'technician': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'maintenance_checklist': forms.HiddenInput(),
        }

class SoftwareForm(forms.ModelForm):
    class Meta:
        model = Software
        fields = ['name', 'vendor', 'license_key', 'license_type', 'purchase_date', 'expiry_date', 'price', 'seats_total', 'category', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'license_key': forms.TextInput(attrs={'class': 'form-control'}),
            'license_type': forms.Select(attrs={'class': 'form-select'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'seats_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SoftwareAllocationForm(forms.ModelForm):
    class Meta:
        model = SoftwareAllocation
        fields = ['software', 'employee', 'asset', 'assigned_date', 'notes']
        widgets = {
            'software': forms.Select(attrs={'class': 'form-select'}),
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'asset': forms.Select(attrs={'class': 'form-select'}),
            'assigned_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

SoftwareAllocationFormSet = inlineformset_factory(
    Asset, SoftwareAllocation,
    form=SoftwareAllocationForm,
    extra=0,
    can_delete=True
)

class CloudAssetForm(forms.ModelForm):
    class Meta:
        model = CloudAsset
        fields = ['name', 'provider', 'service_type', 'ip_address', 'billing_cycle', 'cost', 'purchase_date', 'expiry_date', 'auto_renew', 'status', 'login_url', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. company.com'}),
            'provider': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS, GoDaddy'}),
            'service_type': forms.Select(attrs={'class': 'form-select'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'login_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class InfrastructureForm(forms.ModelForm):
    class Meta:
        model = Infrastructure
        fields = ['name', 'type', 'location', 'capacity', 'photo', 'condition', 'last_maintenance_date', 'next_maintenance_date', 'notes', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 42U, 1200VA'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'last_maintenance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_maintenance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Latitude (e.g. -6.200000)'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Longitude (e.g. 106.816666)'}),
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'type', 'parent', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ['title', 'vendor', 'contract_type', 'start_date', 'end_date', 'billing_cycle', 'cost', 'ip_address', 'login_url', 'document', 'auto_renew', 'notify_days_before', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional (for VPS/Hosting)'}),
            'login_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Optional (https://...)'}),
            'document': forms.FileInput(attrs={'class': 'form-control'}),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_days_before': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# class DailyLogForm(forms.ModelForm):
#     class Meta:
#         model = DailyLog
#         fields = ['date', 'task', 'asset', 'activity', 'description', 'category', 'duration', 'status']
#         widgets = {
#             'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
#             'task': forms.Select(attrs={'class': 'form-select'}),
#             'asset': forms.Select(attrs={'class': 'form-select'}),
#             'activity': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Or type custom activity...'}),
#             'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
#             'category': forms.Select(attrs={'class': 'form-select'}),
#             'duration': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
#             'status': forms.Select(attrs={'class': 'form-select'}),
#         }
#     
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Optional: Make name/category optional if task is selected (handled in clean() ideally)
#         self.fields['task'].empty_label = "Select Standard Task (Optional)"
#         self.fields['asset'].empty_label = "Select Asset (Optional)"

# class ProjectForm(forms.ModelForm):
#     class Meta:
#         model = Project
#         fields = ['name', 'description', 'manager', 'start_date', 'end_date', 'status', 'priority', 'progress', 'budget']
#         widgets = {
#             'name': forms.TextInput(attrs={'class': 'form-control'}),
#             'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
#             'manager': forms.Select(attrs={'class': 'form-select'}),
#             'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
#             'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
#             'status': forms.Select(attrs={'class': 'form-select'}),
#             'priority': forms.Select(attrs={'class': 'form-select'}),
#             'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
#             'budget': forms.NumberInput(attrs={'class': 'form-control'}),
#         }
class PartHistoryForm(forms.ModelForm):
    class Meta:
        model = PartHistory
        fields = ['part_name', 'action_date', 'description', 'cost', 'vendor']
        widgets = {
            'part_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Motherboard, RAM Upgrade'}),
            'action_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
        }
