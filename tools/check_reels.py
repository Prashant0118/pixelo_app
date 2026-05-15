import urllib.request, urllib.error, json
url='http://127.0.0.1:8000/api/reels-videos/?max_results=12&q=All%20shorts:1'
req=urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print('STATUS', r.getcode())
        data=json.load(r)
        print('videos_count=', len(data.get('videos', [])))
        print('sample=', data.get('videos', [])[:2])
except urllib.error.HTTPError as e:
    print('HTTPERR', e.code)
    try:
        print(e.read().decode('utf-8'))
    except Exception:
        pass
except Exception as e:
    print('ERR', e)
