"""
Embeddings generation using Azure OpenAI
"""
import os
import json
import hashlib
from typing import List, Optional
from openai import AzureOpenAI
from .config import openai_config

# Simple in-memory cache for embeddings
_embedding_cache: dict = {}


def get_openai_client() -> Optional[AzureOpenAI]:
    """Get Azure OpenAI client if configured."""
    if not openai_config.endpoint or not openai_config.api_key:
        return None
    
    return AzureOpenAI(
        azure_endpoint=openai_config.endpoint,
        api_key=openai_config.api_key,
        api_version="2024-02-01"
    )


def generate_embedding(text: str, use_cache: bool = True, dimensions: Optional[int] = None) -> Optional[List[float]]:
    """
    Generate embedding for a text using Azure OpenAI.
    Returns None if OpenAI is not configured.
    
    Args:
        text: Text to embed.
        use_cache: Whether to use the in-memory cache.
        dimensions: Override the default embedding dimension (e.g. 3072 for PostgreSQL).
    """
    if not text or not text.strip():
        return None
    
    # Normalize text
    text = text.strip().lower()
    dim = dimensions or openai_config.embedding_dimension
    
    # Check cache (include dimension in key to avoid collisions)
    cache_key = hashlib.md5(f"{dim}:{text}".encode()).hexdigest()
    if use_cache and cache_key in _embedding_cache:
        return _embedding_cache[cache_key]
    
    client = get_openai_client()
    if not client:
        return None
    
    try:
        response = client.embeddings.create(
            model=openai_config.embedding_deployment,
            input=text,
            dimensions=dim
        )
        
        embedding = response.data[0].embedding
        
        # Cache the result
        if use_cache:
            _embedding_cache[cache_key] = embedding
        
        return embedding
    
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


def generate_embeddings_batch(texts: List[str], use_cache: bool = True) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts."""
    results = []
    dim = openai_config.embedding_dimension
    
    # Separate cached and uncached texts
    uncached_indices = []
    uncached_texts = []
    
    for i, text in enumerate(texts):
        if not text or not text.strip():
            results.append(None)
            continue
        
        text = text.strip().lower()
        # Include dimension in cache key to be consistent with generate_embedding()
        cache_key = hashlib.md5(f"{dim}:{text}".encode()).hexdigest()
        
        if use_cache and cache_key in _embedding_cache:
            results.append(_embedding_cache[cache_key])
        else:
            results.append(None)  # Placeholder
            uncached_indices.append(i)
            uncached_texts.append(text)
    
    # Generate embeddings for uncached texts
    if uncached_texts:
        client = get_openai_client()
        if client:
            try:
                response = client.embeddings.create(
                    model=openai_config.embedding_deployment,
                    input=uncached_texts,
                    dimensions=dim
                )
                
                for j, embedding_data in enumerate(response.data):
                    idx = uncached_indices[j]
                    embedding = embedding_data.embedding
                    results[idx] = embedding
                    
                    # Cache with dimension-aware key
                    if use_cache:
                        cache_key = hashlib.md5(f"{dim}:{uncached_texts[j]}".encode()).hexdigest()
                        _embedding_cache[cache_key] = embedding
            
            except Exception as e:
                print(f"Error generating batch embeddings: {e}")
    
    return results


def embedding_to_json(embedding: Optional[List[float]]) -> Optional[str]:
    """Convert embedding to JSON string for storage."""
    if embedding is None:
        return None
    return json.dumps(embedding)


def json_to_embedding(json_str: Optional[str]) -> Optional[List[float]]:
    """Convert JSON string back to embedding list."""
    if not json_str:
        return None
    return json.loads(json_str)
