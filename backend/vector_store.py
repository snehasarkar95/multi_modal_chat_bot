from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import MarkdownHeaderTextSplitter
import numpy as np
from typing import List, Dict, Optional
import uuid

class VectorStore:
    def __init__(self, collection_name: str = "wikipedia_docs"):
        self.collection_name = collection_name
        self.client = QdrantClient(path="./qdrant_data")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_size = 384
        
        self._initialize_collection()
    
    def _initialize_collection(self):
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
        except:
            # Create collection if it doesn't exist
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_size,
                    distance=Distance.COSINE
                )
            )
    def build_markdown_document(self,document: Dict) -> str:
        """
        Convert WikiRequest data into a structured Markdown string
        suitable for chunking.
        """
        markdown_parts = [
            f"## {document['title']}--Summary\n{(document['summary']).strip()}\n",
        ]
        sections = document['content'].split("\n== ")
        for idx, section in enumerate(sections):
            if idx == 0:
                if section.strip():
                    markdown_parts.append(f"## Introduction\n{section.strip()}\n")
                continue
            if "==" in section:
                header, *content = section.split("==", 1)  # split on first '=='
                header = header.strip().strip("=")    
                content_text = content[0].strip() if content else ""

                if header.lower() in ["see also", "references", "external links", "further reading"]:
                    continue
                markdown_parts.append(f"## {header}\n{content_text}\n")

        return "\n\n".join(markdown_parts)

    def _chunk_markdown(self, markdown_content: str, url: str) -> List[Dict]:
        """Split markdown content into chunks with headers"""
        headers_to_split_on = [
            ("##", "Header 2"),
        ]
        
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False
        )
        
        chunks = splitter.split_text(markdown_content)
        for chunk in chunks:
            if "url" not in chunk.metadata:
                chunk.metadata["url"] = url
        return chunks
    
    def store_document(self, document: Dict) -> bool:
        """Store document in vector database"""
        try:
            markdown_content = self.build_markdown_document(document)
            chunks = self._chunk_markdown(markdown_content, document['url'])
            points = []
            for chunk in chunks:
                embedding = self.embedding_model.encode(chunk.page_content).tolist()
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        'content': chunk.page_content,
                        'metadata': chunk.metadata,
                        'title': document['title'],
                        'url': document['url'],
                        'source': "wikipedia"
                    }
                )
                points.append(point)

            # Store in Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            return True

        except Exception as e:
            print(f"Error storing document: {e}")
            return False

    
    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for similar content"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search in Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit
            )
            
            return [
                {
                    'content': result.payload['content'],
                    'metadata': result.payload['metadata'],
                    'title': result.payload['title'],
                    'url': result.payload['url'],
                    'score': result.score
                }
                for result in results
            ]
            
        except Exception as e:
            print(f"Error searching: {e}")
            return []
    
    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                'vectors_count': collection_info.vectors_count,
                'points_count': collection_info.points_count
            }
        except:
            return {'vectors_count': 0, 'points_count': 0}