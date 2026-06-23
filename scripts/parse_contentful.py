import json

with open('/var/folders/7j/qts1qph52rl4jlvxqyky7f640000gn/T/hermes-results/call_00_5dvHdoZGangrcIzi2TAc7968.txt') as f:
    data = json.loads(f.read())

result = data.get('result', data)
if isinstance(result, str):
    result = json.loads(result)

jobs = result.get('jobs', [])
print(f'Total jobs: {len(jobs)}')

swe_kw = ['software engineer', 'machine learning', 'ml engineer', 'ai engineer', 
          'data engineer', 'backend engineer', 'fullstack', 'full stack', 'devops',
          'platform engineer', 'site reliability', 'sre', 'data scientist',
          'engineering manager', 'staff engineer', 'principal engineer', 
          'backend', 'frontend', 'infrastructure']

for j in jobs:
    title = j.get('title', '')
    loc = j.get('location', {}).get('name', '')
    offices = [o.get('name', '') for o in j.get('offices', [])]
    content = j.get('content', '')
    abs_url = j.get('absolute_url', '')
    
    tl = title.lower()
    ll = loc.lower()
    os_str = ' '.join(offices).lower()
    cl = content.lower()
    
    is_swe = any(kw in tl for kw in swe_kw)
    if not is_swe:
        continue
    
    remote_loc = any(w in ll for w in ['remote', 'anywhere', 'global'])
    remote_off = any(w in os_str for w in ['remote', 'anywhere'])
    remote_con = ('fully remote' in cl or '100% remote' in cl or 'work remotely' in cl)
    
    if remote_loc or remote_off or remote_con:
        print(f'REMOTE: {title} | Loc: {loc} | URL: {abs_url} | Offices: {offices}')
    else:
        print(f'NON-REMOTE: {title} | Loc: {loc}')
