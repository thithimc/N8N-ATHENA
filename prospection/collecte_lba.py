import json,urllib.request,time,os
# Usage : DEPT=77 python3 prospection/collecte_lba.py
DEPT=os.environ.get('DEPT','94')
B="https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/search?hitsPerPage=100&admin_area=departement:"+DEPT+"&page="
out=[]
for p in range(0,300):
    for t in range(4):
        try:
            d=json.load(urllib.request.urlopen(B+str(p),timeout=60)); break
        except Exception as e: print(p,e); time.sleep(2**t)
    hs=d.get('hits',[]); 
    if not hs: break
    out+=hs; time.sleep(0.3)
json.dump(out,open(f'prospection/all{DEPT}.json','w'),ensure_ascii=False)
print(len(out), len({h['_id'] for h in out}))

