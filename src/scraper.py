import os
import re
import time
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# zendesk API URL and base domain
ZENDESK_ARTICLES_URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
BASE_DOMAIN = "https://support.optisigns.com"

# bad html tags to delete
BAD_TAGS = ["script", "style", "head", "meta", "link", "nav", "footer", "header", "iframe", "noscript"]


# remove advertisements and garbage elements
def prune_unwanted_elements(soup):
    # delete bad tags
    for tag in soup.find_all(BAD_TAGS):
        tag.decompose()

    # delete ad banners by class/id/label
    pattern = re.compile(r"\b(ad|ads|advert|advertisement|sponsor|promoted|promo)\b", re.IGNORECASE)
    for el in soup.find_all(True):
        cls = " ".join(el.get("class", []))
        el_id = el.get("id", "")
        label = el.get("aria-label", "")
        if pattern.search(cls) or pattern.search(el_id) or pattern.search(label):
            el.decompose()

    # resolve relative links and images
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if href.startswith("/"):
            a["href"] = BASE_DOMAIN + href

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("/"):
            img["src"] = BASE_DOMAIN + src
        elif src.startswith("data:"):
            img.decompose()

# get all articles from zendesk API
def get_articles_from_zendesk(max_retries=2, retry_delay=1):
    articles_list = []
    current_url = ZENDESK_ARTICLES_URL
    
    while currentUrl := current_url:
        data = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(currentUrl, timeout=15)
                response.raise_for_status()
                data = response.json()
                break
            except Exception as e:
                if attempt < max_retries:
                    print(f"fetch error, retrying: {e}")
                    time.sleep(retry_delay)
                else:
                    print(f"fetch failed: {e}")
                    if articles_list:
                        return articles_list, "incomplete"
                    return [], "failed"

        page_articles = data.get("articles", [])
        articles_list.extend(page_articles)
        current_url = data.get("next_page")
             
    return articles_list, "complete"

# convert HTML content to Markdown format
def convert_html_to_markdown(html_content, article_title, article_url):
    if not html_content:
        body_markdown = "No content available."
    else:
        soup = BeautifulSoup(html_content, "html.parser")
        prune_unwanted_elements(soup)
        body_markdown = md(str(soup), heading_style="ATX", bullets="*")
    
    # remove duplicate empty lines
    body_markdown = re.sub(r'\n{3,}', '\n\n', body_markdown).strip()
    
    return (
        f"# {article_title}\n\n"
        f"Article URL: {article_url}\n\n"
        f"---\n\n"
        f"{body_markdown}\n"
    )

# save article Markdown file
def save_article_as_markdown(article, output_dir="data/articles"):
    os.makedirs(output_dir, exist_ok=True)
    
    title = article.get("title", "Untitled")
    html_url = article.get("html_url", "")
    body_html = article.get("body", "")
    
    slug = html_url.rstrip("/").split("/")[-1]
    if not slug:
        slug = re.sub(r'[^a-zA-Z0-9]', '-', title).lower()
        slug = f"{article.get('id')}-{slug}"
        
    file_path = os.path.join(output_dir, f"{slug}.md")
    markdown_content = convert_html_to_markdown(body_html, title, html_url)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    return file_path
