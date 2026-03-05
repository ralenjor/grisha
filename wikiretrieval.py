import wikipediaapi
import json
import time

# 1. SETUP
# Added 'extract_format' and ensured user_agent is specific
wiki = wikipediaapi.Wikipedia(
    user_agent='grisha (mr.christopher.hahn@gmail.com)',
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI
)

titles_to_download = []

# 2. LOAD TITLES
try:
    with open('titleswithquotes', 'r', encoding='utf-8') as f:
        for line in f:
            clean_line = line.strip()
            clean_line = clean_line.replace('"', '').replace("'", "").replace(",", "")
            clean_line = clean_line.replace("[[", "").replace("]]", "")
            if clean_line:
                titles_to_download.append(clean_line)
    print(f"Successfully loaded and cleaned {len(titles_to_download)} titles.")
except FileNotFoundError:
    print("Error: titleswithquotes not found!")
    exit()

# 3. BATCHING HELPER
def get_batches(item_list, n):
    """Splits a list into chunks of size n."""
    for i in range(0, len(item_list), n):
        yield item_list[i:i + n]

# 4. DOWNLOAD FUNCTION
def fetch_content(title_list, batch_size=50):
    if not title_list:
        return

    # Use 'a' (append) mode so you don't overwrite the file if the script restarts
    with open('russian_military_data.jsonl', 'a', encoding='utf-8') as f:
        # We process in batches to manage the loop logic better
        for batch in get_batches(title_list, batch_size):
            for title in batch:
                try:
                    page = wiki.page(title)

                    if page.exists():
                        entry = {
                            "title": page.title,
                            "text": page.text,
                            "url": page.fullurl,
                            "metadata": {"source": "wikipedia", "topic": "Russian Military"}
                        }
                        f.write(json.dumps(entry) + '\n')
                        print(f"Downloaded: {title}")
                    else:
                        print(f"Page not found: {title}")
 
                    # Polite delay: 100ms between individual page calls
                    time.sleep(0.1)

                except Exception as e:
                    print(f"Error fetching {title}: {e}")
                    # If the server is mad, wait longer
                    time.sleep(5)

            # Optional: Extra "breather" after every 50 articles
            print(f"--- Batch of {batch_size} completed. Taking a breather... ---")
            time.sleep(1)

if __name__ == "__main__":
    fetch_content(titles_to_download, batch_size=50)
