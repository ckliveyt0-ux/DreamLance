from flask import Flask, request, jsonify, send_from_directory, abort, Response
import os
import sqlite3
from sqlite3 import Connection
from datetime import datetime
import json
import smtplib
import requests
from email.message import EmailMessage
from functools import wraps
import time

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(APP_ROOT, 'data.db')

app = Flask(__name__, static_folder='.', static_url_path='')

# Jobs cache
_jobs_cache = { 'items': [], 'fetched_at': None }

# News cache
_news_cache = { 'items': [], 'fetched_at': None }

# Load .env file manually if it exists
env_path = os.path.join(APP_ROOT, '.env')
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
    except Exception as e:
        print(f"Warning: Could not read .env file: {e}")

# Configuration via environment variables
ADMIN_USER = os.environ.get('ADMIN_USER', 'Kiran1598')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'Kiran@1598')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'dreamlance246@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'dreamlance246@gmail.com')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

def get_db() -> Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            interest TEXT,
            message TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'pending',
            estimate_cost INTEGER,
            estimate_timeline INTEGER,
            admin_note TEXT
        )
    ''')
    conn.commit()
    conn.close()

ensure_db()

# Auth decorator for admin routes (supporting both Basic and Bearer auth)
def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # 1. Try standard request.authorization (Basic)
        auth = request.authorization
        if auth and auth.username == ADMIN_USER and auth.password == ADMIN_PASS:
            return fn(*args, **kwargs)
        
        # 2. Try Bearer token manually
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.lower().startswith('bearer '):
            try:
                token = auth_header.split(' ', 1)[1]
                import base64
                decoded = base64.b64decode(token).decode('utf-8')
                username, password = decoded.split(':', 1)
                if username == ADMIN_USER and password == ADMIN_PASS:
                    return fn(*args, **kwargs)
            except Exception:
                pass
                
        # Return a 401 without WWW-Authenticate header so browsers don't show prompt
        return Response('Unauthorized', 401)
    return wrapper

# Email sending helper (SendGrid or SMTP)
def send_email(to_email, subject, body):
    if SENDGRID_API_KEY:
        # Use SendGrid API
        url = 'https://api.sendgrid.com/v3/mail/send'
        headers = {
            'Authorization': f'Bearer {SENDGRID_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'personalizations': [{ 'to': [{ 'email': to_email }] }],
            'from': { 'email': FROM_EMAIL },
            'subject': subject,
            'content': [{ 'type': 'text/plain', 'value': body }]
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            return r.status_code in (200,202)
        except Exception:
            return False
    elif SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = FROM_EMAIL
            msg['To'] = to_email
            msg.set_content(body)
            if SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
            else:
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT or 587, timeout=10)
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"[!] SMTP Error sending email to {to_email}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # No email backend configured; log to file for now
        try:
            with open(os.path.join(APP_ROOT, 'email.log'), 'a', encoding='utf-8') as f:
                f.write(f"From: {FROM_EMAIL}\nTo: {to_email}\nSubject: {subject}\n{body}\n\n---\n")
            return True
        except Exception as e:
            print(f"[!] Log-to-file error: {str(e)}")
            return False

@app.route('/')
def index():
    return send_from_directory(APP_ROOT, 'index.html')

@app.route('/api/requests', methods=['POST'])
def api_requests():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'invalid payload'}), 400

    name = data.get('name')
    email = data.get('email')
    interest = data.get('interest')
    message = data.get('message')

    # Basic validation
    if not email or '@' not in email:
        return jsonify({'error': 'invalid email'}), 400
    if not interest or interest not in ('jobs','projects','startup'):
        return jsonify({'error': 'invalid interest'}), 400

    conn = get_db()
    c = conn.cursor()
    created = datetime.utcnow().isoformat() + 'Z'
    c.execute('''INSERT INTO requests (name,email,interest,message,created_at,status) VALUES (?,?,?,?,?,?)''',
              (name,email,interest,message,created,'pending'))
    conn.commit()
    rid = c.lastrowid
    row = c.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
    conn.close()

    item = dict(row)
    return jsonify({'status':'ok','item':item}), 201

@app.route('/api/jobs', methods=['GET'])
def api_jobs():
    # Simple caching for 5 minutes
    now = time.time()
    if _jobs_cache.get('fetched_at') and now - _jobs_cache['fetched_at'] < 300 and _jobs_cache.get('items'):
        return jsonify({'jobs': _jobs_cache['items']})
    job_api_key = '7abf95bac1a148da807549888f7e5daf'
    items = []
    try:
        headers = {
            'X-RapidAPI-Key': job_api_key,
            'X-RapidAPI-Host': 'jsearch.p.rapidapi.com'
        }
        r = requests.get(
            'https://jsearch.p.rapidapi.com/search',
            headers=headers,
            params={
                'query': 'latest hiring jobs software developer remote internship',
                'num_pages': '1',
                'page': '1'
            },
            timeout=10
        )
        data = r.json()
        for j in data.get('data', [])[:12]:
            url = j.get('job_apply_link') or j.get('job_post_url') or j.get('redirect_url') or j.get('url')
            items.append({
                'id': j.get('job_id') or j.get('id'),
                'title': j.get('job_title') or j.get('title'),
                'company': j.get('employer_name') or j.get('company_name') or 'Hiring Company',
                'category': j.get('job_employment_type') or j.get('job_category') or 'Job',
                'url': url,
                'type': j.get('job_employment_type') or j.get('job_type') or 'Full-time',
                'location': j.get('job_city') or j.get('job_country') or j.get('candidate_required_location') or 'Remote'
            })
        if not items:
            raise ValueError('Empty job results')
    except Exception:
        # fallback to Remotive if RapidAPI job search fails
        try:
            r = requests.get('https://remotive.io/api/remote-jobs', timeout=8)
            data = r.json()
            jobs = data.get('jobs', [])[:12]
            for j in jobs:
                items.append({
                    'id': j.get('id'),
                    'title': j.get('title'),
                    'company': j.get('company_name'),
                    'category': j.get('category'),
                    'url': j.get('url'),
                    'type': j.get('job_type'),
                    'location': j.get('candidate_required_location')
                })
        except Exception:
            items = []
            
    # Ultimate fallback jobs if both APIs fail or return empty results
    if not items:
        items = [
            {
                'id': 'fb-1',
                'title': 'Frontend Developer (React)',
                'company': 'Stripe',
                'category': 'software-development',
                'url': 'https://stripe.com/jobs',
                'type': 'Full-time',
                'location': 'Remote, US'
            },
            {
                'id': 'fb-2',
                'title': 'Junior Full-Stack Engineer',
                'company': 'Vercel',
                'category': 'software-development',
                'url': 'https://vercel.com/careers',
                'type': 'Full-time',
                'location': 'Remote, Worldwide'
            },
            {
                'id': 'fb-3',
                'title': 'AI Systems Engineering Intern',
                'company': 'OpenAI',
                'category': 'internship',
                'url': 'https://openai.com/careers',
                'type': 'Internship',
                'location': 'San Francisco, CA'
            },
            {
                'id': 'fb-4',
                'title': 'Data Platform Engineer',
                'company': 'Netflix',
                'category': 'software-development',
                'url': 'https://jobs.netflix.com',
                'type': 'Full-time',
                'location': 'Los Gatos, CA'
            },
            {
                'id': 'fb-5',
                'title': 'Associate Product Designer',
                'company': 'Airbnb',
                'category': 'design',
                'url': 'https://careers.airbnb.com',
                'type': 'Full-time',
                'location': 'Remote'
            },
            {
                'id': 'fb-6',
                'title': 'Backend Developer (Go/Python)',
                'company': 'Supabase',
                'category': 'software-development',
                'url': 'https://supabase.com/careers',
                'type': 'Full-time',
                'location': 'Remote, Europe'
            },
            {
                'id': 'fb-7',
                'title': 'Software Engineering Intern',
                'company': 'Google',
                'category': 'internship',
                'url': 'https://careers.google.com',
                'type': 'Internship',
                'location': 'Mountain View, CA'
            },
            {
                'id': 'fb-8',
                'title': 'iOS Development Intern',
                'company': 'Apple',
                'category': 'internship',
                'url': 'https://www.apple.com/careers',
                'type': 'Internship',
                'location': 'Cupertino, CA'
            }
        ]
    _jobs_cache['items'] = items
    _jobs_cache['fetched_at'] = now
    return jsonify({'jobs': items})

@app.route('/api/news', methods=['GET'])
def api_news():
    now = time.time()
    if _news_cache.get('fetched_at') and now - _news_cache['fetched_at'] < 600 and _news_cache.get('items'):
        return jsonify({'news': _news_cache['items']})
    
    items = []
    # Try RapidAPI news search for tech hiring updates
    api_key = '7abf95bac1a148da807549888f7e5daf'
    try:
        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'newscatcher.p.rapidapi.com'
        }
        r = requests.get(
            'https://newscatcher.p.rapidapi.com/v1/search',
            headers=headers,
            params={
                'q': 'hiring tech jobs startup recruitment employment career',
                'lang': 'en',
                'page_size': '15',
                'sort_by': 'date'
            },
            timeout=10
        )
        data = r.json()
        for article in data.get('articles', []):
            category = 'tech'
            title_lower = (article.get('title') or '').lower()
            if 'startup' in title_lower or 'founder' in title_lower:
                category = 'startup'
            elif 'remote' in title_lower or 'work from home' in title_lower:
                category = 'remote'
            elif 'intern' in title_lower or 'graduate' in title_lower:
                category = 'internship'
            elif 'diversity' in title_lower or 'inclusion' in title_lower:
                category = 'diversity'

            items.append({
                'title': article.get('title'),
                'description': article.get('excerpt') or article.get('summary') or article.get('description'),
                'image': article.get('media'),
                'url': article.get('link') or article.get('url'),
                'source': article.get('clean_url') or article.get('ranked_source'),
                'publishedAt': article.get('published_date') or article.get('published_at'),
                'category': category
            })
    except Exception:
        pass
    
    # If no NewsAPI or limited results, add demo hiring news
    if len(items) < 8:
        demo_news = [
            {
                'title': 'Tech Giants Announce Record Hiring Spree in 2026',
                'description': 'Major tech companies like Google, Amazon, and Microsoft are expanding teams across AI, cloud computing, and cybersecurity roles with competitive compensation.',
                'image': 'https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=400&q=80',
                'url': 'https://techcrunch.com/category/startups/',
                'source': 'TechCrunch',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'tech'
            },
            {
                'title': 'Startups Compete for Top Talent with Generous Offers',
                'description': 'Emerging startups in AI and fintech are offering competitive salaries and equity packages to attract experienced developers and designers.',
                'image': 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=400&q=80',
                'url': 'https://venturebeat.com/category/ai/',
                'source': 'VentureBeat',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'startup'
            },
            {
                'title': 'Remote Work Opportunities Surge Across Industries',
                'description': 'Companies worldwide are opening remote positions for developers, designers, and project managers. Work-from-anywhere jobs now dominate tech hiring.',
                'image': 'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=400&q=80',
                'url': 'https://www.forbes.com/innovation/',
                'source': 'Forbes',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'remote'
            },
            {
                'title': 'Internship Programs Expand with Paid Opportunities',
                'description': 'Major corporations launch paid internships with mentorship and potential for full-time roles. Summer 2026 sees record-breaking intern hiring.',
                'image': 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=400&q=80',
                'url': 'https://www.linkedin.com/news/',
                'source': 'LinkedIn News',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'internship'
            },
            {
                'title': 'Skills Gap Closes: Coding Bootcamps Drive Employment',
                'description': 'Bootcamp graduates land high-paying roles; industry partners report strong hiring trends with average salaries exceeding $100k.',
                'image': 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=400&q=80',
                'url': 'https://www.edsurge.com/',
                'source': 'EdTech Weekly',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'tech'
            },
            {
                'title': 'Diversity Hiring Initiatives Show Positive Results',
                'description': 'Companies achieving diversity goals by investing in inclusive recruitment and mentorship programs. Women in tech hiring up 35% year-over-year.',
                'image': 'https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?auto=format&fit=crop&w=400&q=80',
                'url': 'https://www.shrm.org/',
                'source': 'HR Insider',
                'publishedAt': datetime.utcnow().isoformat() + 'Z',
                'category': 'diversity'
            }
        ]
        items.extend(demo_news[:8-len(items)])
    
    _news_cache['items'] = items[:10]
    _news_cache['fetched_at'] = now
    return jsonify({'news': _news_cache['items']})

@app.route('/projects')
def projects():
    return send_from_directory(APP_ROOT, 'projects.html')

@app.route('/api/projects-list')
def api_projects_list():
    try:
        with open(os.path.join(APP_ROOT, 'projects.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin():
    return send_from_directory(APP_ROOT, 'admin.html')

@app.route('/database')
def database():
    return send_from_directory(APP_ROOT, 'database.html')

@app.route('/api/requests/list', methods=['GET'])
@require_admin
def api_requests_list():
    conn = get_db()
    rows = conn.execute('SELECT * FROM requests ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return jsonify(items)

@app.route('/api/requests/<int:rid>/estimate', methods=['POST'])
@require_admin
def api_set_estimate(rid):
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error':'invalid payload'}), 400
    cost = data.get('cost')
    timeline = data.get('timeline')
    note = data.get('note')
    if cost is None or timeline is None:
        return jsonify({'error':'cost and timeline required'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE requests SET estimate_cost=?, estimate_timeline=?, admin_note=?, status=? WHERE id=?',
              (int(cost), int(timeline), note, 'estimated', rid))
    conn.commit()
    row = c.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error':'not found'}), 404
    item = dict(row)

    # send email notification to requester
    subject = f"Your request #{rid} — estimate from DreamLance"
    body = f"Hi {item.get('name') or ''},\n\nYour request has been reviewed. Estimated cost: ${item.get('estimate_cost')} ; timeline: {item.get('estimate_timeline')} days.\n\nNote from admin:\n{note or '—'}\n\nThanks,\nDreamLance team"
    send_email(item.get('email'), subject, body)

    return jsonify({'status':'ok','item':item})

@app.route('/api/requests/<int:rid>/preview-email', methods=['POST'])
@require_admin
def api_preview_email(rid):
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error':'invalid payload'}), 400
    cost = data.get('cost')
    timeline = data.get('timeline')
    note = data.get('note')
    
    conn = get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error':'not found'}), 404
    item = dict(row)

    subject = f"Your request #{rid} — estimate from DreamLance"
    body = f"Hi {item.get('name') or ''},\n\nYour request has been reviewed. Estimated cost: ${cost} ; timeline: {timeline} days.\n\nNote from admin:\n{note or '—'}\n\nThanks,\nDreamLance team"
    
    return jsonify({'subject': subject, 'body': body})

@app.route('/api/export-csv')
@require_admin
def api_export_csv():
    import csv
    from io import StringIO
    conn = get_db()
    rows = conn.execute('SELECT * FROM requests ORDER BY id DESC').fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Email','Service','Message','Created','Status','Estimate Cost','Estimate Timeline','Admin Note'])
    for row in rows:
        writer.writerow([
            row['id'], row['name'], row['email'], row['interest'],
            row['message'], row['created_at'], row['status'],
            row['estimate_cost'], row['estimate_timeline'], row['admin_note']
        ])
    
    csv_content = output.getvalue()
    return csv_content, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment;filename=requests.csv'
    }

if __name__ == '__main__':
    # Unified server running on port 8000 with a thread pool for request handling
    print("Starting unified DreamLance website on port 8000...")
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)
