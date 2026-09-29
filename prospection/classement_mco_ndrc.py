import json,re,unicodedata,collections
import os,math
# Usage : DEPT=77 CENTRE="48.8528,2.6031" python3 prospection/classement_mco_ndrc.py
DEPT=os.environ.get('DEPT','94')
CENTRE=[float(x) for x in os.environ['CENTRE'].split(',')] if os.environ.get('CENTRE') else None
def dist_km(h):
    c=(h.get('location') or {}).get('coordinates')
    if not CENTRE or not c: return ''
    la1,lo1,la2,lo2=map(math.radians,(CENTRE[0],CENTRE[1],c[1],c[0]))
    a=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return round(2*6371*math.asin(math.sqrt(a)),1)
d=json.load(open(f'prospection/all{DEPT}.json'))
def n(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
MCO=re.compile(r"vendeu|vente|magasin|rayon|caisse|boutique|libre-service|commerce de detail|merchandis|manager de|responsable de (boutique|magasin|rayon|caisses|point de vente|departement)|gerant.*(magasin|commerce|superette)|epicerie|drive|e-commerce|chef de rayon|conseiller.*(vente|beaute)|adjoint.*(magasin|responsable (de )?(magasin|boutique|rayon))|directeur.*magasin|employe.*commerce")
NDRC=re.compile(r"commercia|technico-commercial|attache commercial|charge.*(clientele|affaires|client)|conseiller.*(clientele|client|commercial|immobilier|gestion de patrimoine|en assurance|financier)|negociateur|business develop|televend|teleconseil|teleprospect|telemarket|prospect|representant|agent commercial|account|chef de secteur|charge.*accueil en banque|delegue|courtier|souscripteur|chargee? de developpement|ingenieur commercial|vendeu.*(automobile|grossiste)|relation client")
EXCL=re.compile(r"formation|cfa |ecole|institut de formation|campus|academ")
BAD=re.compile(r"technicien.*apres-vente|atelier apres-vente|service apres-vente|smava|developpement (d'activites sportives|culturel|economique)|affaires (reglementaires|foncieres|btp)|^magasinier|drive|prospectus|escale|or, de metaux|depot-vente|ambulant")

CATS=[
 ('Commerce de gros / B2B', r"commerce de gros|intermediaires.*commerce|centrales? d'achat"),
 ('Restauration', r"restauration|debits? de boissons|traiteur"),
 ('Grande distribution & supermarchés', r"supermarche|hypermarche|superette|commerce d'alimentation generale|multi-commerces|magasin non specialise"),
 ('Boulangerie & métiers de bouche', r"boulangerie|patisserie|pain|viandes|poissons|fruits et legumes|boissons en magasin|alimentaires? (en magasin|sur eventaires)|confiserie"),
 ('Mode, chaussures & accessoires', r"habillement|chaussure|maroquinerie|textiles|bijouterie|horlogerie"),
 ('Beauté, santé & parfumerie', r"parfumerie|beaute|pharmaceut|articles medicaux"),
 ('Maison, bricolage & jardin', r"meubles|equipements du foyer|quincaillerie|tapis|fleurs|plantes"),
 ('High-tech, électroménager & télécoms', r"electromenager|telecommunication|ordinateurs|audio et video|informatique|logiciels|portails internet|traitement de donnees|equipements de communication"),
 ('Sport, loisirs & culture', r"sport|jeux|jouets|livres|journaux|papeterie|edition|spectacle|artistique|photograph|agences de presse"),
 ('Automobile & mobilité', r"vehicules|automobile|motocycles|carburants|camions"),
 ('Banque, crédit & assurance', r"intermediations monetaires|credit|assurance|services financiers|retraites|securite sociale|recouvrement|evaluation des risques"),
 ('Immobilier', r"immobili|immeubles|location de (terrains|logements)|geometres"),
 ('Vente à distance & e-commerce', r"vente a distance"),
 ('Tourisme & transport', r"voyage|voyagistes|transports? aerien"),
 ('La Poste & services publics', r"activites de poste|administration publique|organisations"),
 ('Services aux entreprises, conseil & communication', r"soutien aux entreprises|conseil|relations publiques|publicite|etudes de marche|centres d'appels|services administratifs|sieges sociaux|holding|ressources humaines|juridiques|scientifiques|films"),
 ('Autres commerces de détail', r"commerces? de detail|biens d'occasion"),
 ('Industrie & énergie', r"fabrication|distribution de combustibles|commerce d'electricite|eaux usees|desinfection"),
]
TITLE_CATS=[('Restauration',r"restaura|serveu|equipier|elior"),('Mode, chaussures & accessoires',r"pret-a-porter|habillement"),('High-tech, électroménager & télécoms',r"high-tech|informatique"),('Boulangerie & métiers de bouche',r"produits de la mer|boulang"),('Grande distribution & supermarchés',r"carrefour|auchan|leclerc|intermarche|monoprix|franprix|lidl|rayon|caisse"),('Banque, crédit & assurance',r"banque|bancaire|assurance"),('Immobilier',r"immobili"),('Automobile & mobilité',r"automobile|vehicule")]
def categorie(sect,texte):
    for c,p in CATS:
        if re.search(p,sect): return c
    for c,p in TITLE_CATS:
        if re.search(p,texte): return c
    return 'Non précisé' if not sect else 'Autres'
rows=collections.OrderedDict()
for h in d:
    if h['sub_type']=='formation' or h.get('departement_code')!=DEPT: continue
    labs=(h.get('rome_labels') or [])
    offre=h['sub_type']!='recruteurs_lba'
    if offre: labs=[]  # pour une offre, seul l'intitulé compte (les métiers ROME associés sont trop larges)
    txt_l=[n(x) for x in labs]
    title=h.get('title') or ''
    if h['sub_type']!='recruteurs_lba': txt_l.append(n(title))
    sect=n(h.get('activity_sector'))
    mco=[l for l,t in zip(labs+[title],txt_l) if MCO.search(t) and not BAD.search(t) and not re.search(r'apres-vente',t)]
    ndrc=[l for l,t in zip(labs+[title],txt_l) if (NDRC.search(t) or 'conseiller client apres-vente' in t) and not BAD.search(t)]
    if not offre and 'pharmaceut' not in sect and re.search(r"commerce de detail|supermarche|hypermarche|superette|commerce d'alimentation",sect): mco=mco or ['(secteur commerce de détail)']
    if h['sub_type']!='recruteurs_lba':
        lvl=h.get('level') or ''
        if lvl and not re.search(r'BTS|Bac\b|Bac,',lvl): pass
    if not offre and re.search(r"restauration|debits? de boissons",sect): mco=mco or ['(secteur restauration)']
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
    rows[h['_id']]=dict(Entreprise=org,Catégorie=categorie(sect,n(org+' '+title+' '+' '.join(labs))),Filière=fil,Type=typ,Intitulé=title if h['sub_type']!='recruteurs_lba' else '',
        Métiers=' ; '.join(dict.fromkeys([x for x in mco+ndrc if not x.startswith('(')]))[:500],
        Secteur=h.get('activity_sector') or '',Adresse=addr,CP=cp,Ville=ville,SIRET=siret,
        Niveau=h.get('level') or '',Contrat=', '.join(h.get('contract_type') or []),
        Publication=(h.get('publication_date') or '')[:10] if h['sub_type']!='recruteurs_lba' else '',
        Organisme_école='Oui' if org_is_school else '',Distance_km=dist_km(h),Pertinence=len(set(mco+ndrc)),Lien=url)
R=list(rows.values())
R.sort(key=lambda r:(r['Type'][0]!='O', r['Ville'], r['Entreprise']))
json.dump(R,open(f'prospection/result{DEPT}.json','w'),ensure_ascii=False)
print(len(R)); print(collections.Counter(r['Filière'] for r in R)); print(collections.Counter(r['Type'] for r in R))
print(collections.Counter(r['Ville'] for r in R).most_common(15))
