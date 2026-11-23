import urllib.request
import urllib.parse
import json
import sys

def query_overpass(query):
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    req = urllib.request.Request(
        'https://overpass-api.de/api/interpreter',
        data=data,
        method='POST'
    )
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode('utf-8'))

# Query 1: Transit nodes and ways with Metrolinea-related names in Bucaramanga area
q1 = '''[out:json][timeout:90];
(
  node["public_transport"](7.0,-73.25,7.3,-73.0);
  node["highway"="bus_stop"](7.0,-73.25,7.3,-73.0);
  way["public_transport"="station"](7.0,-73.25,7.3,-73.0);
  relation["route"="bus"]["operator"~"Metrolinea|Metrolínea",i](7.0,-73.25,7.3,-73.0);
);
out center;'''

print("Querying Overpass API for public transport nodes...")
try:
    result = query_overpass(q1)
    print(f"Found {len(result.get('elements', []))} elements")
    with open('overpass_transit.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Saved to overpass_transit.json")
    
    # Print first 10 elements
    for el in result.get('elements', [])[:20]:
        name = el.get('tags', {}).get('name', 'N/A')
        lat = el.get('lat', el.get('center', {}).get('lat', 'N/A'))
        lon = el.get('lon', el.get('center', {}).get('lon', 'N/A'))
        pt = el.get('tags', {}).get('public_transport', el.get('tags', {}).get('highway', 'N/A'))
        print(f"  [{el['type']}] {name} | {lat}, {lon} | {pt}")
        
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
