---
name: reel
description: Transforme des rushs vidéo en reel vertical 9:16 sous-titré (coupe des silences, sous-titres mot par mot, titre d'accroche), puis propose de le programmer sur les réseaux via Postiz. À utiliser quand l'utilisateur dit « fais-moi un reel », « monte ces rushs », « sous-titre cette vidéo », etc.
---

# Rushs → reel

Script : `plugkit-maison/reels/make_reel.py` (ffmpeg + faster-whisper, 100 % local et gratuit).

## Étapes

1. Vérifier les dépendances une fois : `ffmpeg -version` et `python3 -c "import faster_whisper"`.
   Si besoin : `pip install -r plugkit-maison/reels/requirements.txt`.
2. Demander (si l'utilisateur ne l'a pas dit) :
   - le ou les fichiers de rushs (dans l'ordre) ;
   - le cadrage : `crop` (plein écran, recadré au centre, idéal face caméra) ou `flou`
     (toute l'image gardée sur un fond flouté, idéal pour une vidéo horizontale/écran) ;
   - un titre d'accroche (facultatif, affiché 3,5 s en haut).
3. Lancer :
   ```bash
   python3 plugkit-maison/reels/make_reel.py <rush1> [rush2 ...] -o <sortie>.mp4 \
     --fond crop --accroche "<titre>" --modele small --srt
   ```
   Options utiles : `--pas-de-coupe` (garder les blancs), `--duree-silence 0.8` (couper moins),
   `--mots 2` (sous-titres plus courts), `--couleur "#00E5FF"`, `--modele medium` (plus précis, plus lent).
4. Relire le fichier `.ass` généré (`--srt`) : corriger les fautes de transcription (noms propres,
   noms d'écoles, sigles) directement dedans si besoin, puis relancer le rendu.
5. Extraire 2 images pour contrôle visuel :
   `ffmpeg -ss 1 -i <sortie>.mp4 -frames:v 1 apercu.png`.
6. Proposer une légende (accroche + 3 hashtags + CTA type « Commente GUIDE pour recevoir… »
   si une règle mot-clé existe dans le board Monday « Automations DM »).
7. Si l'utilisateur veut publier : utiliser le skill/CLI **Postiz** (`postiz upload` puis
   `postiz posts:create ... --settings '{"post_type":"post"}'`). Toujours demander la date/heure
   et confirmer avant de programmer.
