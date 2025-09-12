import wikipedia
import json
from typing import List, Dict, Optional
import asyncio
import aiohttp
import logging
from ddgs import DDGS 
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class WebSearchManager:
    def __init__(self):
        self.wikipedia_timeout = 5
        self.duckduckgo_timeout = 8

        wikipedia.set_lang('en')
        wikipedia.set_rate_limiting(True)
    
    async def fetch_webpage_content(self, url: str) -> str:
        """Fetch and extract main content from a webpage"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        soup = BeautifulSoup(html_content, 'html.parser')
                        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                            element.decompose()
                        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main', 'article'])
                        
                        if main_content:
                            paragraphs = main_content.find_all('p')
                            content = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                        else:
                            paragraphs = soup.find_all('p')
                            content = ' '.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

                        if len(content) > 2000:
                            content = content[:2000] + "..."
                        return content
                    else:
                        return f"Could not fetch content (Status: {response.status})"
        except Exception as e:
            return f"Error fetching content: {str(e)}"
        
    async def search_wikipedia(self, query: str) -> Optional[Dict]:
        """Search Wikipedia for the query"""
        try:
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(None, lambda: wikipedia.search(query, results=3))
            if not search_results:
                return None 
            page_title = search_results[0]
            page = await loop.run_in_executor(
                None, lambda: wikipedia.page(page_title, auto_suggest=False)
            )
            return {
                'title': page.title,
                'content': page.summary,
                'url': page.url,
                'source': 'wikipedia',
                'score': 0.9
            } 
        except wikipedia.exceptions.DisambiguationError as e:
            return {
                'title': f"Disambiguation: {query}",
                'content': f"Multiple options found: {', '.join(e.options[:5])}",
                'url': f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}",
                'source': 'wikipedia_disambiguation',
                'score': 0.7
            }
        except wikipedia.exceptions.PageError:
            return None
        except Exception as e:
            # logger.warning(f"Wikipedia search error: {e}")
            print(f"Wikipedia search error: {e}")
            return None
    
    # NOTE check fucntion no in use
    async def test_search_duckduckgo(self, query: str) -> List[Dict]:
        """Search DuckDuckGo for the query with proper headers"""
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1',
                'no_redirect': '1',
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=self.duckduckgo_timeout) as response:
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        # If not JSON, try to parse as text first
                        text_response = await response.text()
                        # Sometimes DDG returns JavaScript, try to extract JSON from it
                        if 'application/x-javascript' in content_type or 'javascript' in content_type:
                            # Try to find JSON in the JavaScript response
                            json_start = text_response.find('{')
                            json_end = text_response.rfind('}') + 1
                            if json_start != -1 and json_end != -1:
                                json_str = text_response[json_start:json_end]
                                try:
                                    data = json.loads(json_str)
                                except json.JSONDecodeError:
                                    # Fallback: try to get HTML version
                                    return await self.fallback_duckduckgo_search(query)
                            else:
                                return await self.fallback_duckduckgo_search(query)
                        else:
                            # Try to parse as JSON anyway
                            try:
                                data = await response.json()
                            except:
                                return await self.fallback_duckduckgo_search(query)
                    else:
                        # Proper JSON response
                        data = await response.json()
                    
                    results = []
                    
                    # Extract instant answer
                    if data.get('AbstractText'):
                        results.append({
                            'title': data.get('Heading', query),
                            'content': data.get('AbstractText', ''),
                            'url': data.get('AbstractURL', ''),
                            'source': 'duckduckgo_instant',
                            'score': 0.85
                        })
                    # # Extract related topics
                    # for topic in data.get('RelatedTopics', [])[:5]:
                    #     if isinstance(topic, dict) and 'Text' in topic and 'FirstURL' in topic:
                    #         results.append({
                    #             'title': topic.get('Text', '').split(' - ')[0] if ' - ' in topic.get('Text', '') else query,
                    #             'content': topic.get('Text', ''),
                    #             'url': topic.get('FirstURL', ''),
                    #             'source': 'duckduckgo_related',
                    #             'score': 0.7
                    #         })
                    #     elif isinstance(topic, dict) and 'Name' in topic:
                    #         # Handle different response format
                    #         results.append({
                    #             'title': topic.get('Name', query),
                    #             'content': topic.get('Description', '') or topic.get('Result', ''),
                    #             'url': topic.get('FirstURL', '') or topic.get('URL', ''),
                    #             'source': 'duckduckgo_topic',
                    #             'score': 0.6
                    #         })
                    
                    return results
                    
        except asyncio.TimeoutError:
            # logger.warning("DuckDuckGo search timed out")
            print("DuckDuckGo search timed out")
            return []
        except Exception as e:
            # logger.warning(f"DuckDuckGo search error: {e}")
            print(f"DuckDuckGo search error: {e}")
            return []
    

    async def search_duckduckgo(self, query: str) -> List[Dict]:
        """Search DuckDuckGo using the official library"""
        print(f"Searching DuckDuckGo for: {query}")
        
        try:
            results = []
            ddgs = DDGS() 
            text_results = ddgs.text(query, max_results=5)
            if text_results:
                top_result = text_results[0]
                detailed_content = await self.fetch_webpage_content(top_result.get('href', ''))
                results.append({
                    'title': top_result.get('title', ''),
                    'content': detailed_content if detailed_content else top_result.get('body', ''),
                    'url': top_result.get('href', ''),
                    'source': 'duckduckgo_web_detailed',
                    'score': 0.9
                })
                for result in text_results[1:4]:
                    results.append({
                        'title': result.get('title', ''),
                        'content': result.get('body', ''),
                        'url': result.get('href', ''),
                        'source': 'duckduckgo_web',
                        'score': 0.7
                    })
            news_results = ddgs.news(query, max_results=3)
            if news_results:
                top_result = news_results[0]
                detailed_content = await self.fetch_webpage_content(top_result.get('href', ''))
                results.append({
                    'title': top_result.get('title', ''),
                    'content': detailed_content if detailed_content else top_result.get('body', ''),
                    'url': top_result.get('href', ''),
                    'source': 'duckduckgo_web_detailed',
                    'score': 0.9
                })
                for result in news_results[1:4]:
                    results.append({
                        'title': result.get('title', ''),
                        'content': result.get('body', ''),
                        'url': result.get('url', ''),
                        'source': 'duckduckgo_news',
                        'score': 0.7
                    })
            
            print(f"DuckDuckGo search completed with {len(results)} results")
            return results
            
        except Exception as e:
            print(f"DuckDuckGo library search error: {e}")
            return await self.fallback_manual_search(query)

    async def fallback_duckduckgo_search(self, query: str) -> List[Dict]:
        """Fallback search using HTML endpoint or alternative approach"""
        try:
            html_url = "https://html.duckduckgo.com/html/"
            params = {'q': query}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(html_url, params=params, headers=headers, timeout=10) as response:
                    html_content = await response.text()
                    results = []
                    results.append({
                        'title': f"Search: {query}",
                        'content': f"Web search results for '{query}'",
                        'url': f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                        'source': 'duckduckgo_fallback',
                        'score': 0.5
                    })
                    
                    return results
                    
        except Exception as e:
            logger.warning(f"Fallback DuckDuckGo search also failed: {e}")
            return []
        
    async def combined_web_search(self, query: str) -> List[Dict]:
        """Perform combined Wikipedia and DuckDuckGo search"""
        try:
            wikipedia_task = asyncio.create_task(self.search_wikipedia(query))
            duckduckgo_task = asyncio.create_task(self.search_duckduckgo(query))
            
            wikipedia_result, duckduckgo_results = await asyncio.gather(
                wikipedia_task, duckduckgo_task,
                return_exceptions=True
            )
            all_results = []
            if wikipedia_result and not isinstance(wikipedia_result, Exception):
                all_results.append(wikipedia_result)

            if duckduckgo_results and not isinstance(duckduckgo_results, Exception):
                all_results.extend(duckduckgo_results)
            unique_results = self._deduplicate_results(all_results)
            # logger.info(f"Combined web search found {len(unique_results)} results for '{query}'")
            print(f"Combined web search found {len(unique_results)} results for '{query}'")
            return unique_results
            
        except Exception as e:
            # logger.error(f"Combined web search failed: {e}")
            print(f"Combined web search failed: {e}")
            return []
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate or very similar results"""
        seen_urls = set()
        unique_results = []
        
        for result in results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
            elif not url:
                unique_results.append(result)
        return unique_results

web_search_manager = WebSearchManager() # Initializing web search manager