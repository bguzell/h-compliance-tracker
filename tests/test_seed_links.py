from urllib.parse import urlsplit
from src.seed import read_baseline,read_links,read_overrides,seed_database
from sqlalchemy import create_engine,select
from src.models import Hospital

def test_original_38_bad_csv_values_are_accounted_for():
    rows=read_baseline(); links=read_links(); overrides=read_overrides()
    bad={r['Hospital Name'] for r in rows if not urlsplit((links.get(r['Hospital Name']) or r['HFA Link']).strip()).netloc}
    assert len(rows)==212 and len(bad)==38 and bad==set(overrides)
    assert all(v['verified_live_retrieval'].startswith('NO') for v in overrides.values())

def test_seed_preserves_original_file_and_flags_candidate_urls(tmp_path):
    url='sqlite:///'+str(tmp_path/'testseed.db')
    assert seed_database(url)==212
    e=create_engine(url)
    with __import__('sqlalchemy.orm',fromlist=['Session']).Session(e) as db:
        hospitals=db.scalars(select(Hospital)).all()
        assert len(hospitals)==212
        schuyler=next(x for x in hospitals if x.name=='Schuyler Hospital')
        assert schuyler.hfa_url.startswith('https://cayugahealth.org/')
        northwell=next(x for x in hospitals if x.name=='South Shore University Hospital')
        assert northwell.hfa_url_provenance=='SAME_SYSTEM_CANDIDATE'
        assert northwell.grade is None and northwell.review_count==17
        assert sum(x.hfa_url_provenance=='UNRESOLVED_MISSING_URL' for x in hospitals)==0
