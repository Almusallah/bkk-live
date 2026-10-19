import unittest,sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from hcmc_rental_rules import assess
from build_catalog import export,reviews
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
  r=self.row()|{'rental_category':'office','rent_vnd':10000000,'district':'District 1','sqm':55,'area_basis':'usable','workstations':6,'workspace_evidence':'Measured six-desk layout','office_character':'informal','office_use_evidence':'Advertised as small office'}
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
  office=r|{'rental_category':'office','rent_vnd':10000000,'district':'District 3','sqm':50,'office_character':'informal','office_use_evidence':'Small office'}
  out,_=export([r,office],'saigon','rent',{});self.assertEqual(len(out),2);self.assertNotEqual(out[0]['id'],out[1]['id'])
  out,_=export([r],'saigon','rent',{},[r|{'_run':'2026-10-12','last_seen':'2026-10-12','rent_vnd':16000000,'rent_usd':610}]);self.assertEqual(out[0]['localPrice'],16000000)
 def test_fee_overrun_and_invalid_numbers(self):
  self.assertEqual(assess(self.row(mandatory_fees_vnd=1000000))[0],'needs_verification')
  self.assertEqual(assess(self.row()|{'rent_vnd':float('nan')})[0],'needs_verification')

 def test_office_scope_size_and_capacity(self):
  r=self.row()|{'rental_category':'office','rent_vnd':10000000,'district':'Bình Thạnh','sqm':50,'office_character':'informal','office_use_evidence':'Studio offered'}
  self.assertEqual(assess(r)[0],'needs_verification')
  self.assertEqual(assess(r|{'rent_vnd':12000001})[0],'rejected')
  self.assertEqual(assess(r|{'district':'Nhà Bè'})[0],'rejected')
  self.assertEqual(assess(r|{'sqm':105})[0],'rejected')
  self.assertEqual(assess(r|{'workstations':6,'workspace_evidence':'Measured plan'})[0],'match')
 def test_latest_over_budget_observation_removes_old_match(self):
  r=self.row(last_seen='2026-10-05')
  newer=r|{'_run':'2026-10-18','last_seen':'2026-10-18','rent_vnd':19000000,'rent_usd':735}
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/'hcmc-rental-research'/'2026-10-18';run.mkdir(parents=True)
   (run/'journal.json').write_text(json.dumps({'status':'complete'}))
   (run/'candidate-state.json').write_text(json.dumps({'rejected_candidates':[newer]}))
   self.assertEqual(export([r],'saigon','rent',{},reviews(Path(tmp),'hcmc-rental-research'))[0],[])

 def test_office_exception_and_new_areas(self):
  r=self.row()|{'rental_category':'office','rent_vnd':12000000,'district':'District 4','sqm':50,'office_character':'informal'}
  self.assertEqual(assess(r)[0],'rejected')
  self.assertEqual(assess(r|{'office_exception_reason':'Photo-verified shaded terrace and adaptable room'})[0],'needs_verification')
  self.assertEqual(assess(r|{'rent_vnd':10000000,'district':'Phú Nhuận'})[0],'needs_verification')
  self.assertEqual(assess(r|{'rent_vnd':12000001,'office_exception_reason':'Terrace'})[0],'rejected')
