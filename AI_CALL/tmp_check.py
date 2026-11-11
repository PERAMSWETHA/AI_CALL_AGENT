import pathlib
root = pathlib.Path('.venv/Lib/site-packages').resolve()
print('site-packages', root)
path = root / 'twilio' / 'rest' / 'api' / 'v2010' / 'account' / 'sip' / 'domain' / 'auth_types' / 'auth_type_registrations'
print('path', path)
print('exists', path.exists())
print('contents', sorted(p.name for p in path.iterdir()) if path.exists() else 'missing')
import twilio.rest.api.v2010.account.sip.domain.auth_types.auth_type_registrations as m
print('imported', m)
