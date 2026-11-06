"""Import exactly the original 2025 212-row review, preserving original source CSV unchanged."""
import csv, hashlib
from urllib.parse import urlsplit
from pathlib import Path
from sqlalchemy import select
from .config import ROOT
from .database import engine,init_db,session_factory
from .models import Hospital, CriterionResult
from .criteria import CRITERIA

TRACKER = ROOT / 'data/seed/cssny_2025_tracker.csv'
LINKS = ROOT / 'data/seed/cssny_2025_hfa_links.csv'
OVERRIDES = ROOT / 'data/seed/hfa_url_overrides.csv'

def read_baseline():
    with TRACKER.open(encoding='utf-8-sig',newline='') as f:
        rr=csv.reader(f); next(rr); cols=next(rr)
        return [dict(zip(cols,row)) for row in rr if any(row)]

def read_links():
    with LINKS.open(encoding='utf-8-sig',newline='') as f:
        return {r['Hospital name']:r['External HFA link'] for r in csv.DictReader(f)}

def read_overrides():
    with OVERRIDES.open(encoding='utf-8', newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=len({r['hospital_name'] for r in rows}):
        raise ValueError('Duplicate source override hospital name')
    for r in rows:
        candidate=urlsplit(r['candidate_official_url'])
        if candidate.scheme!='https' or not candidate.netloc or candidate.username or candidate.password:
            raise ValueError('Invalid candidate source URL: '+r['hospital_name'])
    return {r['hospital_name']:r for r in rows}

def hospital_id(row):
    id_=row['OCN_PFI'].strip()
    if id_: return id_
    # ONE historical record lacks ALL operating IDs; explicitly mark as provisional and reconcile.
    key='|'.join([row['Hospital Name'],row['Address'],row['City']])
    return 'UNRESOLVED-'+hashlib.sha256(key.encode()).hexdigest()[:12]

def seed_database(db_url=None):
    e=engine(db_url); init_db(e); SF=session_factory(e)
    records=read_baseline(); links=read_links(); overrides=read_overrides()
    if len(records)!=212: raise ValueError(f'Expected 212 records; found {len(records)}')
    if len(set(hospital_id(row) for row in records))!=len(records): raise ValueError('Hospital identifier collision')
    with SF.begin() as db:
        for row in records:
            hid=hospital_id(row)
            h=db.get(Hospital,hid)
            if h is None: h=Hospital(hospital_id=hid); db.add(h)
            h.name=row['Hospital Name'].strip(); h.pfi=row['Permanent Facility Identifier (PFI)'].strip()
            h.ocn=row['Operating certificate number'].strip()
            h.ocn_pfi=row['OCN_PFI'].strip() or None
            h.address=row['Address'].strip(); h.city=row['City'].strip()
            h.state=row['State'].strip() or 'NY'; h.zipcode=row['Zip'].strip()
            h.system=row['System'].strip()
            historical_link=(links.get(h.name) or row['HFA Link']).strip()
            parsed=urlsplit(historical_link)
            if parsed.scheme in ('http','https') and parsed.netloc:
                h.hfa_url=historical_link
                h.hfa_url_provenance='ORIGINAL_2025_CSSNY_UNVERIFIED'
            elif h.name in overrides:
                h.hfa_url=overrides[h.name]['candidate_official_url']
                h.hfa_url_provenance=overrides[h.name]['resolution_type']
            else:
                h.hfa_url=None
                h.hfa_url_provenance='UNRESOLVED_MISSING_URL'
            if h.hfa_url_provenance=='UNRESOLVED_MISSING_URL':
                h.source_status='URL_UNRESOLVED'

            h.id_needs_reconciliation=not bool(h.ocn_pfi)
            h.historical_grade=row['COMPLIANCE GRADE'].strip()
            h.historical_error_count=int(row['Noncompliant Categories Count'])
            h.historical_auto_fail=row['Automatic Fail?'].strip().upper()=='TRUE'
            h.historical_languages=row['Languages Available'].strip()
            if not h.results:
                for c in CRITERIA:
                    db.add(CriterionResult(hospital_id=hid,criterion_id=c.id,status='REVIEW',review_reason='Not yet checked against current source material.'))
    return len(records)

if __name__=='__main__': print('Imported:',seed_database())
