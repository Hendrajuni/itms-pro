# ITMS Edition Comparison

This document outlines the feature differences between the **Essential (Free)** and **Enterprise (Pro)** editions of the IT Management System.

| Feature Category | Feature | Essential (Free) | Enterprise (Pro) |
| :--- | :--- | :---: | :---: |
| **Core Limits** | **Locations / Branches** | **1** (Single Site) | **Unlimited** |
| **Core Limits** | **Admin Users** | **1** (Single Admin) | **Unlimited** |
| **Core Limits** | **Asset Limit** | **100 Items** | Unlimited |
| **Dashboard** | **Branch Health Overview** | ❌ Hidden | ✅ Visible |
| **Dashboard** | **Contract Expiry Alerts** | ❌ Hidden | ✅ Visible |
| **Dashboard** | **Software License Alerts** | ❌ Hidden | ✅ Visible |
| **Asset Management** | **Print QR / Barcode** | ❌ Disabled | ✅ Enabled |
| **Asset Management** | **Print Asset Report** | ❌ Disabled | ✅ Enabled |
| **Asset Management** | **Asset History / Audit** | ❌ Hidden | ✅ Visible |
| **System & Admin** | **Integrations** | ❌ Hidden | ✅ Visible |
| **System & Admin** | **Activity / Audit Logs** | ❌ Hidden | ✅ Visible |
| **System & Admin** | **Django Admin Access** | ❌ Hidden | ✅ Visible |
| **System & Admin** | **Site Settings** | ✅ Basic | ✅ Full |
| **Support** | **SLA** | Community / None | Priority Support |

## Implementation details
- **Enforcement**: Limits are enforced at both the **UI level** (buttons hidden) and the **Backend level** (blocking requests).
- **Activation**: Enterprise features are unlocked via a valid License Key.
