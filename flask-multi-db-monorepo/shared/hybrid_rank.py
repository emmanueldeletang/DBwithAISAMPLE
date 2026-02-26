"""
Hybrid search utilities - Reciprocal Rank Fusion (RRF)
"""
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Generic search result with score."""
    id: Any
    data: Dict[str, Any]
    score: float
    source: str = "unknown"  # "keyword", "vector", or "hybrid"


def reciprocal_rank_fusion(
    keyword_results: List[SearchResult],
    vector_results: List[SearchResult],
    k: int = 60,
    keyword_weight: float = 0.5,
    vector_weight: float = 0.5
) -> List[SearchResult]:
    """
    Combine keyword and vector search results using Reciprocal Rank Fusion.
    
    RRF formula: score = sum(weight / (k + rank)) for each list
    
    Args:
        keyword_results: Results from keyword search, ordered by relevance
        vector_results: Results from vector search, ordered by similarity
        k: RRF constant (default 60, higher = more uniform weighting)
        keyword_weight: Weight for keyword results
        vector_weight: Weight for vector results
    
    Returns:
        Combined results sorted by RRF score
    """
    # Normalize weights
    total_weight = keyword_weight + vector_weight
    keyword_weight = keyword_weight / total_weight
    vector_weight = vector_weight / total_weight
    
    # Calculate RRF scores
    rrf_scores: Dict[Any, float] = {}
    result_data: Dict[Any, Dict[str, Any]] = {}
    
    # Process keyword results
    for rank, result in enumerate(keyword_results, start=1):
        rrf_score = keyword_weight / (k + rank)
        rrf_scores[result.id] = rrf_scores.get(result.id, 0) + rrf_score
        result_data[result.id] = result.data
    
    # Process vector results
    for rank, result in enumerate(vector_results, start=1):
        rrf_score = vector_weight / (k + rank)
        rrf_scores[result.id] = rrf_scores.get(result.id, 0) + rrf_score
        if result.id not in result_data:
            result_data[result.id] = result.data
    
    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Create combined results
    combined_results = []
    for id_ in sorted_ids:
        combined_results.append(SearchResult(
            id=id_,
            data=result_data[id_],
            score=rrf_scores[id_],
            source="hybrid"
        ))
    
    return combined_results


def normalize_scores(results: List[SearchResult]) -> List[SearchResult]:
    """Normalize scores to 0-1 range."""
    if not results:
        return results
    
    max_score = max(r.score for r in results)
    min_score = min(r.score for r in results)
    
    if max_score == min_score:
        return [SearchResult(r.id, r.data, 1.0, r.source) for r in results]
    
    return [
        SearchResult(
            r.id,
            r.data,
            (r.score - min_score) / (max_score - min_score),
            r.source
        )
        for r in results
    ]


def merge_and_deduplicate(
    *result_lists: List[SearchResult],
    limit: int = 20
) -> List[SearchResult]:
    """Merge multiple result lists and remove duplicates, keeping highest score."""
    seen: Dict[Any, SearchResult] = {}
    
    for results in result_lists:
        for result in results:
            if result.id not in seen or result.score > seen[result.id].score:
                seen[result.id] = result
    
    sorted_results = sorted(seen.values(), key=lambda x: x.score, reverse=True)
    return sorted_results[:limit]
