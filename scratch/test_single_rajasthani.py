import os
from icrawler.builtin import BingImageCrawler

def main():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_rajasthani_single')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    print("Testing single Rajasthani query...")
    crawler = BingImageCrawler(downloader_threads=2, storage={'root_dir': test_dir})
    crawler.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.bing.com/'
    })
    
    crawler.crawl(keyword='mehndi design rajasthani', max_num=5)
    print("Test complete. Files in test_rajasthani_single:")
    print(os.listdir(test_dir))

if __name__ == '__main__':
    main()
