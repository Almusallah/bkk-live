"""VND hard gates for the user-confirmed HCMC rental brief (2026-10-05)."""
import math

CAPS = {'office': 20_000_000, 'house': 17_000_000, 'modernist_villa': None}
HOUSES = {'house', 'tube_house', 'townhouse'}

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def assess(row):
    if row.get('city') not in ('saigon', 'hcmc'):
        return 'rejected', 'Outside HCMC or location unestablished'
    category = row.get('rental_category')
    if category not in CAPS:
        return 'needs_verification', 'Rental category not established'
    rent = row.get('rent_vnd')
    if not number(rent) or rent <= 0:
        return 'needs_verification', 'Whole-property monthly VND rent not established'
    if row.get('rent_period') != 'month':
        return 'needs_verification', 'Monthly whole-property quote not established'
    if CAPS[category] is not None and rent > CAPS[category]:
        return 'rejected', 'Monthly asking rent exceeds cap'
    kind = row.get('property_type', 'unknown')
    if kind == 'unknown':
        return 'needs_verification', 'Property type not established'
    if category == 'house':
        if kind not in HOUSES:
            return 'rejected', 'Not a whole house'
        beds = row.get('bedrooms')
        if not number(beds) or beds < 0 or beds != int(beds):
            return 'needs_verification', 'Actual bedroom count not established'
        if beds < 3:
            return 'rejected', 'Fewer than three bedrooms'
    elif category == 'modernist_villa':
        if kind != 'villa':
            return 'rejected', 'Not a villa'
        if row.get('centrality') != 'central':
            return 'needs_verification', 'Central Saigon location needs confirmation'
        if row.get('modernist_evidence_status') not in ('source_stated', 'visual_review'):
            return 'needs_verification', 'Southern modernist style needs visual or source verification'
        if not row.get('modernist_evidence'):
            return 'needs_verification', 'Modernist evidence missing'
    else:
        if kind not in HOUSES | {'converted_apartment', 'apartment'} or row.get('office_character') == 'corporate':
            return 'rejected', 'Commercial format outside the office brief'
        if row.get('office_character') != 'informal' or not str(row.get('office_use_evidence') or '').strip():
            return 'needs_verification', 'Informal character and office-use evidence required'
    fees = row.get('mandatory_fees_vnd')
    if fees is not None and (not number(fees) or fees < 0):
        return 'needs_verification', 'Mandatory fees invalid'
    if CAPS[category] is not None and number(fees) and rent + fees > CAPS[category]:
        return 'needs_verification', 'Known monthly total exceeds cap'
    if row.get('listing_status') in ('expired', 'stale'):
        return 'needs_verification', 'Expired or old advertisement; availability needs rechecking'
    return 'match', 'Source-stated criteria only; availability, permissions and all-in cost require confirmation'
