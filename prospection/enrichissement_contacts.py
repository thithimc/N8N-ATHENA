# Enrichit result{DEPT}.json avec les contacts publics :
#  - page La bonne alternance : téléphone, candidature par email possible, lien pour postuler, SIRET des offres
#  - registre des entreprises (recherche-entreprises.api.gouv.fr) : dirigeants, effectif, nombre d'établissements
# Usage : DEPT=77 python3 prospection/enrichissement_contacts.py
import json,os,re,time,urllib.request,urllib.error,html
from concurrent.futures import ThreadPoolExecutor

DEPT=os.environ.get('DEPT','94')
CACHE_LBA='prospection/cache_lba.json'
CACHE_RE='prospection/cache_registre.json'
TRANCHES={'00':'0 salarié','01':'1-2','02':'3-5','03':'6-9','11':'10-19','12':'20-49','21':'50-99','22':'100-199','31':'200-249','32':'250-499','41':'500-999','42':'1000-1999','51':'2000-4999','52':'5000-9999','53':'10000+'}

def load(p):
    try: return json.load(open(p))
    except Exception: return {}
def get(url,tries=10):
    for t in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'prospection-alternance'}),timeout=40).read().decode()
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(1+t)
        except Exception: time.sleep(1+t)
    return None

def contact_lba(url):
    h=get(url)
    if h is None: return {}
    h=h.replace('\\"','"')
    out={}
    m=re.search(r'"contact":(\{"email":"[^"]*","hasEmail":(true|false),"phone":(null|"[^"]*"),"url":"([^"]*)"\}|\{"hasEmail":(true|false),"phone":(null|"[^"]*")\})',h)
    if m:
        out['hasEmail']=(m.group(2) or m.group(5))=='true'
        ph=m.group(3) or m.group(6)
        out['phone']=ph.strip('"') if ph and ph!='null' else ''
        u=m.group(4) or ''
        out['url']=html.unescape(u.encode().decode('unicode_escape')) if u and 'labonnealternance' not in u else ''
    s=re.search(r'"siret":"(\d{14})"',h)
    if s: out['siret']=s.group(1)
    return out

def registre(siren):
    t=get(f'https://recherche-entreprises.api.gouv.fr/search?q={siren}&per_page=1')
    if t is None: return None
    res=[r for r in json.loads(t).get('results',[]) if r.get('siren')==siren]
    if not res: return {}
    r=res[0]
    dirs=[]
    for d in r.get('dirigeants') or []:
        if 'commissaire' in (d.get('qualite') or '').lower(): continue
        if d.get('type_dirigeant')=='personne physique':
            nom=' '.join(x for x in [(d.get('prenoms') or '').split(' ')[0].title(),(d.get('nom') or '').upper()] if x)
        else:
            nom=d.get('denomination') or ''
        if nom: dirs.append(f"{nom} ({d.get('qualite') or 'dirigeant'})")
    return {'dirigeants':dirs,'nb_etab':r.get('nombre_etablissements_ouverts'),
            'effectif':TRANCHES.get(r.get('tranche_effectif_salarie') or '',''),
            'nom_legal':r.get('nom_complet') or ''}

R=json.load(open(f'prospection/result{DEPT}.json'))
cl=load(CACHE_LBA); cr=load(CACHE_RE)
todo=[r['Lien'] for r in R if r['Lien'] not in cl]
with ThreadPoolExecutor(4) as ex:
    for i,(u,v) in enumerate(zip(todo,ex.map(contact_lba,todo))):
        cl[u]=v
        if i%100==0: json.dump(cl,open(CACHE_LBA,'w')); print('lba',i,len(todo),flush=True)
json.dump(cl,open(CACHE_LBA,'w'))
sirens=sorted({(r['SIRET'] or cl[r['Lien']].get('siret',''))[:9] for r in R} - {''})
todo=[s for s in sirens if cr.get(s) is None]
with ThreadPoolExecutor(5) as ex:
    for i,(sn,v) in enumerate(zip(todo,ex.map(registre,todo))):
        cr[sn]=v
        if i%100==0: json.dump(cr,open(CACHE_RE,'w')); print('registre',i,len(todo),flush=True)
json.dump(cr,open(CACHE_RE,'w'))

for r in R:
    c=cl.get(r['Lien']) or {}
    siret=r['SIRET'] or c.get('siret','')
    g=cr.get(siret[:9]) or {}
    r['SIRET']=siret
    r['Téléphone']=c.get('phone','')
    r['Candidature_email']='Oui (via le bouton « J\'envoie ma candidature » du lien)' if c.get('hasEmail') else ''
    r['Lien_candidature']=c.get('url','')
    r['Dirigeants']=' ; '.join(g.get('dirigeants') or [])
    r['Effectif']=g.get('effectif','')
    nb=g.get('nb_etab')
    r['Nb_établissements']=nb if nb is not None else ''
    r['Structure']=('Grand réseau / enseigne : viser le responsable du point de vente' if nb and nb>=20 else
                    'Réseau moyen' if nb and nb>=5 else
                    'Indépendant / PME : le dirigeant recrute souvent lui-même' if nb else '')
json.dump(R,open(f'prospection/result{DEPT}.json','w'),ensure_ascii=False)
print('ok',DEPT,sum(bool(r['Dirigeants']) for r in R),'avec dirigeant /',len(R),
      sum(bool(r['Téléphone']) for r in R),'avec téléphone')
