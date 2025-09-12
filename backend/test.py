import wikipedia

# # Search for a topic
# results = wikipedia.search("Python programming language")
# print("Search results:", results)

# # Get summary of a page
# summary = wikipedia.summary("Python (programming language)", sentences=2)
# print("\nSummary:\n", summary)

# Get full page content
# page = wikipedia.page("what are research articles?")
# print("\nTitle:", page.title)
# print("URL:", page.url)
# print("Content (first 500 chars):", page.content)


import requests
import json

def duckduckgo_search(query):
    url = "https://api.duckduckgo.com/"
    params = {
        'q': query,
        'format': 'json',
        'no_html': '1',
        'skip_disambig': '1'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant information
        results = {
            'abstract': data.get('Abstract', ''),
            'abstract_text': data.get('AbstractText', ''),
            'abstract_source': data.get('AbstractSource', ''),
            'abstract_url': data.get('AbstractURL', ''),
            'related_topics': data.get('RelatedTopics', []),
            'results': data.get('Results', [])
        }
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

# Usage
results = duckduckgo_search("Give the history of inspirext")
print(json.dumps(results, indent=2))
print(results.get('abstract'))