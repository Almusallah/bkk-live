#!/usr/bin/env python3
"""Build a compact unified catalog from observed scanner records. No network or invented rows."""
import argparse,base64,hashlib,io,json,re,subprocess,sys
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
GEO=None
def load_geo(workspace):
 global GEO
 try:
  sys.path.insert(0,str(workspace/'scripts'));import geocode;GEO=geocode.Geo();print('geo cache:',len(GEO.urls),'urls',len(GEO.names),'names')
 except Exception as e:print('geo unavailable:',e)
def ownership_of(r):
 group=r.get('review_group')
 if group:return {'foreign_quota_stated':'stated','negative_or_alternative':'restricted'}.get(group,'unknown')
 status=r.get('foreign_status',r.get('foreign_freehold','unknown'))
 return 'stated' if status in ('foreign_eligible','foreign_freehold') else 'restricted' if status in ('local_only','leasehold_or_thai_only') else 'unknown'
def reviews(reports,folder):
 """New observations from completed draft runs (oldest first, so the latest observation wins). Not merged into any master."""
 out=[]
 for journal in sorted((reports/folder).glob('*/journal.json')):
  try:
   if json.loads(journal.read_text()).get('status')!='complete':continue
   state=json.loads((journal.parent/'candidate-state.json').read_text())
  except Exception:continue
  for r in state.get('review_candidates') or []:
   if not isinstance(r.get('rent_usd' if 'rental' in folder else 'price_usd'),(int,float)):continue
   out.append(r|{'_run':journal.parent.name})
 return out
def export(rows,city,mode,photos,review_rows=()):
 records={};merged=0;added=0;refreshed=0
 for r in rows:
  key=canonical(r.get('link',''))
  price=r.get('rent_usd') if mode=='rent' else r.get('price_usd')
  if not key or not isinstance(price,(int,float)) or price<=0:continue
  ident=hashlib.sha256(f'{city}:{mode}:{key}'.encode()).hexdigest()[:16]
  status=r.get('foreign_status',r.get('foreign_freehold','unknown'))
  ownership=ownership_of(r)
  photo=photos.get(key) or r.get('image_url') or ''
  if photo and not (photo.startswith('https://') or photo.startswith('images/')):photo=''
  row={'id':ident,'city':city,'mode':mode,'title':r.get('title','Untitled listing'),'district':r.get('district') or 'Area not stated','position':r.get('position') or '',
       'price':price,'localPrice':r.get('rent_vnd',r.get('rent_thb')) if mode=='rent' else r.get('price_vnd',r.get('price_thb')),'currency':'VND' if city=='saigon' else 'THB',
       'area':r.get('sqm'),'beds':r.get('bedrooms'),'ownership':ownership,'image':photo,'url':r['link'],'source':r.get('source','Listing source'),
       'lastSeen':r.get('last_seen'),'firstSeen':r.get('first_seen'),'baseScore':r.get('base_score',r.get('score',0)),'notes':r.get('notes',''),
       'watchlist':r.get('watchlist',''),'suspect':bool(r.get('price_suspect')),'depositMonths':r.get('deposit_months'),'advanceMonths':r.get('advance_months'),
       'leaseMonths':r.get('min_lease_months'),'furnished':r.get('furnished'),'pets':r.get('pets'),'alternatives':[]}
  geo=GEO.lookup(city,r) if GEO else None
  if geo:row|={'lat':round(geo[0],5),'lng':round(geo[1],5),'geo':geo[2]}
  if ident in records:
   merged+=1;old=records[ident]
   if (row['lastSeen'] or '')>(old['lastSeen'] or ''):row['alternatives']=[old['url']]+old['alternatives'];records[ident]=row
   elif row['url']!=old['url']:old['alternatives'].append(row['url'])
  else:records[ident]=row
 # Draft observations: exact-ID matches refresh date/price on the display copy only; unseen IDs are added as unverified.
 for r in review_rows:
  key=canonical(r.get('link',''));price=r.get('rent_usd') if mode=='rent' else r.get('price_usd')
  if not key:continue
  ident=hashlib.sha256(f'{city}:{mode}:{key}'.encode()).hexdigest()[:16];seen=r.get('last_seen') or r['_run']
  old=records.get(ident)
  if old and not old.get('review'):
   if seen>(old['lastSeen'] or ''):
    if abs(price-old['price'])>=1:old['notes']=(old.get('notes') or '')+f" | Asking changed from USD {old['price']:,.0f} to USD {price:,.0f} (observed {seen}, unreviewed)."
    old['lastSeen']=seen;old['price']=round(price,2);old['localPrice']=r.get('rent_thb') if mode=='rent' else r.get('price_thb',old['localPrice']);refreshed+=1
   continue
  export_one=export([r],city,mode,photos)[0]
  if not export_one:continue
  row=export_one[0];row['review']=True;row['lastSeen']=seen;row['firstSeen']=r.get('first_seen') or seen
  row['baseScore']=min(row['baseScore'] or 0,80)  # unreviewed rows never outrank reviewed picks on score alone
  if not old:added+=1
  records[ident]=row
 if review_rows:print(f'  {city} {mode}: +{added} new unverified, {refreshed} re-observed')
 return list(records.values()),merged

def localise_images(rows,out):
 """Hotlink-protected thumbnails (e.g. housenow's Next.js proxy needs a same-origin Referer): fetch once, shrink, serve from images/."""
 try:from PIL import Image
 except ImportError:return 0
 n=0
 for row in rows:
  img=row.get('image') or ''
  if not img.startswith('https://') :continue
  name=hashlib.sha256(img.encode()).hexdigest()[:24]+'.jpg';path=out/'images'/name
  if not path.exists():
   ref=urlsplit(row['url']);referer=f'{ref.scheme}://{ref.netloc}/'
   src=img
   if '/_next/image' in src:  # Next.js proxies reject bare requests (400); fetch the original instead
    src=dict(parse_qsl(urlsplit(src).query)).get('url',src)
    if 'firebasestorage.googleapis.com' in src and 'alt=media' not in src:src+=('&' if '?' in src else '?')+'alt=media'
   blob=subprocess.run(['curl','-sL','--max-time','20','-e',referer,'-A','Mozilla/5.0',src],capture_output=True).stdout
   try:
    im=Image.open(io.BytesIO(blob)).convert('RGB');im.thumbnail((520,360));im.save(path,'JPEG',quality=78,optimize=True)
   except Exception:continue
  row['image']='images/'+name;n+=1
 return n

def main():
 p=argparse.ArgumentParser();p.add_argument('--workflows',type=Path,required=True);p.add_argument('--reports',type=Path);p.add_argument('--workspace',type=Path,default=ROOT.parents[1]);a=p.parse_args();out=ROOT/'docs';(out/'images').mkdir(exist_ok=True)
 load_geo(a.workspace)
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
  state=json.loads((a.workflows/folder/'state.json').read_text());rows,merged=export(state['rows'],city,mode,photos,reviews(a.reports,folder) if a.reports else ())
  if city=='saigon':print('  localised saigon thumbnails:',localise_images(rows,out))
  data={'city':city,'mode':mode,'lastRun':max([state.get('last_run') or '']+[r['lastSeen'] or '' for r in rows if r.get('review')]) or None,'rows':rows,'duplicatesMerged':merged,'status':'available','mapped':sum(1 for r in rows if r.get('geo') and r['geo']!='district'),'unverified':sum(1 for r in rows if r.get('review'))}
  file=f'{city}-{mode}.json';(out/'data'/file).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
  catalog.append({k:v for k,v in data.items() if k!='rows'}|{'count':len(rows),'file':file});print(city,mode,len(rows),'merged',merged,'mapped',data['mapped'],'unverified',data['unverified'])
 rental=a.workflows/'hcmc-rental-research/state.json'
 if rental.exists():
  state=json.loads(rental.read_text());rows,merged=export(state['rows'],'saigon','rent',photos)
  data={'city':'saigon','mode':'rent','lastRun':state.get('last_run'),'rows':rows,'duplicatesMerged':merged,'status':'available'}
 else:
  data={'city':'saigon','mode':'rent','lastRun':None,'rows':[],'duplicatesMerged':0,'status':'not-yet-scanned'}
 (out/'data/saigon-rent.json').write_text(json.dumps(data));catalog.append({k:v for k,v in data.items() if k!='rows'}|{'count':len(data['rows']),'file':'saigon-rent.json'})
 (out/'data/catalog.json').write_text(json.dumps(catalog))
if __name__=='__main__':main()
