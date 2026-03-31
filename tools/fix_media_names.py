import os
import sys

# ensure project root is on sys.path so `import myproject` works
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()

from django.conf import settings
from myapp.models import Post, Story, Message

def fix_queryset(qs, model_name):
    changed = 0
    for obj in qs:
        name = (getattr(obj.media, 'name', None) or '').strip()
        if not name:
            continue
        try:
            storage_exists = obj.media.storage.exists(name)
        except Exception:
            storage_exists = False

        fs_path = os.path.join(settings.MEDIA_ROOT, name.lstrip('/'))
        fs_exists = os.path.exists(fs_path)

        if storage_exists:
            continue

        if fs_exists:
            # try common corrections
            candidates = [name.lstrip('/'), name.lstrip('/media/'), os.path.basename(name)]
            fixed = False
            for cand in candidates:
                if not cand:
                    continue
                try:
                    if obj.media.storage.exists(cand):
                        obj.media.name = cand
                        obj.save(update_fields=['media'])
                        print(f"Fixed {model_name} id={obj.id}: {name!r} -> {cand!r}")
                        changed += 1
                        fixed = True
                        break
                except Exception:
                    continue
            if not fixed:
                print(f"Unfixed {model_name} id={obj.id}: storage missing but fs exists at {fs_path!r}")
        else:
            if name.startswith(('http://', 'https://')):
                print(f"Remote URL (left alone) {model_name} id={obj.id}: {name}")
            else:
                print(f"Missing file for {model_name} id={obj.id}: {name!r}")

    return changed

def main():
    print('Scanning Posts...')
    posts_qs = Post.objects.filter(media__isnull=False).exclude(media__exact='')
    changed_posts = fix_queryset(posts_qs, 'Post')

    print('Scanning Stories...')
    stories_qs = Story.objects.filter(image__isnull=False).exclude(image__exact='')
    changed_stories = fix_queryset(stories_qs, 'Story')

    print('Scanning Messages...')
    msgs_qs = Message.objects.filter(media__isnull=False).exclude(media__exact='')
    changed_msgs = fix_queryset(msgs_qs, 'Message')

    print(f"Done. Changes made: posts={changed_posts}, stories={changed_stories}, messages={changed_msgs}")

if __name__ == '__main__':
    main()
