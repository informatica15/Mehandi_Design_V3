import os
import shutil
import time
from icrawler.builtin import BingImageCrawler

test_categories = {
    'rajasthani': [
        'mehndi design rajasthani traditional',
        'rajasthani bridal mehndi full hand'
    ],
    'minimalist': [
        'mehndi design minimalist simple',
        'minimalist henna design back hand'
    ]
}

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(base_dir, 'test_rate_limit_bypass')
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    print("Testing 2-query strategy with 5s delay...")
    for category, queries in test_categories.items():
        category_dir = os.path.join(test_dir, category)
        os.makedirs(category_dir)
        
        print(f"\nScraping {category}...")
        for i, query in enumerate(queries):
            print(f"  Query {i+1}: '{query}'")
            temp_dir = os.path.join(category_dir, f"temp_{i}")
            os.makedirs(temp_dir)
            
            crawler = BingImageCrawler(downloader_threads=2, storage={'root_dir': temp_dir})
            crawler.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.bing.com/'
            })
            
            # Scrape top 25 images
            crawler.crawl(keyword=query, max_num=25, overwrite=True)
            
            # Move files
            for filename in os.listdir(temp_dir):
                src_file = os.path.join(temp_dir, filename)
                if os.path.isfile(src_file):
                    shutil.move(src_file, os.path.join(category_dir, f"q{i}_{filename}"))
            shutil.rmtree(temp_dir)
            
            print(f"  Finished query {i+1}. Waiting 5 seconds...")
            time.sleep(5)
            
        print(f"Finished {category}. Total images: {len(os.listdir(category_dir))}")

if __name__ == '__main__':
    main()
