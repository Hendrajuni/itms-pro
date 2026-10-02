import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "itms.settings")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    try:
        cursor.execute("ALTER TABLE governance_projectdocument ADD COLUMN document_type varchar(50) DEFAULT 'Other' NOT NULL;")
        print("Added document_type")
    except Exception as e:
        print("Error adding document_type:", e)
    
    try:
        cursor.execute("ALTER TABLE governance_projectdocument ADD COLUMN name varchar(255) DEFAULT '' NOT NULL;")
        print("Added name")
    except Exception as e:
        print("Error adding name:", e)
        
    try:
        cursor.execute("ALTER TABLE governance_projectdocument ALTER COLUMN file DROP NOT NULL;")
        print("Altered file to allow NULL")
    except Exception as e:
        print("Error altering file:", e)
