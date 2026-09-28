import json,re,unicodedata,collections
d=json.load(open('prospection/all94.json'))
def n(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
MCO=re.compile(r"vendeu|vente|magasin|rayon|caisse|boutique|libre-service|commerce de detail|merchandis|manager de|responsable de (boutique|magasin|rayon|caisses|point de vente|departement)|gerant.*(magasin|commerce|superette)|epicerie|drive|e-commerce|chef de rayon|conseiller.*(vente|beaute)|adjoint.*(magasin|responsable)|directeur.*magasin|employe.*commerce")
NDRC=re.compile(r"commercia|technico-commercial|attache commercial|charge.*(clientele|affaires|client)|conseiller.*(clientele|client|commercial|immobilier|gestion de patrimoine|en assurance|financier)|negociateur|business develop|televend|teleconseil|teleprospect|telemarket|prospect|representant|agent commercial|account|chef de secteur|charge.*accueil en banque|delegue|courtier|souscripteur|chargee? de developpement|ingenieur commercial|vendeu.*(automobile|grossiste)|relation client")
EXCL=re.compile(r"formation|cfa |ecole|institut de formation|campus|academ")
BAD=re.compile(r"technicien.*apres-vente|atelier apres-vente|service apres-vente|smava|developpement (d'activites sportives|culturel|economique)|affaires (reglementaires|foncieres|btp)|^magasinier|drive|prospectus|escale|or, de metaux|depot-vente|ambulant")
rows=collections.OrderedDict()
for h in d:
    if h['sub_type']=='formation' or h.get('departement_code')!='94': continue
    labs=(h.get('rome_labels') or [])
    txt_l=[n(x) for x in labs]
    title=h.get('title') or ''
    if h['sub_type']!='recruteurs_lba': txt_l.append(n(title))
    sect=n(h.get('activity_sector'))
    mco=[l for l,t in zip(labs+[title],txt_l) if MCO.search(t) and not BAD.search(t) and not re.search(r'apres-vente',t)]
    ndrc=[l for l,t in zip(labs+[title],txt_l) if (NDRC.search(t) or 'conseiller client apres-vente' in t) and not BAD.search(t)]
    if 'pharmaceut' not in sect and re.search(r"commerce de detail|supermarche|hypermarche|superette|commerce d'alimentation",sect): mco=mco or ['(secteur commerce de détail)']
    if h['sub_type']!='recruteurs_lba':
        lvl=h.get('level') or ''
        if lvl and not re.search(r'BTS|Bac\b|Bac,',lvl): pass
    if not (mco or ndrc): continue
    org=h.get('organization_name') or title
    if h['sub_type']!='recruteurs_lba' and EXCL.search(n(org)): org_is_school=True
    else: org_is_school=False
    addr=h.get('address') or ''
    m=re.search(r'(\d{5})\s+(.*)$',addr)
    cp,ville=(m.group(1),m.group(2).title()) if m else ('','')
    fil='MCO + NDRC' if mco and ndrc else ('MCO' if mco else 'NDRC')
    slug=re.sub(r'[^a-z0-9]+','-',n(title)).strip('-')
    url=f"https://labonnealternance.apprentissage.beta.gouv.fr/emploi/{h['sub_type']}/{h['url_id']}/{slug}"
    typ={'recruteurs_lba':'Entreprise susceptible de recruter (candidature spontanée)','offres_emploi_lba':'Offre publiée sur La bonne alternance','offres_emploi_partenaires':'Offre partenaire (France Travail…)'}[h['sub_type']]
    siret=h['url_id'] if h['sub_type']=='recruteurs_lba' else ''
    rows[h['_id']]=dict(Entreprise=org,Filière=fil,Type=typ,Intitulé=title if h['sub_type']!='recruteurs_lba' else '',
        Métiers=' ; '.join(dict.fromkeys([x for x in mco+ndrc if not x.startswith('(')]))[:500],
        Secteur=h.get('activity_sector') or '',Adresse=addr,CP=cp,Ville=ville,SIRET=siret,
        Niveau=h.get('level') or '',Contrat=', '.join(h.get('contract_type') or []),
        Publication=(h.get('publication_date') or '')[:10] if h['sub_type']!='recruteurs_lba' else '',
        Organisme_école='Oui' if org_is_school else '',Pertinence=len(set(mco+ndrc)),Lien=url)
R=list(rows.values())
R.sort(key=lambda r:(r['Type'][0]!='O', r['Ville'], r['Entreprise']))
json.dump(R,open('prospection/result.json','w'),ensure_ascii=False)
print(len(R)); print(collections.Counter(r['Filière'] for r in R)); print(collections.Counter(r['Type'] for r in R))
print(collections.Counter(r['Ville'] for r in R).most_common(15))
