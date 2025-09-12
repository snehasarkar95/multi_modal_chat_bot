
from typing import List, Dict

def format_web_context(web_results: List[Dict]) -> str:
    """Format web results for display in response"""
    if not web_results:
        return ""
    
    context_lines = []
    for i, result in enumerate(web_results[:3], 1):
        source = result.get('source', 'web')
        title = result.get('title', 'Unknown')
        url = result.get('url', '')
        
        source_display = source.upper().replace('_', ' ')
        context_lines.append(f"{i}. [{source_display}] {title}\n")
        if url:
            context_lines.append(f"   URL: {url}")
        context_lines.append("") 
    return "\n".join(context_lines)