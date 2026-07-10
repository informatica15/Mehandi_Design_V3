import os
from icrawler.builtin import BingImageCrawler

def main():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_pagination')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    print("Testing single query pagination (50 images)...")
    crawler = BingImageCrawler(downloader_threads=4, storage={'root_dir': test_dir})
    crawler.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.bing.com/'
    })
    
    crawler.crawl(keyword='mehndi design rajasthani', max_num=50)
    print(f"Test complete. Downloaded {len(os.listdir(test_dir))} files.")

if __name__ == '__main__':
    main()
