import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_catalog import canonical,export
class CatalogTests(unittest.TestCase):
 def test_same_portal_id_merges_alias_domains(self):
  rows=[{'title':'A','link':'https://www.fazwaz.com/property-sales/home-u123','price_usd':100000,'last_seen':'2026-09-01'},{'title':'Updated','link':'https://www.fazwaz.co.th/en/property-sales/home-u123','price_usd':110000,'last_seen':'2026-09-12'}]
  out,merged=export(rows,'bangkok','buy',{});self.assertEqual(merged,1);self.assertEqual(out[0]['title'],'Updated');self.assertEqual(len(out[0]['alternatives']),1)
 def test_distinct_query_ids_and_cities_stay_distinct(self):
  self.assertNotEqual(canonical('https://x.com/item?id=1'),canonical('https://x.com/item?id=2'))
  rows=[{'link':'https://x.com/1','price_usd':100000}];a,_=export(rows,'saigon','buy',{});b,_=export(rows,'bangkok','buy',{});self.assertNotEqual(a[0]['id'],b[0]['id'])
 def test_unknown_evidence_is_not_upgraded(self):
  out,_=export([{'link':'https://x.com/1','price_usd':100000}],'saigon','buy',{});self.assertEqual(out[0]['ownership'],'unknown');self.assertIsNone(out[0]['lastSeen'])
 def test_review_rows_are_flagged_and_never_replace_reviewed_rows(self):
  base=[{'title':'Reviewed','link':'https://x.com/1','price_usd':100000,'last_seen':'2026-09-01','score':90}]
  rev=[{'title':'Seen again','link':'https://x.com/1','price_usd':95000,'last_seen':'2026-09-15','_run':'2026-09-15','score':95},
       {'title':'Brand new','link':'https://x.com/2','price_usd':120000,'last_seen':'2026-09-15','_run':'2026-09-15','score':97,'review_group':'foreign_quota_stated'}]
  out,_=export(base,'bangkok','buy',{},rev);by={r['url']:r for r in out}
  old=by['https://x.com/1'];self.assertEqual(old['title'],'Reviewed');self.assertFalse(old.get('review',False));self.assertEqual(old['lastSeen'],'2026-09-15');self.assertEqual(old['price'],95000);self.assertIn('changed',old['notes'])
  new=by['https://x.com/2'];self.assertTrue(new['review']);self.assertLessEqual(new['baseScore'],80);self.assertEqual(new['ownership'],'stated')
 def test_geo_precision_is_carried_not_upgraded(self):
  import build_catalog as bc
  class G:
   def lookup(self,city,r):return (13.7,100.5,'district')
  bc.GEO=G();out,_=export([{'link':'https://x.com/9','price_usd':100000}],'bangkok','buy',{});bc.GEO=None
  self.assertEqual(out[0]['geo'],'district')
if __name__=='__main__':unittest.main()
