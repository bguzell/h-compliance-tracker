"""Authoritative NYS DOH roster/geocoding; no invented lat/lon or name-only auto-merges."""
import httpx,re
from sqlalchemy import select
from .config import SOURCE_DOHSOCRATA,S
from .database import session_factory
from .models import Hospital

def norm(value): return re.sub(r'\s+',' ',str(value or '').lower().strip()).replace('.','')

def get_official_roster(client=None,limit=6000):
    own=client is None; client=client or httpx.Client(timeout=35)
    try:
        items=[]
        for off in range(0,limit,1000):
            res=client.get(SOURCE_DOHSOCRATA,params={'$limit':1000,'$offset':off})
            res.raise_for_status(); batch=res.json()
            if not isinstance(batch,list): raise ValueError('Unexpected Socrata response')
            items.extend(batch)
            if len(batch)<1000: break
        return items
    finally:
        if own: client.close()

def point_of(rec):
    loc=rec.get('location') or rec.get('geocoded_column') or rec.get('location_1') or {}
    if isinstance(loc,dict):
        if loc.get('latitude') and loc.get('longitude'):
            return float(loc['latitude']),float(loc['longitude'])
        coords=loc.get('coordinates')
        if coords and len(coords)==2: return float(coords[1]),float(coords[0])
    try:
        lat=rec.get('latitude') or rec.get('lat'); lon=rec.get('longitude') or rec.get('lon')
        if lat is not None and lon is not None: return float(lat),float(lon)
    except ValueError: pass
    return None

def sync_roster(records=None,SF=None):
    records=records if records is not None else get_official_roster()
    SF=SF or session_factory()
    index={}
    for row in records:
        pfi=row.get('facility_id') or row.get('pfi') or row.get('pfi_id')
        if pfi is None: continue
        key=str(pfi).lstrip('0') or '0'
        index.setdefault(key,[]).append(row)
    matched=0; flagged=[]
    with SF.begin() as s:
        for h in s.scalars(select(Hospital)).all():
            candidates=index.get(str(h.pfi).lstrip('0') or '0',[]) if h.pfi else []
            # Match PFI *and* either city, ZIP or exact name, to avoid extension mis-assignment.
            candidates=[x for x in candidates if norm(x.get('city'))==norm(h.city) or norm(x.get('fac_zip') or x.get('zip'))==norm(h.zipcode) or norm(x.get('facility_name') or x.get('name'))==norm(h.name)]
            if len(candidates)!=1:
                h.roster_status='Needs reconciliation';flagged.append(h.hospital_id);continue
            src=candidates[0];h.roster_status='DOH match confirmed';h.county=src.get('county') or h.county
            point=point_of(src)
            if point and 40.3 <= point[0] <= 45.2 and -80.3 <= point[1] <= -71:
                h.latitude,h.longitude=point
                h.location_provenance=SOURCE_DOHSOCRATA
            matched+=1
    return {'matched':matched,'flagged':len(flagged),'flagged_ids':flagged}
