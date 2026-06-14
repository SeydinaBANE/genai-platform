# ADR 003 — Choix du Framework RAG

## Statut
Accepté

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
