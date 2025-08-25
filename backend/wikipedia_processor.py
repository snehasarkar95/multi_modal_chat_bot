import requests
from bs4 import BeautifulSoup
import markdown
from typing import Optional, Dict
import re

class WikipediaProcessor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _validate_wikipedia_url(self, url: str) -> bool:
        """Validate if URL is a Wikipedia URL"""
        wikipedia_patterns = [
            r'^https?://(?:[a-z]+\.)?wikipedia\.org/wiki/',
            r'^https?://(?:[a-z]{2})\.wikipedia\.org/wiki/'
        ]
        
        return any(re.match(pattern, url, re.IGNORECASE) for pattern in wikipedia_patterns)
    
    def _html_to_markdown(self, element) -> str:
        """Convert HTML element to markdown format"""
        markdown_lines = []
        
        for child in element.children:
            if child.name == 'h1':
                markdown_lines.append(f"# {child.get_text().strip()}")
            elif child.name == 'h2':
                markdown_lines.append(f"## {child.get_text().strip()}")
            elif child.name == 'h3':
                markdown_lines.append(f"### {child.get_text().strip()}")
            elif child.name == 'p':
                markdown_lines.append(child.get_text().strip())
            elif child.name == 'ul':
                for li in child.find_all('li'):
                    markdown_lines.append(f"- {li.get_text().strip()}")
            elif child.name == 'ol':
                for i, li in enumerate(child.find_all('li'), 1):
                    markdown_lines.append(f"{i}. {li.get_text().strip()}")
            elif child.name == 'table':
                # Simple table conversion
                rows = child.find_all('tr')
                if rows:
                    headers = [th.get_text().strip() for th in rows[0].find_all(['th', 'td'])]
                    markdown_lines.append("| " + " | ".join(headers) + " |")
                    markdown_lines.append("|" + "|".join(["---"] * len(headers)) + "|")
                    for row in rows[1:]:
                        cells = [td.get_text().strip() for td in row.find_all(['th', 'td'])]
                        markdown_lines.append("| " + " | ".join(cells) + " |")
        
        return "\n\n".join(markdown_lines)