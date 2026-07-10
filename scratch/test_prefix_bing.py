import os
from icrawler.builtin import BingImageCrawler

def main():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_simplified_bing')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    print("Testing BingImageCrawler with prefix 'mehndi design' and modern User-Agent...")
    crawler = BingImageCrawler(downloader_threads=2, storage={'root_dir': test_dir})
    crawler.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    crawler.crawl(keyword='mehndi design bridal hand', max_num=5)
    print("Test complete. Files in test_simplified_bing:")
    print(os.listdir(test_dir))

if __name__ == '__main__':
    main()
