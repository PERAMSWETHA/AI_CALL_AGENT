from app import app

client = app.test_client()
resp = client.post('/voice', data={'CallSid': 'test-call', 'From': '+15551234567'})
print('status', resp.status_code)
print(resp.get_data(as_text=True))
