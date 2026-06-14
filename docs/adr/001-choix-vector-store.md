# ADR 001 — Choix du Vector Store

## Statut
Accepté

## Contexte
Nous avons besoin d'un vector store pour stocker et interroger les embeddings des documents dans le pipeline RAG.

## Options envisagées
- **Qdrant** : open source, performant, gRPC natif, clustering HA
- **Pinecone** : SaaS, managed, cher à volume
- **Weaviate** : open source, mais plus lourd (inclut un module d'embedding dont on n'a pas besoin)
- **Milvus** : très performant mais complexe à opérer (dépend de etcd, minio, etc.)

## Décision
Qdrant

## Raisons
- **Performance** : 2-3x plus rapide que Pinecone à volume égal
- **gRPC natif** : latence réduite par rapport à REST
- **Clustering simple** : sharding + replication sans dépendances externes
- **Snapshots intégrés** : backup/restore natifs
- **Open source** : pas de vendor lock-in, déploiement on-prem possible
- **Client Python mature** : bonne intégration avec LlamaIndex

## Conséquences
- ✅ Opérateur K8s disponible pour déploiement automatisé
- ✅ Coût fixe (pas de scaling coûteux à chaque query comme Pinecone)
- ❌ Opérations supplémentaires (backup, monitoring, scaling)
