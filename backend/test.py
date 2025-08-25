import wikipedia

# Search for a topic
# results = wikipedia.search("Python programming language")
# print("Search results:", results)

# # Get summary of a page
# summary = wikipedia.summary("Python (programming language)", sentences=2)
# print("\nSummary:\n", summary)

# Get full page content
page = wikipedia.page("Data Science")
print("\nTitle:", page.title)
print("URL:", page.url)
print("Content (first 500 chars):", page.content)
