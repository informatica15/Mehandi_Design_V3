import os
from icrawler.builtin import GoogleImageCrawler

def main():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_google')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    print("Testing GoogleImageCrawler...")
    crawler = GoogleImageCrawler(downloader_threads=2, storage={'root_dir': test_dir})
    crawler.crawl(keyword='arabic mehndi design simple', max_num=5)
    print("Test complete. Files in test_google:")
    print(os.listdir(test_dir))

if __name__ == '__main__':
    main()
