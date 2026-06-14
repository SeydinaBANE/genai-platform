# Couche 4 — RAG Pipeline

## Objectif
Indexer, récupérer et générer des réponses à partir de documents avec une architecture RAG industrialisée.

## Stack
- **Framework** : LlamaIndex
- **Chunking** : Sentence splitting + semantic chunking
- **Embedding** : text-embedding-3-large (via Gateway)
- **Vector Store** : Qdrant (couche 2)
- **Hybrid Search** : dense (embedding) + sparse (BM25)
- **Reranking** : Cohere rerank v3
- **Evaluation** : RAGAS

## Architecture

```
[Document] → [Parser] → [Chunker] → [Embedding] → [Qdrant]
                                                     ↓
[Query] → [Hybrid Search] → [Retrieval] → [Reranking] → [Context Builder]
                                                              ↓
                                                      [LLM Generation]
                                                              ↓
                                                      [Response + Citations]
```

## Stratégie de chunking

```python
class ChunkingStrategy:
    def chunk_document(self, text: str) -> list[Chunk]:
        chunks = []

        # 1. Split sémantique par paragraphes
        paragraphs = self._split_by_paragraphs(text)

        for para in paragraphs:
            # 2. Si trop long, split par phrases
            if len(para) > self.max_chunk_size:
                sentences = self._split_by_sentences(para)
                chunks.extend(self._group_sentences(sentences))
            else:
                chunks.append(Chunk(
                    text=para,
                    metadata={"source": self.source, "section": self._detect_section(para)}
                ))

        # 3. Overlap entre chunks (10-15%)
        chunks = self._add_overlap(chunks, overlap_ratio=0.1)

        return chunks
```

Règles :
- **Chunk size** : 512-1024 tokens selon le modèle
- **Overlap** : 10-15% entre chunks pour éviter la perte de contexte
- **Metadata** : source, page, section, date → pour le filtrage et les citations
- **Document store** : garder les chunks originaux pour la récupération exacte

## Hybrid Search

```python
class HybridSearch:
    def __init__(self, vector_client, sparse_client=None):
        self.vector_client = vector_client
        self.sparse_client = sparse_client or BM25Okapi

    async def search(self, query: str, top_k: int = 20) -> list[ScoredPoint]:
        dense_results = await self._dense_search(query, top_k=top_k)
        sparse_results = await self._sparse_search(query, top_k=top_k)

        # Reciprocal Rank Fusion
        return self._rrf_fusion(dense_results, sparse_results, k=60)

    async def _dense_search(self, query: str, top_k: int) -> list[ScoredPoint]:
        embedding = await self.embedding_model.embed(query)
        return self.vector_client.search(
            collection_name="documents",
            query_vector=embedding,
            limit=top_k,
            with_payload=True,
        )

    async def _sparse_search(self, query: str, top_k: int) -> list[ScoredPoint]:
        return self.sparse_client.search(query, top_k=top_k)
```

## Reranking

```python
class Reranker:
    def __init__(self, model: str = "cohere/rerank-v3.5"):
        self.model = model

    async def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        response = await self.gateway.rerank(
            model=self.model,
            query=query,
            documents=[doc.text for doc in documents],
            top_n=top_k,
        )
        indices = [r.index for r in response.results]
        return [documents[i] for i in indices]
```

## Evaluation (RAGAS)

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)

class RAGEvaluator:
    def evaluate_pipeline(self, dataset) -> dict:
        result = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_recall,
                context_precision,
            ],
        )
        return {
            "faithfulness": result["faithfulness"],
            "relevancy": result["answer_relevancy"],
            "recall": result["context_recall"],
            "precision": result["context_precision"],
            "composite": sum(result.values()) / len(result),
        }
```

## Production thresholds

| Métrique | Seuil d'alerte | Seuil critique |
|---|---|---|
| Faithfulness | < 0.85 | < 0.75 |
| Answer relevancy | < 0.80 | < 0.70 |
| Context recall | < 0.80 | < 0.70 |
| Context precision | < 0.85 | < 0.75 |
| Retrieval latency P99 | > 500ms | > 1s |
| Generation latency P99 | > 5s | > 10s |

## Pièges à éviter
- ❌ Chunking naïf (sentence splitting simple) → perte de sémantique
- ❌ Pas de reranking → le top-5 vectoriel n'est pas le top-5 sémantique
- ❌ Ignorer le contexte → l'overlap entre chunks est critique
- ❌ Pas d'évaluation → impossible de détecter la regression
- ❌ BM25 sans tuning → résultats sparses médiocres
