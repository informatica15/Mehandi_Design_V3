import requests
import json
from bs4 import BeautifulSoup

def main():
    query = 'bridal mehndi'
    url = f"https://www.bing.com/images/search?q={query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.bing.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    session = requests.Session()
    # First visit bing homepage to get cookies
    session.get("https://www.bing.com/", headers=headers)
    
    # Now query images
    response = session.get(url, headers=headers)
    print(f"Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', class_='iusc')
    print(f"Found {len(links)} links")
    
    for i, link in enumerate(links[:5]):
        try:
            m_attr = link.get('m')
            if m_attr:
                m_data = json.loads(m_attr)
                murl = m_data.get('murl')
                title = m_data.get('t') or 'No Title'
                print(f"  {i+1}: {title[:50]}... ({murl})")
        except Exception:
            continue

if __name__ == '__main__':
    main()
