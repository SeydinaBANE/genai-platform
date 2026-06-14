# ADR 004 — Stratégie de Déploiement

## Statut
Accepté

## Contexte
Nous devons déployer la plateforme avec zéro temps d'arrêt et capacité de rollback immédiat.

## Options envisagées
- **Blue/Green** : deux environnements complets, bascule instantanée
- **Canary** : déploiement progressif, 1% → 10% → 100%
- **Rolling update** : pods remplacés un par un, pas d'isolation
- **Recreate** : arrêt puis redémarrage, temps d'arrêt

## Décision
Blue/Green pour production, Rolling update pour staging

## Raisons
- **Rollback instantané** : basculer le trafic vers l'ancien environnement
- **Isolation totale** : le nouvel environnement peut être testé avant bascule
- **Smoke tests possibles** : tester la nouvelle version AVANT de servir le trafic
- **Zéro downtime** : garantie pendant la bascule
- **K8s native** : deux services, un ingress, bascule par label selector

## Conséquences
- ✅ Rollback en < 30s (changement de label)
- ✅ Tests de validation sur l'environnement inactif
- ❌ 2x la consommation de ressources pendant le déploiement
- ❌ Pas de progressive exposure (tout le trafic bascule d'un coup)

## Mitigations
- Pour réduire le surcoût ressources, on scale down l'environnement inactif à 1 replica
- Pour le canary, on utilise des feature flags pour exposer progressivement les features
