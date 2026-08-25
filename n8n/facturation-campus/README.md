# Migration Zapier → n8n : Facturation Campus (Typeform → Email)

Remplace les **9 Zaps** « Typeform New Entry → Send Email » par **un seul workflow n8n** ([`workflow.json`](./workflow.json)).

## Ce que fait le workflow

Un salarié dépose une facture via un des 9 Typeform « Facturation Campus » →
un email en texte brut est envoyé (comme dans Zapier) avec la facture (PDF) en pièce jointe.

```
9 × Typeform Trigger ──▶ Preparer email ──▶ Telecharger la facture ──▶ Send Email (Gmail)
   (1 par campus)         (Code : corps du     (HTTP + auth Typeform,     (to/cc/objet par
                           mail + config        car les fichiers          campus, PJ = facture)
                           par campus)          Typeform sont privés)
```

Corps du mail reproduit à l'identique du Zap :

> Hello Samia,
>
> Direction vient de déposer une nouvelle facture "Achat centre" datant du 2026-07-24 d'un montant de 28,49 € chez AMAZON à débiter du Compte directeur de centre - 77. Merci !

## Les 9 formulaires couverts

| Campus | Formulaire Typeform | form_id |
|---|---|---|
| 06 | Facturation Campus 06 | `GoYjt7QL` |
| 13 | Facturation Campus 13 | `wWiTmFbt` |
| 34 | Facturation Campus 34 | `Ei4mhN30` |
| 66 | Facturation Campus 66 | `prq60cLp` |
| 69 | Facturation Campus 69 | `ISq3V0un` |
| 77 | Facturation Campus 77 | `O6cupDZd` |
| 91 | Facturation Campus 91 | `M6EyJ8VW` |
| 93 | Facturation Campus 93 | `zKkRmCZi` |
| 94 | Facturation Campus 94 | `STqpGfRz` |

Les 9 formulaires ont les mêmes questions (Qui dépose, Compte débiteur, Type de
facture, Type de facture (Market), Commerçant, Date de la facture, Montant,
Facture). Le code repère les réponses par **intitulé de question** (fourni dans
le payload du webhook), donc pas besoin de gérer les IDs de champs qui diffèrent
d'un formulaire à l'autre.

## Installation

### 1. Créer les credentials dans n8n

- **Typeform API** : token personnel à générer sur
  [admin.typeform.com](https://admin.typeform.com) → *Settings → Personal tokens*
  (scopes : `forms:read`, `webhooks:read`, `webhooks:write`, `responses:read`).
  Utilisé 2 fois : par les triggers (création des webhooks) et par le nœud
  « Telecharger la facture » (les fichiers uploadés sur Typeform ne sont pas publics).
- **Gmail OAuth2** : avec le compte **thibaud@athena-bs.fr** (l'expéditeur des Zaps).

### 2. Importer le workflow

n8n → *Workflows → Import from File* → `workflow.json`, puis assigner :
- le credential **Typeform** sur les 9 nœuds trigger **et** sur « Telecharger la facture » ;
- le credential **Gmail** sur « Send Email ».

### 3. ⚠️ Compléter la configuration des destinataires

Ouvrir le nœud **« Preparer email »** : l'objet `CAMPUS` en tête du code contient
`to`, `cc`, `subject` et `greeting` (prénom du « Hello … ») pour chaque campus.

**Seule la ligne du campus 77 est reprise du Zap d'origine** (to : samia@athena-bs.fr,
cc : elodie@athena-bs.fr + lisa@athena-bs.fr, objet « Dépôt de facture - CSM »).
Les 8 autres lignes sont pré-remplies avec les mêmes valeurs et marquées `TODO` :
**recopier les To/Cc/Objet de chacun des 8 autres Zaps avant de les couper.**
Vérifier aussi l'orthographe de l'adresse `samia@athena-bs.fr` (peu lisible sur la capture du Zap).

### 4. Tester puis basculer

1. Activer le workflow n8n (les webhooks Typeform sont créés automatiquement).
2. Soumettre un test sur un formulaire (ex. Campus 77) et vérifier l'email reçu
   (destinataires, corps, pièce jointe).
   ⚠️ Tant que le Zap correspondant est encore actif, l'email partira **en double**
   (Zapier + n8n) : c'est normal pendant le test.
3. Une fois validé : **désactiver les 9 Zaps dans Zapier** (ce qui supprime leurs
   webhooks Typeform).

## Notes

- L'email part en texte brut (`Body type: plain` dans Zapier), sans la signature
  « sent by n8n » (`appendAttribution: false`).
- Seule une des deux questions « Type de facture » / « Type de facture (Market) »
  est posée selon le compte débiteur choisi (logique du formulaire) ; comme dans
  Zapier, les deux sont concaténées, l'une étant vide.
- La date est envoyée au format brut Typeform (`AAAA-MM-JJ`), comme dans Zapier.
- Si un jour un 10ᵉ campus est créé : dupliquer un nœud trigger avec le nouveau
  `form_id` et ajouter une ligne dans `CAMPUS`.
