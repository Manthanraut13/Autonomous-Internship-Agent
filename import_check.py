import sys, os, importlib
root = r'c:/Users/ADMIN/Desktop/Autonomus Internship Agent'
if root not in sys.path:
    sys.path.insert(0, root)
modules = [
    'tools.whatsapp_handler',
    'tools.application_filler',
    'main',
    'db.models',
    'config.settings',
    'db.database',
]
errors = []
for m in modules:
    try:
        importlib.import_module(m)
    except Exception as e:
        errors.append((m, str(e)))
print('Import errors:', errors)
