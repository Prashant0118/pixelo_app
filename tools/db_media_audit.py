import os, sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()

from django.conf import settings
from myapp.models import Post, Story, Message, Profile

def check_field(obj, field_name, model_label, results):
    f = getattr(obj, field_name, None)
    name = getattr(f, 'name', '') or ''
    if not name:
        return
    # classify
    if name.startswith(('http://', 'https://')):
        results['remote'].append((model_label, obj.id, field_name, name))
        return
    try:
        storage_exists = f.storage.exists(name)
    except Exception:
        storage_exists = False
    fs_path = os.path.join(settings.MEDIA_ROOT, name.lstrip('/'))
    fs_exists = os.path.exists(fs_path)
    if not storage_exists:
        if fs_exists:
            results['fs_only'].append((model_label, obj.id, field_name, name, fs_path))
        else:
            results['missing'].append((model_label, obj.id, field_name, name))

def scan_all():
    results = {'missing': [], 'fs_only': [], 'remote': []}

    print('Scanning Posts...')
    for p in Post.objects.filter(media__isnull=False).exclude(media__exact=''):
        check_field(p, 'media', 'Post', results)

    print('Scanning Stories...')
    for s in Story.objects.filter(image__isnull=False).exclude(image__exact=''):
        check_field(s, 'image', 'Story', results)

    print('Scanning Messages...')
    for m in Message.objects.filter(media__isnull=False).exclude(media__exact=''):
        check_field(m, 'media', 'Message', results)

    print('Scanning Profiles...')
    for prof in Profile.objects.filter(image__isnull=False).exclude(image__exact=''):
        check_field(prof, 'image', 'Profile', results)

    return results

if __name__ == '__main__':
    res = scan_all()
    print('\nSUMMARY:')
    print('Missing (storage and fs):', len(res['missing']))
    for row in res['missing'][:50]:
        print(' ', row)
    print('\nFilesystem-only (fs exists but storage.exists False):', len(res['fs_only']))
    for row in res['fs_only'][:50]:
        print(' ', row)
    print('\nRemote URLs stored in DB (left as-is):', len(res['remote']))
    for row in res['remote'][:50]:
        print(' ', row)
