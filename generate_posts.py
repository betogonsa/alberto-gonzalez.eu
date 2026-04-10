#!/usr/bin/env python3
"""
Fetches the Substack RSS feed and generates individual HTML article pages.
PRESERVES existing posts - only adds new ones, never deletes old ones.
Uses posts_registry.json as persistent memory of all posts.

To manually add a post:
1. Create the HTML file in the posts/ folder
2. Add an entry to posts_registry.json with: title, slug, date, date_long, excerpt, url, substack_url
3. Commit and push

To edit a post:
1. Edit the HTML file directly in posts/
2. Update the entry in posts_registry.json if needed
3. Commit and push
"""

import feedparser
import os
import re
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

FEED_URL = "https://albertogonzalezsanchez.substack.com/feed"
POSTS_DIR = "posts"
REGISTRY_FILE = "posts_registry.json"

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Alberto González Sánchez</title>
    <meta name="description" content="{description}">
    <meta name="author" content="Alberto González Sánchez">
    <meta name="keywords" content="Alberto González Sánchez, EIB, European Investment Bank, transport, {keywords}">
    <meta property="og:type" content="article">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:url" content="https://alberto-gonzalez.eu/posts/{slug}.html">
    <link rel="canonical" href="https://alberto-gonzalez.eu/posts/{slug}.html">
    <link rel="icon" type="image/jpeg" href="../picture_linkedin.jpg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="../style.css">
    <style>
        .article-header {{ padding-top:20px; margin-bottom:32px; border-bottom:1px solid var(--border); padding-bottom:24px; }}
        .article-header h1 {{ font-size:1.8rem; font-weight:700; line-height:1.3; margin-bottom:8px; }}
        .article-date {{ font-family:'Source Sans 3',sans-serif; font-size:0.85rem; color:var(--text-light); }}
        .article-body {{ font-size:0.95rem; line-height:1.9; color:var(--text); }}
        .article-body p {{ margin-bottom:16px; }}
        .article-body h2,.article-body h3,.article-body h4 {{ font-family:'Lora',serif; margin-top:32px; margin-bottom:12px; }}
        .article-body h2 {{ font-size:1.3rem; }} .article-body h3 {{ font-size:1.15rem; }}
        .article-body img {{ max-width:100%; height:auto; border-radius:8px; margin:16px 0; }}
        .article-body blockquote {{ border-left:3px solid var(--accent); padding-left:16px; margin:16px 0; font-style:italic; color:var(--text-secondary); }}
        .article-body ul,.article-body ol {{ margin:12px 0; padding-left:24px; }}
        .article-body li {{ margin-bottom:6px; }}
        .article-body a {{ color:var(--accent); }}
        .article-footer {{ margin-top:48px; padding-top:24px; border-top:1px solid var(--border); font-family:'Source Sans 3',sans-serif; font-size:0.9rem; color:var(--text-secondary); }}
        .article-footer a {{ font-weight:600; }}
        .article-body .subscription-widget-wrap-editor,.article-body .subscription-widget,.article-body .button-wrapper,.article-body .captioned-button-wrap {{ display:none; }}
    </style>
</head>
<body>
    <nav>
        <div class="nav-inner">
            <a href="../index.html" class="nav-name">Alberto González Sánchez</a>
            <ul class="nav-links">
                <li><a href="../index.html">Home</a></li>
                <li><a href="../writing.html" class="active">Writing</a></li>
                <li><a href="../contact.html">Contact</a></li>
            </ul>
        </div>
    </nav>
    <div class="container">
        <div class="page-content">
            <div class="article-header">
                <h1>{title}</h1>
                <p class="article-date">{date} · Originally published on <a href="{substack_url}" target="_blank" rel="noopener"><em>The mobility climate</em></a></p>
            </div>
            <div class="article-body">
                {content}
            </div>
            <div class="article-footer">
                <p>This article was originally published on <a href="{substack_url}" target="_blank" rel="noopener">The mobility climate</a> on Substack.</p>
                <p style="margin-top:12px;">
                    <a href="../writing.html">← All articles</a> · 
                    <a href="../index.html">Home</a>
                </p>
            </div>
        </div>
        <footer>
            All views expressed on this site and in my newsletter are personal and do not represent the positions of the European Investment Bank.
            <br>© {year} Alberto González Sánchez
        </footer>
    </div>
</body>
</html>"""


def slugify(title):
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]


def clean_content(html_content):
    if not html_content:
        return ""
    html_content = re.sub(r'<div class="subscription-widget-wrap-editor".*?</div>\s*</div>\s*</div>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<p class="button-wrapper".*?</p>', '', html_content, flags=re.DOTALL)
    html_content = re.sub(r'<div class="captioned-button-wrap".*?</div>\s*</div>', '', html_content, flags=re.DOTALL)
    return html_content


def extract_description(html_content, max_length=160):
    text = re.sub(r'<[^>]+>', '', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    return text


def extract_keywords(title):
    stop_words = {'the','a','an','and','or','but','in','on','at','to','for','of','with','by','is','it','its','are','was','were','be','been','being','have','has','had','do','does','did','will','would','could','should','may','might','can','this','that','these','those','i','my','me','we','our','you','your','not','no','how','what','where','when','why','which','who'}
    words = re.findall(r'\b\w+\b', title.lower())
    return ', '.join([w for w in words if w not in stop_words and len(w) > 2][:8])


def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_registry(registry):
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def registry_has_slug(registry, slug):
    return any(p['slug'] == slug for p in registry)


def fetch_feed_items():
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Try direct RSS
    req = urllib.request.Request(FEED_URL, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                feed_content = response.read()
            print(f"Fetched {len(feed_content)} bytes from RSS feed.")
            feed = feedparser.parse(feed_content)
            if feed.entries:
                items = []
                for entry in feed.entries:
                    content = ''
                    if 'content' in entry and entry.content:
                        content = entry.content[0].get('value', '')
                    elif 'summary' in entry:
                        content = entry.summary
                    pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
                    date_iso, date_long, date_str, year = '', '', '', datetime.now().year
                    if pub_date:
                        d = datetime(pub_date.tm_year, pub_date.tm_mon, pub_date.tm_mday)
                        date_iso = d.strftime('%Y-%m-%d')
                        date_long = d.strftime('%B %Y')
                        date_str = d.strftime('%B %d, %Y')
                        year = d.year
                    items.append({
                        'title': entry.get('title', 'Untitled'), 'content': content,
                        'description': entry.get('summary', ''), 'link': entry.get('link', ''),
                        'date_iso': date_iso, 'date_long': date_long, 'date_str': date_str, 'year': year,
                    })
                return items
        except urllib.error.HTTPError as e:
            print(f"Attempt {attempt+1}: HTTP Error {e.code}: {e.reason}")
            if attempt < 2:
                import time; time.sleep(5)
        except Exception as e:
            print(f"Attempt {attempt+1}: Error: {e}")
            if attempt < 2:
                import time; time.sleep(5)

    # Fallback: rss2json
    print("Trying rss2json fallback...")
    try:
        fallback_url = f"https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(FEED_URL, safe='')}"
        req2 = urllib.request.Request(fallback_url, headers=headers)
        with urllib.request.urlopen(req2, timeout=30) as response:
            data = json.loads(response.read())
        if data.get('status') == 'ok' and data.get('items'):
            print(f"Fallback succeeded. Got {len(data['items'])} items.")
            items = []
            for item in data['items']:
                pub_date = item.get('pubDate', '')
                date_iso, date_long, date_str, year = '', '', '', datetime.now().year
                if pub_date:
                    try:
                        d = datetime.strptime(pub_date[:10], '%Y-%m-%d')
                        date_iso, date_long, date_str, year = pub_date[:10], d.strftime('%B %Y'), d.strftime('%B %d, %Y'), d.year
                    except: pass
                items.append({
                    'title': item.get('title', 'Untitled'),
                    'content': item.get('content', item.get('description', '')),
                    'description': item.get('description', ''),
                    'link': item.get('link', ''),
                    'date_iso': date_iso, 'date_long': date_long, 'date_str': date_str, 'year': year,
                })
            return items
    except Exception as e:
        print(f"rss2json fallback error: {e}")
    return []


def generate_article_page(item, slug):
    content = clean_content(item['content'])
    description = extract_description(item.get('description', content), max_length=160)
    keywords = extract_keywords(item['title'])
    substack_url = item.get('link', 'https://albertogonzalezsanchez.substack.com/')
    page_html = TEMPLATE.format(
        title=item['title'].replace('{', '{{').replace('}', '}}'),
        description=description.replace('"', '&quot;'), slug=slug, keywords=keywords,
        date=item.get('date_str', ''), year=item.get('year', datetime.now().year),
        substack_url=substack_url, content=content
    )
    filepath = os.path.join(POSTS_DIR, f"{slug}.html")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(page_html)
    return filepath


def inject_static_html(posts_data):
    # Index.html - recent 5
    recent_items = []
    for post in posts_data[:5]:
        date_part = f' <span style="font-weight:400;color:#888;">({post["date_long"]})</span>' if post.get('date_long') else ''
        excerpt_part = f'\n                        <span class="post-excerpt">{post["excerpt"]}…</span>' if post.get('excerpt') else ''
        recent_items.append(f'''                    <li>
                        <a href="{post['url']}">
                            <span class="post-title">{post['title']}{date_part}</span>{excerpt_part}
                        </a>
                    </li>''')
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = r'(<ul id="recent-posts" class="recent-list">).*?(</ul>)'
        replacement = f'\\1\n' + '\n'.join(recent_items) + '\n                \\2'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Injected recent publications into index.html")

    # Writing.html - all posts
    all_items = []
    for post in posts_data:
        date_part = f' <span style="font-weight:400;color:#888;">({post["date_long"]})</span>' if post.get('date_long') else ''
        excerpt_part = f'\n                        <span class="post-excerpt">{post["excerpt"]}…</span>' if post.get('excerpt') else ''
        all_items.append(f'''                    <li>
                        <a href="{post['url']}">
                            <span class="post-title">{post['title']}{date_part}</span>{excerpt_part}
                        </a>
                    </li>''')
    if os.path.exists('writing.html'):
        with open('writing.html', 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = r'(<ul id="all-posts" class="recent-list">).*?(</ul>)'
        replacement = f'\\1\n' + '\n'.join(all_items) + '\n            \\2'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        with open('writing.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Injected all posts into writing.html")


def generate_sitemap(posts_data):
    today = datetime.now().strftime('%Y-%m-%d')
    urls = [
        {'loc': 'https://alberto-gonzalez.eu/', 'priority': '1.0', 'changefreq': 'weekly', 'lastmod': today},
        {'loc': 'https://alberto-gonzalez.eu/writing.html', 'priority': '0.8', 'changefreq': 'weekly', 'lastmod': today},
        {'loc': 'https://alberto-gonzalez.eu/contact.html', 'priority': '0.5', 'changefreq': 'monthly', 'lastmod': today},
    ]
    for post in posts_data:
        urls.append({
            'loc': f"https://alberto-gonzalez.eu/{post['url']}",
            'priority': '0.7', 'changefreq': 'monthly',
            'lastmod': post.get('date', today) or today,
        })
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f'  <url>\n    <loc>{u["loc"]}</loc>\n    <lastmod>{u["lastmod"]}</lastmod>\n    <changefreq>{u["changefreq"]}</changefreq>\n    <priority>{u["priority"]}</priority>\n  </url>')
    xml.append('</urlset>')
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml))
    with open('robots.txt', 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nAllow: /\n\nSitemap: https://alberto-gonzalez.eu/sitemap.xml\n')
    print(f"Generated sitemap.xml with {len(urls)} URLs")


def main():
    print("=" * 60)
    print("Substack Article Page Generator (with Registry)")
    print("=" * 60)

    # 1. Load existing registry
    registry = load_registry()
    print(f"Registry: {len(registry)} existing posts.")

    # 2. Fetch new items from RSS
    items = fetch_feed_items()

    if not items:
        print("No items fetched. Using existing registry only.")
    else:
        os.makedirs(POSTS_DIR, exist_ok=True)
        new_count = 0
        for item in items:
            slug = slugify(item['title'])
            if not registry_has_slug(registry, slug):
                filepath = generate_article_page(item, slug)
                print(f"  NEW: {filepath}")
                registry.append({
                    'title': item['title'], 'slug': slug,
                    'date': item.get('date_iso', ''), 'date_long': item.get('date_long', ''),
                    'excerpt': extract_description(item.get('description', ''), max_length=150),
                    'url': f"posts/{slug}.html", 'substack_url': item.get('link', ''),
                })
                new_count += 1
            else:
                filepath = generate_article_page(item, slug)
                print(f"  Updated: {filepath}")
        print(f"\n{new_count} new, {len(registry)} total.")

    # 3. Sort by date (newest first)
    registry.sort(key=lambda p: p.get('date', ''), reverse=True)

    # 4. Save registry
    save_registry(registry)

    # 5. Build posts_data from registry
    posts_data = [{
        'title': p['title'], 'slug': p['slug'], 'date': p.get('date', ''),
        'date_long': p.get('date_long', ''), 'excerpt': p.get('excerpt', ''), 'url': p['url'],
    } for p in registry]

    # 6. Generate index files
    posts_index = [{'title': p['title'], 'slug': p['slug'], 'date': p['date'], 'url': p['url']} for p in posts_data]
    with open('posts_index.js', 'w', encoding='utf-8') as f:
        f.write(f"const POSTS_INDEX = {json.dumps(posts_index, ensure_ascii=False, indent=2)};")

    # 7. Inject static HTML
    inject_static_html(posts_data)

    # 8. Generate sitemap
    generate_sitemap(posts_data)

    print(f"\nDone! {len(posts_data)} total articles on site.")


if __name__ == '__main__':
    main()
