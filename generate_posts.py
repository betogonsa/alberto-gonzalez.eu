#!/usr/bin/env python3
"""
Fetches the Substack RSS feed and generates individual HTML article pages.
Run manually or via GitHub Actions (see .github/workflows/generate-posts.yml).
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
        .article-header {{
            padding-top: 20px;
            margin-bottom: 32px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 24px;
        }}
        .article-header h1 {{
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 8px;
        }}
        .article-date {{
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.85rem;
            color: var(--text-light);
        }}
        .article-body {{
            font-size: 0.95rem;
            line-height: 1.9;
            color: var(--text);
        }}
        .article-body p {{
            margin-bottom: 16px;
        }}
        .article-body h2, .article-body h3, .article-body h4 {{
            font-family: 'Lora', serif;
            margin-top: 32px;
            margin-bottom: 12px;
        }}
        .article-body h2 {{ font-size: 1.3rem; }}
        .article-body h3 {{ font-size: 1.15rem; }}
        .article-body img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 16px 0;
        }}
        .article-body blockquote {{
            border-left: 3px solid var(--accent);
            padding-left: 16px;
            margin: 16px 0;
            font-style: italic;
            color: var(--text-secondary);
        }}
        .article-body ul, .article-body ol {{
            margin: 12px 0;
            padding-left: 24px;
        }}
        .article-body li {{
            margin-bottom: 6px;
        }}
        .article-body a {{
            color: var(--accent);
        }}
        .article-footer {{
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}
        .article-footer a {{
            font-weight: 600;
        }}
        .article-body .subscription-widget-wrap-editor,
        .article-body .subscription-widget,
        .article-body .button-wrapper,
        .article-body .captioned-button-wrap {{
            display: none;
        }}
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
                <p style="margin-top: 12px;">
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
    """Convert a title to a URL-friendly slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]


def clean_content(html_content):
    """Clean up Substack HTML content for display on our site."""
    if not html_content:
        return ""
    
    # Remove Substack subscription widgets
    html_content = re.sub(
        r'<div class="subscription-widget-wrap-editor".*?</div>\s*</div>\s*</div>',
        '', html_content, flags=re.DOTALL
    )
    
    # Remove Substack subscribe buttons
    html_content = re.sub(
        r'<p class="button-wrapper".*?</p>',
        '', html_content, flags=re.DOTALL
    )
    
    # Remove captioned button wraps (share buttons etc.)
    html_content = re.sub(
        r'<div class="captioned-button-wrap".*?</div>\s*</div>',
        '', html_content, flags=re.DOTALL
    )
    
    return html_content


def extract_description(html_content, max_length=160):
    """Extract a plain text description from HTML content."""
    text = re.sub(r'<[^>]+>', '', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    return text


def extract_keywords(title):
    """Extract simple keywords from the title."""
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'is', 'it', 'its', 'are', 'was', 'were', 'be',
                  'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that',
                  'these', 'those', 'i', 'my', 'me', 'we', 'our', 'you', 'your',
                  'not', 'no', 'how', 'what', 'where', 'when', 'why', 'which', 'who'}
    words = re.findall(r'\b\w+\b', title.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    return ', '.join(keywords[:8])


def main():
    print(f"Fetching RSS feed from {FEED_URL}...")
    
    # Substack blocks many automated requests. Use a full browser user agent.
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    req = urllib.request.Request(FEED_URL, headers=headers)
    
    feed_content = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                feed_content = response.read()
            print(f"Fetched {len(feed_content)} bytes from RSS feed.")
            break
        except urllib.error.HTTPError as e:
            print(f"Attempt {attempt + 1}: HTTP Error {e.code}: {e.reason}")
            if attempt < 2:
                import time
                time.sleep(5)
        except Exception as e:
            print(f"Attempt {attempt + 1}: Error: {e}")
            if attempt < 2:
                import time
                time.sleep(5)
    
    if not feed_content:
        print("Could not fetch feed after 3 attempts. Trying rss2json fallback...")
        try:
            fallback_url = f"https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(FEED_URL, safe='')}"
            req2 = urllib.request.Request(fallback_url, headers=headers)
            with urllib.request.urlopen(req2, timeout=30) as response:
                import json
                data = json.loads(response.read())
            
            if data.get('status') == 'ok' and data.get('items'):
                print(f"Fallback succeeded. Got {len(data['items'])} items from rss2json.")
                # Convert rss2json format to generate pages
                os.makedirs(POSTS_DIR, exist_ok=True)
                generated = 0
                posts_index = []
                
                for item in data['items']:
                    title = item.get('title', 'Untitled')
                    slug = slugify(title)
                    filepath = os.path.join(POSTS_DIR, f"{slug}.html")
                    
                    content = clean_content(item.get('content', item.get('description', '')))
                    description = extract_description(item.get('description', ''), max_length=160)
                    keywords = extract_keywords(title)
                    substack_url = item.get('link', 'https://albertogonzalezsanchez.substack.com/')
                    
                    pub_date = item.get('pubDate', '')
                    if pub_date:
                        try:
                            date_obj = datetime.strptime(pub_date[:10], '%Y-%m-%d')
                            date_str = date_obj.strftime('%B %d, %Y')
                        except:
                            date_obj = datetime.now()
                            date_str = ''
                    else:
                        date_obj = datetime.now()
                        date_str = ''
                    
                    page_html = TEMPLATE.format(
                        title=title.replace('{', '{{').replace('}', '}}'),
                        description=description.replace('"', '&quot;'),
                        slug=slug,
                        keywords=keywords,
                        date=date_str,
                        year=date_obj.year,
                        substack_url=substack_url,
                        content=content
                    )
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(page_html)
                    
                    print(f"  Generated: {filepath}")
                    generated += 1
                    
                    date_iso = ''
                    if pub_date:
                        date_iso = pub_date[:10]
                    posts_index.append({
                        'title': title,
                        'slug': slug,
                        'date': date_iso,
                        'url': f"posts/{slug}.html"
                    })
                
                with open('posts_index.js', 'w', encoding='utf-8') as f:
                    f.write(f"const POSTS_INDEX = {json.dumps(posts_index, ensure_ascii=False, indent=2)};")
                
                print(f"\nDone! Generated {generated} article pages via rss2json fallback.")
                return
            else:
                print("rss2json fallback also failed.")
                return
        except Exception as e:
            print(f"rss2json fallback error: {e}")
            return
    
    feed = feedparser.parse(feed_content)
    
    if not feed.entries:
        print("No entries found in parsed feed.")
        print(f"Feed bozo: {feed.bozo}")
        if feed.bozo_exception:
            print(f"Feed error: {feed.bozo_exception}")
        return
    
    print(f"Found {len(feed.entries)} articles.")
    
    # Create posts directory
    os.makedirs(POSTS_DIR, exist_ok=True)
    
    generated = 0
    for entry in feed.entries:
        title = entry.get('title', 'Untitled')
        slug = slugify(title)
        filepath = os.path.join(POSTS_DIR, f"{slug}.html")
        
        # Get content
        content = ''
        if 'content' in entry and entry.content:
            content = entry.content[0].get('value', '')
        elif 'summary' in entry:
            content = entry.summary
        
        content = clean_content(content)
        
        # Get date
        pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
        if pub_date:
            date_obj = datetime(pub_date.tm_year, pub_date.tm_mon, pub_date.tm_mday)
            date_str = date_obj.strftime('%B %d, %Y')
        else:
            date_str = ''
            date_obj = datetime.now()
        
        # Get description
        description = extract_description(
            entry.get('summary', content), max_length=160
        )
        
        # Get keywords
        keywords = extract_keywords(title)
        
        # Substack URL
        substack_url = entry.get('link', 'https://albertogonzalezsanchez.substack.com/')
        
        # Escape curly braces in content for format string
        # We use a different approach: replace placeholders manually
        page_html = TEMPLATE.format(
            title=title.replace('{', '{{').replace('}', '}}'),
            description=description.replace('"', '&quot;'),
            slug=slug,
            keywords=keywords,
            date=date_str,
            year=date_obj.year,
            substack_url=substack_url,
            content=content
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(page_html)
        
        print(f"  Generated: {filepath}")
        generated += 1
    
    print(f"\nDone! Generated {generated} article pages in '{POSTS_DIR}/' directory.")
    
    # Build post data for static injection
    posts_data = []
    for entry in feed.entries:
        title = entry.get('title', 'Untitled')
        slug = slugify(title)
        pub_date = entry.get('published_parsed')
        date_str = ''
        date_long = ''
        if pub_date:
            date_obj2 = datetime(pub_date.tm_year, pub_date.tm_mon, pub_date.tm_mday)
            date_str = f"{pub_date.tm_year}-{pub_date.tm_mon:02d}-{pub_date.tm_mday:02d}"
            date_long = date_obj2.strftime('%B %Y')
        
        desc = ''
        if 'summary' in entry:
            desc = extract_description(entry.summary, max_length=150)
        
        posts_data.append({
            'title': title,
            'slug': slug,
            'date': date_str,
            'date_long': date_long,
            'excerpt': desc,
            'url': f"posts/{slug}.html"
        })
    
    # Generate posts_index.js (keep as backup for JS)
    posts_index = [{'title': p['title'], 'slug': p['slug'], 'date': p['date'], 'url': p['url']} for p in posts_data]
    with open('posts_index.js', 'w', encoding='utf-8') as f:
        f.write(f"const POSTS_INDEX = {json.dumps(posts_index, ensure_ascii=False, indent=2)};")
    print("Generated posts_index.js")
    
    # ---- INJECT STATIC HTML INTO INDEX.HTML (Recent publications) ----
    recent_html_items = []
    for post in posts_data[:5]:
        date_part = f' <span style="font-weight:400;color:#888;">({post["date_long"]})</span>' if post['date_long'] else ''
        excerpt_part = f'\n                        <span class="post-excerpt">{post["excerpt"]}…</span>' if post['excerpt'] else ''
        recent_html_items.append(f'''                    <li>
                        <a href="{post['url']}">
                            <span class="post-title">{post['title']}{date_part}</span>{excerpt_part}
                        </a>
                    </li>''')
    
    recent_html = '\n'.join(recent_html_items)
    
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f:
            index_content = f.read()
        
        # Replace the placeholder list with static content
        import re as re2
        # Match the ul with id="recent-posts" and replace its contents
        pattern = r'(<ul id="recent-posts" class="recent-list">).*?(</ul>)'
        replacement = f'\\1\n{recent_html}\n                \\2'
        new_index = re2.sub(pattern, replacement, index_content, flags=re.DOTALL)
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(new_index)
        print("Injected static recent publications into index.html")
    
    # ---- INJECT STATIC HTML INTO WRITING.HTML (All posts) ----
    writing_html_items = []
    for post in posts_data:
        date_part = f' <span style="font-weight:400;color:#888;">({post["date_long"]})</span>' if post['date_long'] else ''
        excerpt_part = f'\n                        <span class="post-excerpt">{post["excerpt"]}…</span>' if post['excerpt'] else ''
        writing_html_items.append(f'''                    <li>
                        <a href="{post['url']}">
                            <span class="post-title">{post['title']}{date_part}</span>{excerpt_part}
                        </a>
                    </li>''')
    
    writing_html = '\n'.join(writing_html_items)
    
    if os.path.exists('writing.html'):
        with open('writing.html', 'r', encoding='utf-8') as f:
            writing_content = f.read()
        
        pattern = r'(<ul id="all-posts" class="recent-list">).*?(</ul>)'
        replacement = f'\\1\n{writing_html}\n            \\2'
        new_writing = re2.sub(pattern, replacement, writing_content, flags=re.DOTALL)
        
        with open('writing.html', 'w', encoding='utf-8') as f:
            f.write(new_writing)
        print("Injected static post archive into writing.html")


if __name__ == '__main__':
    main()
