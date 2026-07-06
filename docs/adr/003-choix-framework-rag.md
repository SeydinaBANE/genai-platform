# ADR 003 — Choix du Framework RAG

## Statut
Amendée — décision initiale non appliquée telle quelle (voir Note de mise à jour)

## Note de mise à jour
La décision ci-dessous de choisir LlamaIndex n'a finalement pas été implémentée. Le pipeline RAG réel
(`src/genai_platform/application/rag_pipeline.py`) est un pipeline maison : chunking et reranking
custom (`domain/chunking.py`, `domain/reranking.py`), recherche vectorielle Qdrant pure — pas de
sparse/BM25, pas de hybrid search — le tout orchestré derrière des ports (`LLMProviderPort`,
`VectorStorePort`) suite au passage à une architecture hexagonale. `llama-index` reste une
dépendance déclarée mais inutilisée. Le raisonnement historique ci-dessous est conservé tel quel
pour mémoire, mais ne décrit pas l'implémentation actuelle.

## Contexte
Nous avons besoin d'un framework pour implémenter le pipeline RAG : ingestion, chunking, retrieval, generation.

## Options envisagées
- **LlamaIndex** : mature, flexible, nombreuses intégrations
- **LangChain** : très utilisé mais API instable, trop d'abstraction
- **Custom** : contrôle total mais réinvente la roue
- **Haystack** : bon mais moins d'intégrations vector stores

## Décision
LlamaIndex

## Raisons
- **API stable** : contrairement à LangChain qui casse tout à chaque release
- **Flexibilité** : on peut remplacer chaque composant (embedding, retrieval, reranking)
- **Qdrant integration** : native, bien maintenue
- **RAGAS integration** : évaluation intégrée
- **Community** : large, documentation de qualité
- **Performances** : plus rapide que LangChain sur les benchmarks

## Conséquences
- ✅ Pipeline RAG modulaire, testable composant par composant
- ✅ Documentation riche pour l'équipe
- ❌ Nécessite de comprendre les abstractions LlamaIndex
