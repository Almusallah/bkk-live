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
if __name__=='__main__':unittest.main()
