from django import forms
from mptt.forms import TreeNodeChoiceField
from assets.models import Location
from .models import Subnet

class SubnetForm(forms.ModelForm):
    location = TreeNodeChoiceField(queryset=Location.objects.all(), required=False)

    class Meta:
        model = Subnet
        fields = ['name', 'cidr', 'location', 'gateway', 'vlan_id', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
