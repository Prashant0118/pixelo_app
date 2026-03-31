import requests
import time
import os
import re

URL_BASE = "http://127.0.0.1:8000"
UPLOAD_URL = f"{URL_BASE}/upload/"
REGISTER_URL = f"{URL_BASE}/register/"
LOGIN_URL = f"{URL_BASE}/login/"
TEST_FILE = "test_large_video.mp4"
SIZE_MB = 60  # 60 MB, should be larger than reel limit -> post

# Test account
TEST_USERNAME = "test_long_video"
TEST_EMAIL = "test_long_video@example.com"
TEST_PASSWORD = "Testpass123!"

# Create test file if not present
if not os.path.exists(TEST_FILE) or os.path.getsize(TEST_FILE) < SIZE_MB * 1024 * 1024:
    print(f"Creating {SIZE_MB}MB test file: {TEST_FILE}")
    with open(TEST_FILE, "wb") as f:
        f.seek(SIZE_MB * 1024 * 1024 - 1)
        f.write(b"\0")

session = requests.Session()
# wait for server
for attempt in range(40):
    try:
        r = session.get(UPLOAD_URL, timeout=5)
        if r.status_code == 200:
            print("Upload page reachable")
            page = r.text
            break
    except Exception as e:
        print("Waiting for server...", e)
    time.sleep(0.5)
else:
    print("Server not reachable")
    raise SystemExit(1)

# Ensure test user exists: register (ignore errors if already exists)
print('Ensuring test user...')
try:
    r = session.get(REGISTER_URL, timeout=5)
    page_reg = r.text
    m2 = re.search(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]", page_reg)
    csrf_reg = m2.group(1) if m2 else session.cookies.get('csrftoken','')
    reg_data = {
        'username': TEST_USERNAME,
        'email': TEST_EMAIL,
        'password1': TEST_PASSWORD,
        'password2': TEST_PASSWORD,
        'csrfmiddlewaretoken': csrf_reg,
    }
    session.post(REGISTER_URL, data=reg_data, headers={'Referer': REGISTER_URL}, timeout=10)
except Exception:
    pass

# Login
print('Logging in...')
try:
    r = session.get(LOGIN_URL, timeout=5)
    page_login = r.text
    m3 = re.search(r"name=['\"]csrfmiddlewaretoken['\"] value=['\"]([^'\"]+)['\"]", page_login)
    csrf_login = m3.group(1) if m3 else session.cookies.get('csrftoken','')
    login_data = {
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'csrfmiddlewaretoken': csrf_login,
    }
    lresp = session.post(LOGIN_URL, data=login_data, headers={'Referer': LOGIN_URL}, timeout=10)
    print('Login status:', lresp.status_code)
except Exception as e:
    print('Login failed:', e)

files = {
    'media': (TEST_FILE, open(TEST_FILE, 'rb'), 'video/mp4')
}
data = {
    'type': 'reel',
    'caption': 'Automated long-video upload test (authenticated)',
    'csrfmiddlewaretoken': session.cookies.get('csrftoken',''),
}
headers = {
    'Referer': UPLOAD_URL,
}
print('Uploading test file as authenticated user...', TEST_FILE)
resp = session.post(UPLOAD_URL, files=files, data=data, headers=headers, timeout=300)
print('Status:', resp.status_code)
print('Response length:', len(resp.text))
print('Response snippet:', resp.text[:400])

# cleanup test file (optional)
# os.remove(TEST_FILE)
