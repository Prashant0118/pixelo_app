import urllib.request

urls = ['http://127.0.0.1:8000/', 'http://127.0.0.1:8000/reels/']
for url in urls:
    req = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print('\nURL:', url)
            for k, v in r.getheaders():
                print(f'{k}: {v}')
    except Exception as e:
        print('\nError fetching', url, e)
