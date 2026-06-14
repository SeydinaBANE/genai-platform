## Description

<!-- Décrivez le changement et motivez-le. -->

## Type de changement

- [ ] Bug fix
- [ ] Nouvelle fonctionnalité
- [ ] Breaking change
- [ ] Documentation
- [ ] Infrastructure / CI

## Checklist senior

### Qualité
- [ ] `make lint` — zéro erreur
- [ ] `make typecheck` — zéro erreur
- [ ] `make test` — tous verts
- [ ] `make precommit-all` — passe

### Sécurité
- [ ] Aucun secret hardcodé (API key, password, token)
- [ ] Aucune donnée sensible dans les logs
- [ ] Les entrées utilisateur sont validées / sanitizées
- [ ] Les permissions sont vérifiées

### Docker
- [ ] `docker build` réussit
- [ ] Image basée sur une image distroless/slim
- [ ] Utilisateur non-root configuré
- [ ] Multi-stage build si applicable

### Production
- [ ] Migration DB testée (rollback inclus)
- [ ] Monitoring / alerting mis à jour
- [ ] Documentation mise à jour
- [ ] Changement backward compatible (ou version bump)

## Tests effectués

<!-- Décrivez les tests manuels ou automatisés. -->

## Screenshots / Logs

<!-- Si applicable. -->

## Liens

- Ticket : #[issue]
- Déploiement : <!-- lien vers le déploiement staging -->
