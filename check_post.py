import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','myproject.settings')
import django
django.setup()
from django.contrib.auth.models import User
from myapp.models import Post
u = User.objects.filter(username='test_long_video').first()
if not u:
    print('No user')
else:
    qs = Post.objects.filter(user=u).order_by('-id')
    print('User:', u.username)
    print('Posts count:', qs.count())
    for p in qs[:5]:
        print('id=', p.id, 'type=', p.type, 'media=', getattr(p.media, 'name', ''))
