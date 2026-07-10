import os
import re
import json
import requests
from bs4 import BeautifulSoup

def main():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_custom_bing')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    query = 'bridal mehndi design hand'
    print(f"Testing custom Bing scraper for: '{query}'")
    
    url = f"https://www.bing.com/images/search?q={query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    print(f"Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', class_='iusc')
    
    image_urls = []
    for link in links:
        try:
            m_attr = link.get('m')
            if m_attr:
                m_data = json.loads(m_attr)
                murl = m_data.get('murl')
                if murl:
                    image_urls.append(murl)
        except Exception as e:
            continue
            
    print(f"Found {len(image_urls)} image URLs.")
    # Show first 10 URLs
    for url in image_urls[:10]:
        print(" -", url)

if __name__ == '__main__':
    main()
