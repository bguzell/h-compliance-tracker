"""Isolation-safe current-state updater: no historical compliance transplanted into today's state."""
import hashlib,json,traceback
from datetime import datetime,timezone,timedelta
from sqlalchemy import delete,select
from .database import init_db,session_factory
from .models import Hospital,SourceDocument,CriterionResult,ChangeEvent,RunLog,ReviewDecision
from .criteria import CRITERIA
from .config import S
from .crawler import crawl_hospital
from .extractor import evaluate,Finding
from .consistency import assess_consistency
from .grader import grade_criteria
from .standards import reference_standard

def now(): return datetime.now(timezone.utc)
def document_hash(docs):
    return hashlib.sha256('|'.join(sorted(f'{d.url}:{d.content_hash}' for d in docs)).encode()).hexdigest()

def update_one(hospital_id, SF=None, fetcher=None, allow_ocr=False):
    SF=SF or session_factory()
    with SF() as s:
        h=s.get(Hospital,hospital_id)
        if h is None: raise KeyError(hospital_id)
        url=h.hfa_url
        provenance=h.hfa_url_provenance or 'ORIGINAL_2025_CSSNY_UNVERIFIED'
    try: crawled=crawl_hospital(url,fetcher=fetcher,allow_ocr=allow_ocr)
    except Exception as exc: # A single site must never end a statewide batch
        from .crawler import CrawlResult
        crawled=CrawlResult([], [str(exc)],False,True)
    with SF.begin() as s:
        h=s.get(Hospital,hospital_id)
        old_grade=h.grade; old_hash=h.current_page_hash
        previous={r.criterion_id:r.status for r in h.results}
        s.execute(delete(SourceDocument).where(SourceDocument.hospital_id==hospital_id))
        s.execute(delete(CriterionResult).where(CriterionResult.hospital_id==hospital_id))
        h.last_checked=now(); h.last_error='; '.join(crawled.errors)[:3000] or None
        if crawled.unavailable or not crawled.documents:
            h.source_status='UNAVAILABLE'
            h.grade=None; h.provisional=True; h.noncompliant_count=0; h.review_count=17
            h.current_page_hash=None
            findings={c.id:Finding(reason='Public source could not be safely retrieved: '+(h.last_error or 'unknown cause')) for c in CRITERIA}
        else:
            new_hash=document_hash(crawled.documents)
            for d in crawled.documents:
                s.add(SourceDocument(hospital_id=hospital_id,url=d.url,doc_type=d.doc_type,title=d.title,language=d.language,content_hash=d.content_hash,extracted_text=d.text,etag=d.etag,last_modified=d.last_modified,retrieved_at=d.retrieved_at,extraction_method=d.method))
            findings=evaluate(crawled.documents,complete=crawled.complete,current_fpl_year=reference_standard()["year"])
            consistency, mismatches=assess_consistency(crawled.documents,crawled.complete)
            # Optional LLM only proposes evidence quotes for unresolved criteria.
            # It NEVER decides PASS/FAIL and all quotes must occur literally in the source.
            import os
            if os.getenv('HFA_AI_PROVIDER','none').lower() != 'none':
                from .ai_extractor import extract_semantic
                for doc in crawled.documents:
                    if doc.doc_type not in ('application','summary','policy'): continue
                    try:
                        for fact in extract_semantic(doc.text,doc.doc_type):
                            cid=fact.field
                            from .criteria import BY_ID
                            criterion=BY_ID.get(cid)
                            if not criterion or criterion.scope not in (doc.doc_type,'website'): continue
                            finding=findings.get(cid)
                            if finding and finding.status=='REVIEW' and not finding.evidence:
                                finding.evidence=fact.evidence
                                finding.url=doc.url
                                finding.doc_type=doc.doc_type
                                finding.title=doc.title
                                finding.confidence=fact.confidence
                                finding.method='ai-candidate-not-graded'
                                finding.explanation=f'AI extracted candidate value: {fact.value}; needs human verification.'
                                finding.reason='An LLM excerpt alone cannot determine compliance.'
                    except Exception as exc:
                        crawled.errors.append(f'Optional AI extraction failed for {doc.url}: {type(exc).__name__}')
            findings['consistent']=consistency
            # A system-wide landing URL may link policies for multiple different hospitals.
            # Do not attribute any of its claims to this particular facility until its
            # applicability has been verified and the URL provenance upgraded.
            if provenance in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT'):
                findings={c.id:Finding(reason='Source URL is only a candidate for this facility; verify facility-specific applicability before grading.') for c in CRITERIA}
                crawled.errors.append('Unverified facility coverage on shared-system source URL')
            # Source-bound reviewer decisions are valid only for *identical* content hashes.
            decisions=s.scalars(select(ReviewDecision).where(ReviewDecision.hospital_id==hospital_id,ReviewDecision.source_hash==new_hash)).all()
            for rev in decisions:
                if rev.criterion_id in findings and rev.decision in ('PASS','FAIL','REVIEW'):
                    base=findings[rev.criterion_id]
                    if not base.url and crawled.documents:
                        base.url=crawled.documents[0].url
                        base.doc_type='landing'
                        base.title='Hospital financial-assistance webpage'
                        base.evidence='HUMAN SOURCE REVIEW: '+(rev.reviewer_note or 'Verified by human reviewer')
                    if base.url and base.evidence:
                        base.status=rev.decision
                        base.explanation=(base.explanation+' | Confirmed by human review: '+(rev.reviewer_note or 'No note')).strip()
                        base.method='human-reviewed'
                        base.confidence=1.0
            outcome=grade_criteria({k:v.status for k,v in findings.items()})
            h.grade=outcome.grade; h.provisional=outcome.provisional
            h.noncompliant_count=outcome.fail_count; h.review_count=outcome.review_count
            h.source_status='CURRENT' if (crawled.complete and provenance not in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT')) else 'PARTIAL_REVIEW'
            h.current_page_hash=new_hash
            if old_hash!=new_hash: h.source_last_changed=now()
        for cid,f in findings.items():
            s.add(CriterionResult(hospital_id=hospital_id,criterion_id=cid,status=f.status,evidence=f.evidence,source_url=f.url,source_document_type=f.doc_type,source_document_title=f.title,source_page=f.page,confidence=f.confidence,extraction_method=f.method,explanation=f.explanation,review_reason=f.reason,retrieved_at=now(),source_hash=h.current_page_hash))
        changed=[cid for cid,f in findings.items() if previous.get(cid)!=f.status]
        if old_hash != h.current_page_hash or changed:
            s.add(ChangeEvent(hospital_id=hospital_id,criteria_changed=json.dumps(changed),old_grade=old_grade,new_grade=h.grade,source_url=h.hfa_url,reason='Public source unavailable' if h.source_status=='UNAVAILABLE' else 'Current source changed' if old_hash else 'First current-source evaluation'))
        s.add(RunLog(hospital_id=hospital_id,outcome=h.source_status,message=h.last_error or f'Inspected {len(crawled.documents)} documents'))
        return {'hospital_id':hospital_id,'grade':h.grade,'provisional':h.provisional,'reviews':h.review_count,'source_status':h.source_status,'errors':crawled.errors}

def refresh_many(limit=None,only_stale_days=None):
    SF=session_factory()
    with SF() as s:
        q=select(Hospital).order_by(Hospital.name)
        if only_stale_days is not None:
            q=q.where((Hospital.last_checked.is_(None))|(Hospital.last_checked<now()-timedelta(days=only_stale_days)))
        ids=[h.hospital_id for h in s.scalars(q).all()]
    if limit is not None: ids=ids[:limit]
    result=[]
    for hid in ids:
        try: result.append(update_one(hid,SF))
        except Exception as e: result.append({'hospital_id':hid,'source_status':'JOB_ERROR','error':str(e)})
    return result

def record_review(hospital_id,criterion_id,source_hash,decision,note='',reviewer='reviewer',SF=None):
    if decision not in ('PASS','FAIL','REVIEW'): raise ValueError('Invalid decision')
    SF=SF or session_factory()
    with SF.begin() as s:
        h=s.get(Hospital,hospital_id)
        if not h or not h.current_page_hash or h.current_page_hash!=source_hash: raise ValueError('Document changed; refresh before reviewing')
        if h.hfa_url_provenance in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT'):
            raise ValueError('Verify facility coverage of the shared HFA source first; cannot grade unverified system-wide documents')
        criterion=s.scalar(select(CriterionResult).where(CriterionResult.hospital_id==hospital_id,CriterionResult.criterion_id==criterion_id))
        if not criterion: raise ValueError('Criterion not found')
        if not note or len(note.strip())<20: raise ValueError('Provide at least 20 characters explaining the review decision')
        if not (criterion.evidence and criterion.source_url):
            # A human can verify *absence* only against a successfully retrieved current
            # landing page and must write the documented check; never fabricate a quote.
            landing=s.scalar(select(SourceDocument).where(SourceDocument.hospital_id==hospital_id,SourceDocument.doc_type=='landing'))
            if not landing: raise ValueError('Current hospital landing page is required for an absence finding')
            criterion.evidence='HUMAN SOURCE REVIEW: '+note.strip()[:1000]
            criterion.source_url=landing.url
            criterion.source_document_type='landing'
            criterion.source_document_title=landing.title
            criterion.extraction_method='human-reviewed-absence' 
        old_grade=h.grade; old_status=criterion.status
        rev=s.scalar(select(ReviewDecision).where(ReviewDecision.hospital_id==hospital_id,ReviewDecision.criterion_id==criterion_id,ReviewDecision.source_hash==source_hash))
        if not rev:
            rev=ReviewDecision(hospital_id=hospital_id,criterion_id=criterion_id,source_hash=source_hash)
            s.add(rev)
        rev.decision=decision; rev.reviewer_note=note[:3000]; rev.reviewer=reviewer[:100]; rev.decided_at=now()
        criterion.status=decision; criterion.explanation=(criterion.explanation or '')+' | Human review: '+note[:500]
        criterion.extraction_method='human-reviewed'; criterion.confidence=1
        statuses={r.criterion_id:r.status for r in s.scalars(select(CriterionResult).where(CriterionResult.hospital_id==hospital_id)).all()}
        outcome=grade_criteria(statuses)
        h.grade=outcome.grade;h.provisional=outcome.provisional;h.noncompliant_count=outcome.fail_count;h.review_count=outcome.review_count
        if old_status!=decision:
            s.add(ChangeEvent(hospital_id=hospital_id,criteria_changed=json.dumps([criterion_id]),old_grade=old_grade,new_grade=h.grade,source_url=criterion.source_url,reason='Reviewed source evidence'))

def light_check(hospital_id,SF=None,fetcher=None):
    """Daily landing-only conditional GET; on changed ETag/content run a full update."""
    from .sources import Fetcher,SourceUnavailable
    SF=SF or session_factory();own=fetcher is None;fetcher=fetcher or Fetcher()
    with SF() as s:
        h=s.get(Hospital,hospital_id)
        if h is None:raise KeyError(hospital_id)
        landing=s.scalar(select(SourceDocument).where(SourceDocument.hospital_id==hospital_id,SourceDocument.doc_type=='landing'))
        if not landing: return update_one(hospital_id,SF,fetcher)
        url=h.hfa_url;etag=landing.etag;modified=landing.last_modified;old_hash=landing.content_hash
    try:
        data=fetcher.fetch(url,etag=etag,last_modified=modified)
        if data.get('not_modified'): changed=False
        else: changed=hashlib.sha256(data['body']).hexdigest()!=old_hash
        if changed: return update_one(hospital_id,SF,fetcher)
        with SF.begin() as s:
            h=s.get(Hospital,hospital_id);h.last_checked=now()
            s.add(RunLog(hospital_id=hospital_id,outcome='UNCHANGED',message='Landing-page conditional GET; full refresh due weekly'))
        return {'hospital_id':hospital_id,'source_status':'UNCHANGED','errors':[]}
    except SourceUnavailable as exc:
        # A temporary failed check should never be reinterpreted as legal noncompliance.
        with SF.begin() as s:
            h=s.get(Hospital,hospital_id)
            h.source_status='STALE_REVIEW';h.last_error=str(exc)
            h.provisional=True
            s.add(RunLog(hospital_id=hospital_id,outcome='STALE_REVIEW',message=str(exc)))
        return {'hospital_id':hospital_id,'source_status':'STALE_REVIEW','errors':[str(exc)]}
    finally:
        if own: fetcher.close()

def light_check_many(limit=None,days=1):
    SF=session_factory()
    with SF() as s:
        cutoff=now()-timedelta(days=days)
        q=select(Hospital.hospital_id).where((Hospital.last_checked.is_(None))|(Hospital.last_checked<cutoff)).order_by(Hospital.name)
        ids=list(s.scalars(q))
    selected = ids[:limit] if limit else ids
    return [light_check(hid,SF) for hid in selected]


def verify_facility_source(hospital_id,evidence_url,note,reviewer='operator',SF=None):
    """Administrative acknowledgement that source materials actually cover this facility.

    This is explicitly a human verification, not an inference from system membership.
    Require an actually fetched source URL and an attributable explanatory note.
    """
    from urllib.parse import urlsplit
    if len(note.strip())<40: raise ValueError('Source verification requires at least 40 characters of facility-specific reasoning')
    SF=SF or session_factory()
    with SF.begin() as s:
        h=s.get(Hospital,hospital_id)
        if not h: raise ValueError('Unknown facility ID')
        if h.hfa_url_provenance not in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT'):
            raise ValueError('Facility source does not require a system-link verification')
        d=s.scalar(select(SourceDocument).where(SourceDocument.hospital_id==hospital_id,SourceDocument.url==evidence_url))
        if not d: raise ValueError('Evidence URL must belong to a CURRENT retrieved source document for this facility')
        if not d.extracted_text or len(d.extracted_text)<65:
            raise ValueError('Verification evidence document must have readable text')
        h.hfa_url_provenance='HUMAN_VERIFIED_FACILITY_COVERAGE'
        s.add(ChangeEvent(hospital_id=hospital_id,old_grade=h.grade,new_grade=h.grade,source_url=evidence_url,reason='Shared source coverage verified by '+reviewer+': '+note[:240]))
    return True
