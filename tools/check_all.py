import urllib.request, json
urls=['http://127.0.0.1:8000/','http://127.0.0.1:8000/reels/','http://127.0.0.1:8000/api/home-videos/','http://127.0.0.1:8000/api/reels-videos/']
for u in urls:
    try:
        r=urllib.request.urlopen(u,timeout=10)
        print('\nURL:',u,'STATUS',r.getcode())
        data=r.read(2048).decode('utf-8',errors='ignore')
        if u.endswith('/api/home-videos/') or u.endswith('/api/reels-videos/'):
            try:
                obj=json.loads(data)
                print('videos_count=', len(obj.get('videos', [])))
            except Exception:
                print('api parse error')
        else:
            print(data.split('\n')[0])
    except Exception as e:
        print('\nURL:',u,'ERROR',e)
