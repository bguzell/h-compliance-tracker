from datetime import datetime,timezone
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from src.models import Base,Hospital,SourceDocument,CriterionResult,ChangeEvent
from src.crawler import CrawledDocument,CrawlResult
import src.updater as updater

def setup():
    e=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(e)
    SF=sessionmaker(bind=e,expire_on_commit=False)
    with SF.begin() as db:db.add(Hospital(hospital_id='01-01',name='Hospital example',hfa_url='https://example.org/hfa',historical_grade='A'))
    return SF

def crawl(payload):
    return CrawlResult([CrawledDocument('https://example.org/hfa','landing','Financial assistance','English',payload,'a1'*32,None,None,'html-text',datetime.now(timezone.utc))],[],True)

def test_initial_2025_grade_does_not_become_current(monkeypatch):
    sf=setup()
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl('Information about financial assistance and admissions.'))
    result=updater.update_one('01-01',SF=sf)
    with sf() as db:
        hospital=db.get(Hospital,'01-01')
        assert hospital.historical_grade=='A'
        assert hospital.grade is None # all results review; honest pending
        assert hospital.review_count==17
        assert len(hospital.documents)==1

def test_source_failure_is_review_and_clears_current_content(monkeypatch):
    sf=setup()
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl('financial assistance.'))
    updater.update_one('01-01',SF=sf)
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:CrawlResult([],['HTTP 403'],False,True))
    result=updater.update_one('01-01',SF=sf)
    with sf() as db:
        h=db.get(Hospital,'01-01')
        assert h.source_status=='UNAVAILABLE' and h.grade is None
        assert not h.documents
        assert all(r.status=='REVIEW' for r in h.results)

def test_no_change_event_if_no_changes(monkeypatch):
    sf=setup()
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl('Financial assistance available.'))
    updater.update_one('01-01',SF=sf)
    updater.update_one('01-01',SF=sf)
    with sf() as db:
        assert len(db.scalars(select(ChangeEvent)).all())==1

def test_manual_review_follows_exact_source_hash(monkeypatch):
    sf=setup()
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl('Financial assistance publicly described here, but there is no published application link.'))
    updater.update_one('01-01',SF=sf)
    with sf() as db:hash_=db.get(Hospital,'01-01').current_page_hash
    updater.record_review('01-01','application_posted',hash_,'FAIL',note='Checked every available assistance link; no application appears.',SF=sf)
    with sf() as db:
        h=db.get(Hospital,'01-01')
        assert h.grade=='F' and h.provisional
        assert next(r for r in h.results if r.criterion_id=='application_posted').source_url
    updater.update_one('01-01',SF=sf)  # exact same content hash should keep review
    with sf() as db:
        h=db.get(Hospital,'01-01')
        assert next(r for r in h.results if r.criterion_id=='application_posted').status=='FAIL'

def test_system_landing_candidate_never_inherits_facility_grade(monkeypatch):
    sf=setup()
    with sf.begin() as db:
        db.get(Hospital,'01-01').hfa_url_provenance='SAME_SYSTEM_CANDIDATE'
    # Fake convincing source statement: even this cannot establish applicability.
    text=('Financial Assistance Application available. Submit applications by mail. '
          'The primary service area includes the relevant counties. ') * 4
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl(text))
    updater.update_one('01-01',SF=sf)
    with sf() as db:
        h=db.get(Hospital,'01-01')
        assert h.grade is None and h.review_count==17
        assert h.source_status=='PARTIAL_REVIEW'
        assert all(r.status=='REVIEW' for r in h.results)

def test_shared_candidate_review_blocked_until_facility_source_verified(monkeypatch):
    import pytest
    sf=setup()
    with sf.begin() as db:db.get(Hospital,'01-01').hfa_url_provenance='SAME_SYSTEM_CANDIDATE'
    monkeypatch.setattr(updater,'crawl_hospital',lambda *args,**kwargs:crawl(('Hospital financial assistance application materials and financial aid. ')*3))
    updater.update_one('01-01',SF=sf)
    with sf() as db:
        h=db.get(Hospital,'01-01')
        src=db.scalar(select(SourceDocument).where(SourceDocument.hospital_id=='01-01'))
        evidence_url=src.url
        hsh=h.current_page_hash
    with pytest.raises(ValueError,match='Verify facility coverage'):
        updater.record_review('01-01','application_posted',hsh,'PASS',note='Reviewed this hospital application thoroughly, verified.',SF=sf)
    with pytest.raises(ValueError,match='at least 40 characters'):
        updater.verify_facility_source('01-01',evidence_url,'Too little',SF=sf)
    assert updater.verify_facility_source('01-01',evidence_url,'I reviewed the published landing page and separately confirmed that the named facility participates.',SF=sf)
    with sf() as db:
        h=db.get(Hospital,'01-01')
        assert h.hfa_url_provenance=='HUMAN_VERIFIED_FACILITY_COVERAGE'
