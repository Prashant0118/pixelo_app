import os, sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()
from myapp.models import Post, Story, Message

def search(substr):
    q_posts = Post.objects.filter(media__icontains=substr)
    q_stories = Story.objects.filter(image__icontains=substr)
    q_msgs = Message.objects.filter(media__icontains=substr)
    print(f"Searching for {substr!r}")
    print('Posts:', q_posts.count())
    for p in q_posts[:20]:
        print(' Post id', p.id, 'name=', repr(getattr(p.media, 'name', '')))
    print('Stories:', q_stories.count())
    for s in q_stories[:20]:
        print(' Story id', s.id, 'name=', repr(getattr(s.image, 'name', '')))
    print('Messages:', q_msgs.count())
    for m in q_msgs[:20]:
        print(' Msg id', m.id, 'name=', repr(getattr(m.media, 'name', '')))

if __name__ == '__main__':
    for term in ('Pixelo_app_logo_design_ykgcws', 'ankur-warikoo_rlt46s'):
        search(term)
