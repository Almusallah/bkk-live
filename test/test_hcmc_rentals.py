import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from hcmc_rental_rules import assess
from build_catalog import export
class RentalTests(unittest.TestCase):
 def row(self,**kw):
  return dict(city='saigon',rental_category='house',property_type='house',rent_vnd=17000000,rent_usd=650,rent_period='month',bedrooms=3,link='https://example.com/house',**kw)
 def test_inclusive_caps_and_true_bedroom_count(self):
  r=self.row();self.assertEqual(assess(r)[0],'match')
  self.assertEqual(assess(r|{'rent_vnd':17000001})[0],'rejected')
  self.assertEqual(assess(r|{'bedrooms':2})[0],'rejected')
  self.assertEqual(assess(r|{'bedrooms':None})[0],'needs_verification')
  self.assertEqual(assess(r|{'property_type':'apartment'})[0],'rejected')
 def test_expired_never_bypasses_budget_or_geography(self):
  r=self.row(listing_status='expired')
  self.assertEqual(assess(r)[0],'needs_verification')
  self.assertEqual(assess(r|{'rent_vnd':18000000})[0],'rejected')
  self.assertEqual(assess(r|{'city':'hanoi'})[0],'rejected')
 def test_office_requires_evidence_and_monthly_whole_quote(self):
  r=self.row()|{'rental_category':'office','rent_vnd':20000000,'office_character':'informal','office_use_evidence':'Advertised as small office'}
  self.assertEqual(assess(r)[0],'match')
  self.assertEqual(assess(r|{'office_use_evidence':None})[0],'needs_verification')
  self.assertEqual(assess(r|{'property_type':'office_tower'})[0],'rejected')
  self.assertEqual(assess(r|{'rent_period':'desk'})[0],'needs_verification')
 def test_villa_uncapped_but_style_must_be_evidenced(self):
  r=self.row()|{'rental_category':'modernist_villa','property_type':'villa','rent_vnd':500000000,'centrality':'central','bedrooms':1}
  self.assertEqual(assess(r)[0],'needs_verification')
  self.assertEqual(assess(r|{'modernist_evidence_status':'visual_review','modernist_evidence':'Documented photo features'})[0],'match')
 def test_dual_category_ids_and_vnd_refresh(self):
  r=self.row(last_seen='2026-10-05')
  office=r|{'rental_category':'office','office_character':'informal','office_use_evidence':'Small office'}
  out,_=export([r,office],'saigon','rent',{});self.assertEqual(len(out),2);self.assertNotEqual(out[0]['id'],out[1]['id'])
  out,_=export([r],'saigon','rent',{},[r|{'_run':'2026-10-12','last_seen':'2026-10-12','rent_vnd':16000000,'rent_usd':610}]);self.assertEqual(out[0]['localPrice'],16000000)
 def test_fee_overrun_and_invalid_numbers(self):
  self.assertEqual(assess(self.row(mandatory_fees_vnd=1000000))[0],'needs_verification')
  self.assertEqual(assess(self.row()|{'rent_vnd':float('nan')})[0],'needs_verification')
