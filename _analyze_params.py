"""Analyze categories of remaining Siemens params after filtering."""
import json
import urllib.request
import uuid
import os

API_TOKEN = os.environ.get('PIF_API_TOKEN', '7261d39496da60ffab55ce2c74a613b694b87eb41bbc654ebad0c75c905191fa')

with open(r'C:\Users\ion.ursu\Downloads\FML3.zip', 'rb') as f:
    fdata = f.read()

boundary = uuid.uuid4().hex
parts = [
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="FML3.zip"\r\n'
    f'Content-Type: application/octet-stream\r\n\r\n'.encode(),
    fdata, b'\r\n',
    f'--{boundary}--\r\n'.encode()
]
body = b''.join(parts)
headers = {
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Authorization': f'Bearer {API_TOKEN}',
    'User-Agent': 'PIF/1.0',
}
req = urllib.request.Request('https://pif.iupif.org/api/import-archive/preview',
                             data=body, headers=headers)
result = json.loads(urllib.request.urlopen(req, timeout=120).read())
d = result['drives'][0]
params = d['params']

# Categorize by PNU range
categories = {}
for code, val in params.items():
    try:
        pnu = int(code.replace('p', '').split('[')[0])
    except ValueError:
        pnu = 99999
    if pnu < 100:
        cat = '0-99 monitoring/diag'
    elif pnu < 200:
        cat = '100-199 motor/basic'
    elif pnu < 300:
        cat = '200-299 converter'
    elif pnu < 400:
        cat = '300-399 motor data'
    elif pnu < 500:
        cat = '400-499 tech func'
    elif pnu < 600:
        cat = '500-599 tech'
    elif pnu < 700:
        cat = '600-699 tech'
    elif pnu < 800:
        cat = '700-799 tech/BICO'
    elif pnu < 900:
        cat = '800-899 BICO interconnect'
    elif pnu < 1000:
        cat = '900-999 faults/alarms'
    elif pnu < 2000:
        cat = '1000-1999 control/tech'
    elif pnu < 3000:
        cat = '2000-2999 communication'
    elif pnu < 4000:
        cat = '3000-3999 safety/ext'
    elif pnu < 5000:
        cat = '4000-4999 CU/boards'
    else:
        cat = '5000+ OEM/extended'
    categories.setdefault(cat, []).append((code, val))

for cat, items in sorted(categories.items()):
    print(f'{cat}: {len(items)} params')
    for code, val in items[:5]:
        desc = d.get('descrieri', {}).get(code, '')
        print(f'    {code:12} = {str(val):20} {desc[:40]}')
    if len(items) > 5:
        print(f'    ... +{len(items) - 5} more')

print(f'\nTotal: {len(params)} params')
