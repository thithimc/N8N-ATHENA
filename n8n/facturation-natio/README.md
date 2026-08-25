# Migration Zapier → n8n : Facturation Natio (Typeform → Email)

Remplace le Zap « Typeform New Entry → Send Email » du formulaire
**Facturation natio** (form_id `AcyACmXB`) par le workflow
[`workflow.json`](./workflow.json).

```
Typeform Trigger ──▶ Preparer email ──▶ Telecharger la facture ──▶ Send Email (Gmail)
```

## Différences avec les formulaires « Facturation Campus »

- « Qui dépose » = service : Commercial, Finance, Marketing, Pédagogie, RH ;
- 5 variantes de « Type de facture (…) » selon le service (une seule est posée,
  le code prend celle qui a une réponse) ;
- champ **Entreprise** au lieu de « Commerçant » ;
- pas de « Compte débiteur ».

Corps du mail généré (exemple) :

> Bonjour,
>
> RH vient de déposer une nouvelle facture "Formation" datant du 2026-08-12 d'un montant de 1200,00 € chez CEGOS. Merci !

## Installation

Identique à [facturation-campus](../facturation-campus/README.md) :
importer `workflow.json`, assigner le credential **Typeform** (trigger +
« Telecharger la facture ») et **Gmail** (« Send Email »).

⚠️ **À compléter avant activation** — en tête du nœud « Preparer email » :
`TO`, `CC`, `SUBJECT` et `GREETING` sont pré-remplis avec les valeurs du Zap
campus 77 et marqués `TODO` : **recopier les valeurs réelles du Zap
« Facturation natio » avant de le couper.**

Puis : activer, tester une soumission (le mail part en double tant que le Zap
est actif), et désactiver le Zap dans Zapier.
