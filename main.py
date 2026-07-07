import os
import json
import hashlib
import sys
from dotenv import load_dotenv
from src.scraper import get_articles_from_zendesk, convert_html_to_markdown
import src.gemini_uploader as gemini_uploader

load_dotenv()

DATA_DIR = "data"
ARTICLES_DIR = os.path.join(DATA_DIR, "articles")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")

# calculate md5 hash of text
def calculate_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

# read metadata file
def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"gemini_store_name": "", "articles": {}}

# save metadata file
def save_metadata(metadata):
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"error save metadata: {e}")

# sync files using 20 threads to run fast
def run_gemini_sync(gemini_client, store, metadata, articles_to_sync, current_slugs, old_articles_metadata, new_articles_metadata, allow_deletes=True):
    added_count = 0
    updated_count = 0
    deleted_count = 0
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # task to sync one file
    def sync_one(art, idx):
        slug = art["slug"]
        file_path = art["file_path"]
        title = art["title"]
        print(f"[{idx}/{len(articles_to_sync)}] syncing: {title}")
        
        # if updated, delete old document first
        if art["is_updated"]:
            old_doc = old_articles_metadata.get(slug, {}).get("document_name")
            if old_doc:
                try:
                    gemini_uploader.delete_document_from_gemini_store(gemini_client, old_doc)
                except Exception:
                    pass
                    
        # upload file
        doc_name = gemini_uploader.upload_file_to_gemini_store(gemini_client, store.name, file_path)
        return {
            "id": art["id"],
            "slug": slug,
            "title": title,
            "html_url": art["html_url"],
            "updated_at": art["updated_at"],
            "hash": art["hash"],
            "document_name": doc_name,
            "is_updated": art["is_updated"]
        }

    # start threads pool
    print(f"Syncing {len(articles_to_sync)} files with Gemini using 20 threads...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        # submit all jobs
        futures = []
        for idx, art in enumerate(articles_to_sync, 1):
            futures.append(executor.submit(sync_one, art, idx))
            
        # get results
        for f in as_completed(futures):
            try:
                res = f.result()
                slug = res["slug"]
                new_articles_metadata[slug] = {
                    "id": res["id"],
                    "title": res["title"],
                    "html_url": res["html_url"],
                    "updated_at": res["updated_at"],
                    "hash": res["hash"],
                    "document_name": res["document_name"]
                }
                if res["is_updated"]:
                    updated_count += 1
                else:
                    added_count += 1
            except Exception as e:
                print(f"sync file error: {e}")

    # delete removed files
    if allow_deletes:
        for slug in list(old_articles_metadata.keys()):
            if slug not in current_slugs:
                old_doc = old_articles_metadata[slug].get("document_name")
                if old_doc:
                    try:
                        gemini_uploader.delete_document_from_gemini_store(gemini_client, old_doc)
                    except Exception:
                        pass
                    
                file_path = os.path.join(ARTICLES_DIR, f"{slug}.md")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                deleted_count += 1

    return added_count, updated_count, deleted_count


def main():
    print("start sync job...")
    
    try:
        client = gemini_uploader.get_gemini_client()
    except Exception as e:
        print(f"config error: {e}")
        return 1
        
    metadata = load_metadata()
    os.makedirs(ARTICLES_DIR, exist_ok=True)

    env_store_name = os.environ.get("GEMINI_STORE_NAME") or "OptiBot Store"
    try:
        store = gemini_uploader.get_or_create_file_search_store(client, store_name=env_store_name)
    except Exception as e:
        print(f"cannot connect to store: {e}")
        return 1

    # reset cache if store changed
    if metadata.get("gemini_store_name") != store.name:
        print("change store or first run. reset cache...")
        metadata["articles"] = {}
        metadata["gemini_store_name"] = store.name

    # fetch articles
    current_articles, fetch_status = get_articles_from_zendesk()
    if fetch_status != "complete":
        print(f"fetch not complete ({fetch_status}). abort sync!")
        return 1

    if not current_articles:
        print("no articles found!")
        return 1
        
    print(f"fetched total {len(current_articles)} articles.")

    current_slugs = set()
    skipped_count = 0
    new_articles_metadata = {}
    old_articles_metadata = metadata.get("articles", {})
    articles_to_sync = []

    # check if file new or updated
    for article in current_articles:
        title = article.get("title", "Untitled")
        html_url = article.get("html_url", "")
        updated_at = article.get("updated_at", "")
        body_html = article.get("body", "")
        
        slug = html_url.rstrip("/").split("/")[-1]
        if not slug:
            continue
            
        current_slugs.add(slug)
        
        markdown_content = convert_html_to_markdown(body_html, title, html_url)
        content_hash = calculate_hash(markdown_content)
        file_path = os.path.join(ARTICLES_DIR, f"{slug}.md")
        
        is_new = slug not in old_articles_metadata
        is_updated = False
        
        if not is_new:
            old_meta = old_articles_metadata[slug]
            is_updated = (old_meta.get("hash") != content_hash) or (old_meta.get("updated_at") != updated_at)

        if is_new or is_updated:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            articles_to_sync.append({
                "id": article.get("id"),
                "slug": slug,
                "title": title,
                "html_url": html_url,
                "updated_at": updated_at,
                "hash": content_hash,
                "file_path": file_path,
                "is_new": is_new,
                "is_updated": is_updated
            })
        else:
            skipped_count += 1
            new_articles_metadata[slug] = old_articles_metadata[slug]

    # start sync to gemini
    try:
        added_count, updated_count, deleted_count = run_gemini_sync(
            client,
            store,
            metadata,
            articles_to_sync,
            current_slugs,
            old_articles_metadata,
            new_articles_metadata,
            allow_deletes=(fetch_status == "complete")
        )
    except Exception as e:
        print(f"sync error: {e}")
        return 1

    metadata["articles"] = new_articles_metadata
    save_metadata(metadata)

    print("========================================")
    print("sync finished!")
    print(f"Added:   {added_count}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Deleted: {deleted_count}")
    print("========================================")

    print(f"added: {added_count}, updated: {updated_count}, skipped: {skipped_count}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
