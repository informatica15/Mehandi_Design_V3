import requests
from bs4 import BeautifulSoup
import json

def main():
    query = 'bridal mehndi'
    url = f"https://images.search.yahoo.com/search/images?p={query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Testing Yahoo Image Search for: '{query}'")
    response = requests.get(url, headers=headers)
    print(f"Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    # Yahoo image search stores details in a list item or a anchor tag, let's look for tags
    items = soup.find_all('li', class_='ld')
    print(f"Found {len(items)} class='ld' items")
    
    # Also check all images
    imgs = soup.find_all('img')
    print(f"Found {len(imgs)} img tags")
    
    # Yahoo often stores JSON in metadata attribute or data attribute
    # Let's inspect some of the 'ld' item contents
    for i, item in enumerate(items[:5]):
        data = item.get('data-rurl') or item.get('data-src') or item.get('data')
        print(f"Item {i+1}: {item.text[:50]}... Data: {data}")

if __name__ == '__main__':
    main()
