import json,urllib.request,time,ssl
B="https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/search?hitsPerPage=100&admin_area=departement:94&page="
out=[]
for p in range(0,60):
    for t in range(4):
        try:
            d=json.load(urllib.request.urlopen(B+str(p),timeout=60)); break
        except Exception as e: print(p,e); time.sleep(2**t)
    hs=d.get('hits',[]); 
    if not hs: break
    out+=hs; time.sleep(0.3)
json.dump(out,open('prospection/all94.json','w'),ensure_ascii=False)
print(len(out), len({h['_id'] for h in out}))

