import os, sys
# ensure project root is on sys.path so `import myproject` works when running this script
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()
from django.conf import settings
from myapp.models import Post

qs = Post.objects.filter(media__isnull=False).exclude(media__exact='')[:500]
if not qs:
    print('No posts with media found.')
for p in qs:
    name = (p.media.name or '')
    try:
        url_prop = p.media_url
    except Exception as e:
        url_prop = f'ERROR:{e}'
    try:
        exists = p.media.storage.exists(name) if name else False
    except Exception as e:
        exists = f'ERROR:{e}'
    fs_path = os.path.join(settings.MEDIA_ROOT, name.lstrip('/')) if name else ''
    fs_exists = os.path.exists(fs_path) if fs_path else False
    print(f"ID:{p.id} name={repr(name)} media_url={url_prop!r} storage_exists={exists} fs_path={fs_path!r} fs_exists={fs_exists}")
