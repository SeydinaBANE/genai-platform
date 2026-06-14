# Couche 2 — Data & Vector Store

## Objectif
Ingérer, transformer et stocker les données pour le pipeline RAG, avec gestion du cycle de vie et lineage.

## Stack
- **Ingestion** : Airbyte (connecteurs SaaS/DB/API)
- **Transformation** : dbt (normalisation, cleaning)
- **Vector Store** : Qdrant (cluster HA, sharding, replication)
- **Document Store** : PostgreSQL (métadonnées, chunks)
- **Embedding** : via LLM Gateway (couche 3)

## Architecture

```
[Sources] → Airbyte → dbt → Qdrant + PostgreSQL
                                     ↓
                            [Hybrid Search API]
                                     ↓
                              [RAG Pipeline]
```

## Bonnes pratiques senior — Qdrant

```python
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    OptimizersConfigDiff,
    WalConfigDiff,
)

client = QdrantClient(url="https://qdrant.internal:6333", prefer_grpc=True)

client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(
        size=1536,
        distance=Distance.COSINE,
        hnsw_config=HnswConfigDiff(
            m=32,
            ef_construct=200,
            full_scan_threshold=10000,
        ),
    ),
    optimizers_config=OptimizersConfigDiff(
        indexing_threshold=50000,
        memmap_threshold=20000,
        default_segment_number=6,
    ),
    wal_config=WalConfigDiff(wal_capacity_mb=1024),
    shard_number=3,
    replication_factor=2,
)
```

Règles :
- **Sharding + Replication** : shard_number >= 3, replication_factor >= 2
- **HNSW tuning** : m=32, ef_construct=200 pour un bon ratio précision/vitesse
- **Prefer gRPC** : beaucoup plus rapide que REST pour les batchs
- **Snapshot réguliers** : backup automatiques vers S3/GCS
- **WAL tuning** : wal_capacity_mb adapté au volume d'écriture

## Bonnes pratiques senior — Data Pipeline

```makefile
data-ingest: ## Ingère les données depuis Airbyte
    airbyte-connector run --config config/sources.yaml

data-transform: ## Applique les transformations dbt
    dbt run --profile genai --target prod

data-test: ## Valide la qualité des données
    dbt test --profile genai --target prod

data-backup: ## Snapshot Qdrant
    curl -X POST 'http://qdrant:6333/collections/documents/snapshots'

data-restore: ## Restaure un snapshot
    curl -X POST 'http://qdrant:6333/collections/documents/snapshots/restore' \
      -H 'Content-Type: application/json' \
      -d '{"location": "s3://backups/qdrant/snapshot-2025-01-01.snapshot"}'
```

## Sécurité
- **Encryption at rest** : chiffrement des volumes Qdrant + PostgreSQL
- **Encryption in transit** : TLS obligatoire entre tous les services
- **Network isolation** : cluster Qdrant accessible uniquement depuis le service mesh
- **Data retention** : TTL configurable par collection
- **PII anonymization** : avant ingestion dans Qdrant

## Monitoring
- **Qdrant** : nombre de points, segments, WAL size, latence search/index
- **Airbyte** : sync success rate, lag, volume
- **dbt** : freshness, test failures, lineage

## Runbook
```bash
curl -s http://qdrant:6333/collections | jq '.result | length'
curl -s http://qdrant:6333/collections/documents | jq '.result.points_count'
python -c "
from qdrant_client import QdrantClient
c = QdrantClient('http://qdrant:6333')
print(c.get_collection('documents'))
"
```

## Pièges à éviter
- ❌ Sharding insuffisant → goulot d'étranglement sur un seul nœud
- ❌ Pas de snapshot → perte de données assurée en cas de corruption
- ❌ HNSW par défaut → performances dégradées sur des volumes > 1M
- ❌ Synchronous embedding → bottleneck, utiliser du batch async
