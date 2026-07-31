from django import forms
from mptt.forms import TreeNodeChoiceField
from assets.models import Location
from .models import Subnet, IPAddress

class SubnetForm(forms.ModelForm):
    location = TreeNodeChoiceField(queryset=Location.objects.all().order_by('tree_id', 'lft'), required=False)

    class Meta:
        model = Subnet
        fields = ['name', 'cidr', 'location', 'gateway', 'vlan_id', 'description']
        widgets = {
            'name': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cidr': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 192.168.10.0/24'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'gateway': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 192.168.10.1'}),
            'vlan_id': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        # Name is now generated in view, so we don't need to validate it here yet.
        # But if it's required in model, we might need to dummy fill it or handle in save.
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Name is auto-generated in view, so it's not required from the user
        self.fields['name'].required = False
        
        # Filter Location for IT Support
        if self.user and not (self.user.is_superuser or self.user.groups.filter(name__in=['Administrator', 'Manager', 'Auditor']).exists()):
            if self.user.groups.filter(name='IT Support').exists() and hasattr(self.user, 'location') and self.user.location:
                # Restrict to their branch and descendants
                root_node = self.user.location.get_root() # Or user.location depending on policy. Using root to be safe for Regional Head logic, but user said "wilayahnya" (their region).
                # Let's use get_descendants(include_self=True) of the user's assigned location for strictness
                # Note: Location.get_descendants returns a list (custom override), but ModelChoiceField needs a QuerySet
                allowed_locations_list = self.user.location.get_descendants(include_self=True)
                allowed_ids = [loc.id for loc in allowed_locations_list]
                
                self.fields['location'].queryset = Location.objects.filter(id__in=allowed_ids).order_by('tree_id', 'lft')

class IPAddressForm(forms.ModelForm):
    class Meta:
        model = IPAddress
        fields = ['address', 'status', 'description', 'mac_address']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.subnet = kwargs.pop('subnet', None)
        super().__init__(*args, **kwargs)

    def clean_address(self):
        address = self.cleaned_data['address']
        if self.subnet:
            # Validate IP is in subnet
            import ipaddress
            try:
                ip_net = ipaddress.ip_network(self.subnet.cidr, strict=False)
                ip_addr = ipaddress.ip_address(address)
                if ip_addr not in ip_net:
                     raise forms.ValidationError(f"IP Address {address} is not within subnet {self.subnet.cidr}")
            except ValueError:
                raise forms.ValidationError("Invalid IP Address format.")
            
            # Check uniqueness in subnet (exclude self if editing, though this is create-only for now)
            # For create, self.instance.pk is None
            qs = IPAddress.objects.filter(subnet=self.subnet, address=address)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                 raise forms.ValidationError(f"IP Address {address} already exists in this subnet.")
        return address
