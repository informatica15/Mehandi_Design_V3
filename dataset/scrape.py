import os
import shutil
import time
from icrawler.builtin import BingImageCrawler

# Queries optimized to start with "mehndi design" to avoid bot detection trending redirects
categories_queries = {
    'bridal': [
        'mehndi design bridal hand',
        'mehndi design bridal wedding'
    ],
    'arabic': [
        'mehndi design arabic style',
        'mehndi design arabic simple'
    ],
    'indo_arabic': [
        'mehndi design indo arabic',
        'mehndi design indo arabic pattern'
    ],
    'minimalist': [
        'mehndi design minimalist simple',
        'mehndi design minimalist back hand'
    ],
    'floral': [
        'mehndi design floral pattern',
        'mehndi design floral simple'
    ],
    'geometric': [
        'mehndi design geometric line',
        'mehndi design geometric pattern'
    ],
    'rajasthani': [
        'mehndi design rajasthani traditional',
        'mehndi design rajasthani bridal'
    ],
    'finger': [
        'mehndi design finger simple',
        'mehndi design finger pattern'
    ]
}

def safe_recreate_dir(path):
    """
    Safely deletes and recreates a directory on Windows to prevent lock issues.
    """
    if os.path.exists(path):
        print(f"Clearing old directory: {path}")
        try:
            shutil.rmtree(path)
            # Bounded wait for Windows to release file handles
            for _ in range(20):
                if not os.path.exists(path):
                    break
                time.sleep(0.1)
        except Exception as e:
            print(f"Warning: could not delete {path} immediately. Retrying... {e}")
            time.sleep(1.0)
            try:
                shutil.rmtree(path)
            except Exception:
                pass
    
    # Try creating it
    for _ in range(5):
        try:
            os.makedirs(path, exist_ok=True)
            return
        except Exception:
            time.sleep(0.2)
    os.makedirs(path, exist_ok=True)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Starting dataset scraping with rate-limit bypass strategy...")
    
    for category, queries in categories_queries.items():
        category_dir = os.path.join(base_dir, category)
        
        # Safely recreate directory
        safe_recreate_dir(category_dir)
        
        print(f"\n==========================================")
        print(f"Scraping category '{category}' using {len(queries)} synonyms...")
        print(f"==========================================")
        
        for i, query in enumerate(queries):
            print(f"Query {i+1}/{len(queries)}: '{query}'")
            
            # Use a temporary subfolder for each query to avoid icrawler duplicate numbering collision
            temp_dir = os.path.join(category_dir, f"temp_{i}")
            os.makedirs(temp_dir, exist_ok=True)
            
            crawler = BingImageCrawler(
                downloader_threads=4,
                storage={'root_dir': temp_dir}
            )
            
            crawler.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.bing.com/'
            })
            
            # Scrape top 25 images
            crawler.crawl(keyword=query, max_num=25, overwrite=True)
            
            # Move downloaded files from temp_dir to category_dir
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    src_file = os.path.join(temp_dir, filename)
                    if os.path.isfile(src_file):
                        # Generate unique filename using query index
                        new_filename = f"q{i}_{filename}"
                        dest_file = os.path.join(category_dir, new_filename)
                        try:
                            shutil.move(src_file, dest_file)
                        except Exception as e:
                            print(f"Error moving file: {e}")
                
                # Remove temp_dir
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
                    
            print(f"  Finished query {i+1}. Waiting 5 seconds to bypass rate limiting...")
            time.sleep(5.0)
            
        # Count total images downloaded
        downloaded = len([f for f in os.listdir(category_dir) if os.path.isfile(os.path.join(category_dir, f))])
        print(f"Finished scraping category '{category}'. Total images: {downloaded}\n")
        time.sleep(3.0)
        
    print("\nDataset scraping complete!")

if __name__ == '__main__':
    main()
