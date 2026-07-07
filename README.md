# OptiBot Mini-Clone Sync Job

This is a simple Python script to scrape help articles from support.optisigns.com, clean them up to Markdown, and sync them with a Google Gemini File Search Store. This helps a Gemini bot answer user questions using the latest support docs.

## How to Setup and Run

### 1. What you need
- Python 3.13 or newer installed.
- Docker (optional, if you want to run via container).
- A Google Gemini API Key from Google AI Studio.

### 2. Configure Environment
Copy the `.env.sample` file to `.env`:
```bash
cp .env.sample .env
```
Open `.env` and put your Gemini API key:
```env
GEMINI_API_KEY=your_actual_api_key_here
GEMINI_STORE_NAME=OptiBot Store
```

### 3. Run Locally
Install Python dependencies:
```bash
pip install -r requirements.txt
```
Run the sync script:
```bash
python main.py
```
This will download all articles, clean the HTML (removing scripts, ads, and fixing link URLs), save them to the `data/articles/` folder, and sync them to your Gemini store.

Run the chatbot test:
```bash
python ask_gemini.py
```
This will ask Gemini a test question ("How do I add a YouTube video?") to verify the search store works and prints citations.

---

## Running with Docker

You can also run everything inside Docker so you don't need to install Python locally.

### 1. Build the Docker Image
```bash
docker build -t optibot-sync .
```

### 2. Run the Container
Run the container and mount the local `data` folder to keep the sync cache:
```bash
docker run --env-file .env -v "$(pwd)/data:/app/data" optibot-sync
```

---

## How it Works

1. **Scraping & Cleaning**:
   - The script pulls articles from Zendesk API.
   - It parses HTML using BeautifulSoup and converts it to Markdown using `markdownify`.
   - It has custom rules to remove ads, menu headers/footers, and turns relative links into working absolute links.
   - It preserves formatting like bold text, lists, and tables so Gemini can read them easily.

2. **Delta Syncing (Only uploads changes)**:
   - On every run, the script calculates MD5 hashes of the markdown files and compares them with `data/metadata.json`.
   - It only uploads new or updated articles to Gemini.
   - If an article is deleted on the website, it deletes it from local storage and the Gemini store too (saves API costs).
