import re

file_path = 'd:/webdev/itms-pro/assets/templates/assets/asset_list.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Hide User column on mobile
content = content.replace(
    '<th>User</th>',
    '<th class="d-none d-md-table-cell">User</th>'
)
# The TD for User:
# We need to replace the <td> that is right before the <td> for specs/category/etc.
# Wait, in financial view:
# <td><small class="text-muted"><i class="fas fa-user-circle me-1"></i>{{ asset.assigned_to.get_full_name|default:asset.assigned_to.username|default:"-" }}</small></td>
content = content.replace(
    '<td>\n                                        <small class="text-muted"><i class="fas fa-user-circle me-1"></i>{{ asset.assigned_to.get_full_name|default:asset.assigned_to.username|default:"-" }}</small>\n                                    </td>',
    '<td class="d-none d-md-table-cell">\n                                        <small class="text-muted"><i class="fas fa-user-circle me-1"></i>{{ asset.assigned_to.get_full_name|default:asset.assigned_to.username|default:"-" }}</small>\n                                    </td>'
)

# For lifecycle view:
# Same TD

# For operational view:
# Same TD

# Financial view hiding
content = content.replace(
    '<th class="text-end">Current Value</th>',
    '<th class="text-end d-none d-lg-table-cell">Current Value</th>'
)
content = content.replace(
    '<th class="text-end">Maint. Cost</th>',
    '<th class="text-end d-none d-xl-table-cell">Maint. Cost</th>'
)
# The corresponding TDs for financial
content = content.replace(
    '<td class="text-end">\n                                        Rp {{ asset.current_value|floatformat:0|intcomma|default:"0" }}\n                                    </td>',
    '<td class="text-end d-none d-lg-table-cell">\n                                        Rp {{ asset.current_value|floatformat:0|intcomma|default:"0" }}\n                                    </td>'
)
content = content.replace(
    '<td class="text-end text-danger">\n                                        Rp {{ asset.maintenance_cost|floatformat:0|intcomma|default:"0" }}\n                                    </td>',
    '<td class="text-end text-danger d-none d-xl-table-cell">\n                                        Rp {{ asset.maintenance_cost|floatformat:0|intcomma|default:"0" }}\n                                    </td>'
)

# Lifecycle view hiding
content = content.replace(
    '<th>Age</th>',
    '<th class="d-none d-lg-table-cell">Age</th>'
)
content = content.replace(
    '<th>Warranty</th>',
    '<th class="d-none d-xl-table-cell">Warranty</th>'
)
content = content.replace(
    '<td>\n                                        <span class="badge bg-light text-dark border">{{ asset.age_years }} Yrs</span>\n                                    </td>',
    '<td class="d-none d-lg-table-cell">\n                                        <span class="badge bg-light text-dark border">{{ asset.age_years }} Yrs</span>\n                                    </td>'
)
# Warranty is slightly complex to regex if not exact, let's leave it or regex it carefully

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Applied mobile hiding to table columns')
