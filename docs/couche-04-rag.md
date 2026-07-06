# Couche 4 — RAG Pipeline

## Objectif
Indexer, récupérer et générer des réponses à partir de documents avec une architecture RAG industrialisée.

## Stack
- **Framework** : pipeline maison (pas de LlamaIndex — `RAGPipeline` orchestre chunking, embedding, recherche et reranking derrière des ports)
- **Chunking** : Sentence splitting + semantic chunking
- **Embedding** : text-embedding-3-large, via `LLMProviderPort` (couche 3)
- **Vector Store** : Qdrant (couche 2), via `VectorStorePort`
- **Recherche** : vectorielle dense uniquement (pas de sparse/BM25 aujourd'hui)
- **Reranking** : Cohere rerank v3
- **Evaluation** : RAGAS

## Architecture

```
[Document] → [Parser] → [Chunker] → [Embedding] → [Qdrant]
                                                     ↓
[Query] → [Embedding] → [Vector Search (Qdrant)] → [Reranking] → [Context Builder]
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

## Recherche vectorielle

Implémentation réelle : `src/genai_platform/adapters/vector_store/qdrant_store.py` (`QdrantVectorStore`,
adapter concret du port `VectorStorePort` défini dans `ports/vector_store.py`), orchestré par
`RAGPipeline` (`src/genai_platform/application/rag_pipeline.py`). Pas de recherche sparse/BM25 —
uniquement une recherche vectorielle dense sur Qdrant.

```python
class QdrantVectorStore:
    def __init__(self, url: str) -> None:
        self._client = AsyncQdrantClient(url=url)
        self._ready = False

    async def ensure_collection(self, collection: str, vector_size: int) -> None:
        # crée la collection Qdrant si absente ; _ready=False si la connexion échoue
        ...

    async def search(
        self, collection: str, query_vector: list[float], limit: int
    ) -> list[ScoredChunk]:
        if not self._ready:
            return []
        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
        )
        return [ScoredChunk(...) for r in results]
```

`RAGPipeline.query` embed la requête via `LLMProviderPort.embed`, appelle `VectorStorePort.search`,
et retourne une réponse statique « aucun document trouvé » si `vector_store.ready` est faux ou si
la recherche ne renvoie aucun résultat — pas de fallback vers une recherche par mots-clés.

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
- ❌ Pas de recherche sparse/mots-clés en complément du vectoriel → une requête avec des termes exacts (nom propre, référence, code produit) peut être mal servie si l'embedding ne capture pas bien ces tokens
