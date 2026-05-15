import json
import urllib.request

def fetch(url):
    try:
        r = urllib.request.urlopen(url, timeout=10)
        data = json.load(r)
        return data
    except Exception as e:
        return {'error': str(e)}

for url in ('http://127.0.0.1:8000/api/home-videos/','http://127.0.0.1:8000/api/reels-videos/'):
    data = fetch(url)
    print('\nURL:', url)
    if 'error' in data:
        print('Error:', data['error'])
        continue
    videos = data.get('videos', [])
    print('Total videos:', len(videos))
    for v in videos[:5]:
        print('-', json.dumps({
            'title': (v.get('title') or '')[:80],
            'videoId': v.get('videoId'),
            'thumbnail': v.get('thumbnail')
        }, ensure_ascii=False))
