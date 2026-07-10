from duckduckgo_search import DDGS

def main():
    print("Testing DDGS images...")
    try:
        with DDGS() as ddgs:
            results = ddgs.images("arabic mehndi design", max_results=10)
            print(f"Successfully retrieved {len(results)} results:")
            for i, r in enumerate(results):
                print(f"{i+1}: {r.get('image')} (Title: {r.get('title')[:30]}...)")
    except Exception as e:
        print("Error during DDGS search:", e)

if __name__ == '__main__':
    main()
