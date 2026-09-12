#!/usr/bin/env python3
"""Build a compact unified catalog from observed scanner records. No network or invented rows."""
import argparse,base64,hashlib,json,re
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
ROOT=Path(__file__).resolve().parents[1]
def canonical(link):
 u=urlsplit(link)
 if u.scheme not in ('https','http') or not u.hostname or u.username:return None
 host=u.hostname.lower().removeprefix('www.')
 if re.search(r'(^|\.)fazwaz\.(com|co\.th|vn)$',host):
  m=re.search(r'-u(\d+)(?:/|$)',u.path)
  if m:return 'fazwaz:'+m.group(1)
 q=urlencode(sorted((k,v) for k,v in parse_qsl(u.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')))
 return urlunsplit(('https',host,u.path.rstrip('/'),q,''))
def export(rows,city,mode,photos):
 records={};merged=0
 for r in rows:
  key=canonical(r.get('link',''))
  price=r.get('rent_usd') if mode=='rent' else r.get('price_usd')
  if not key or not isinstance(price,(int,float)) or price<=0:continue
  ident=hashlib.sha256(f'{city}:{mode}:{key}'.encode()).hexdigest()[:16]
  status=r.get('foreign_status',r.get('foreign_freehold','unknown'))
  ownership='stated' if status in ('foreign_eligible','foreign_freehold') else 'restricted' if status in ('local_only','leasehold_or_thai_only') else 'unknown'
  photo=photos.get(key) or r.get('image_url') or ''
  if photo and not (photo.startswith('https://') or photo.startswith('images/')):photo=''
  row={'id':ident,'city':city,'mode':mode,'title':r.get('title','Untitled listing'),'district':r.get('district') or 'Area not stated','position':r.get('position') or '',
       'price':price,'localPrice':r.get('rent_vnd',r.get('rent_thb')) if mode=='rent' else r.get('price_vnd',r.get('price_thb')),'currency':'VND' if city=='saigon' else 'THB',
       'area':r.get('sqm'),'beds':r.get('bedrooms'),'ownership':ownership,'image':photo,'url':r['link'],'source':r.get('source','Listing source'),
       'lastSeen':r.get('last_seen'),'firstSeen':r.get('first_seen'),'baseScore':r.get('base_score',r.get('score',0)),'notes':r.get('notes',''),
       'watchlist':r.get('watchlist',''),'suspect':bool(r.get('price_suspect')),'depositMonths':r.get('deposit_months'),'advanceMonths':r.get('advance_months'),
       'leaseMonths':r.get('min_lease_months'),'furnished':r.get('furnished'),'pets':r.get('pets'),'alternatives':[]}
  if ident in records:
   merged+=1;old=records[ident]
   if (row['lastSeen'] or '')>(old['lastSeen'] or ''):row['alternatives']=[old['url']]+old['alternatives'];records[ident]=row
   elif row['url']!=old['url']:old['alternatives'].append(row['url'])
  else:records[ident]=row
 return list(records.values()),merged

def main():
 p=argparse.ArgumentParser();p.add_argument('--workflows',type=Path,required=True);a=p.parse_args();out=ROOT/'docs';(out/'images').mkdir(exist_ok=True)
 photos={}
 # Extract existing embedded thumbnails once. Keep the mapping for repeat builds.
 cache=out/'data/photo-index.json'
 if cache.exists():photos=json.loads(cache.read_text())
 for filename in ('bangkok.html','rentals.html'):
  text=(out/filename).read_text();m=re.search(r'<script id="rows" type="application/json">(.*?)</script>',text,re.S)
  if not m:continue
  for r in json.loads(m.group(1)):
   image=r.get('img','');key=canonical(r.get('l',''))
   if not key or not image.startswith('data:image/'):continue
   header,encoded=image.split(',',1);blob=base64.b64decode(encoded);name=hashlib.sha256(blob).hexdigest()[:24]+('.png' if 'png' in header else '.jpg')
   path=out/'images'/name
   if not path.exists():path.write_bytes(blob)
   photos[key]='images/'+name
 cache.write_text(json.dumps(photos,separators=(',',':')))
 catalog=[]
 for city,mode,folder in [('saigon','buy','hcmc-property-research'),('bangkok','buy','bangkok-property-research'),('bangkok','rent','bangkok-rental-research')]:
  state=json.loads((a.workflows/folder/'state.json').read_text());rows,merged=export(state['rows'],city,mode,photos)
  data={'city':city,'mode':mode,'lastRun':state.get('last_run'),'rows':rows,'duplicatesMerged':merged,'status':'available'}
  file=f'{city}-{mode}.json';(out/'data'/file).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
  catalog.append({k:v for k,v in data.items() if k!='rows'}|{'count':len(rows),'file':file});print(city,mode,len(rows),'merged',merged)
 rental=a.workflows/'hcmc-rental-research/state.json'
 if rental.exists():
  state=json.loads(rental.read_text());rows,merged=export(state['rows'],'saigon','rent',photos)
  data={'city':'saigon','mode':'rent','lastRun':state.get('last_run'),'rows':rows,'duplicatesMerged':merged,'status':'available'}
 else:
  data={'city':'saigon','mode':'rent','lastRun':None,'rows':[],'duplicatesMerged':0,'status':'not-yet-scanned'}
 (out/'data/saigon-rent.json').write_text(json.dumps(data));catalog.append({k:v for k,v in data.items() if k!='rows'}|{'count':len(data['rows']),'file':'saigon-rent.json'})
 (out/'data/catalog.json').write_text(json.dumps(catalog))
if __name__=='__main__':main()
