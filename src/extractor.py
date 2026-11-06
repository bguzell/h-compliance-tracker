"""Evidence-grounded extraction and CSSNY decision rules. Unknown is REVIEW, never guessed."""
import re
from dataclasses import dataclass
from .criteria import CRITERIA
from .config import S

@dataclass
class Finding:
    status: str='REVIEW'
    evidence: str=''
    url: str=''
    doc_type: str=''
    title: str=''
    method: str='deterministic'
    confidence: float|None=None
    explanation: str=''
    reason: str='Not enough verified evidence.'
    page: str=''
    def __post_init__(self):
        if self.status not in ('PASS','FAIL','REVIEW','N/A'): raise ValueError('Invalid decision')
        if self.status in ('PASS','FAIL') and (not self.evidence or not self.url): raise ValueError('Decision requires evidence or absence-check record')

def snippet(text,match,radius=105):
    return text[max(0,match.start()-radius):min(len(text),match.end()+radius)].strip()

def detected_page(text,start):
    prev=list(re.finditer(r'\[Page (\d+)\]',text[:start]))
    return 'p. '+prev[-1].group(1) if prev else ''

def scan(docs,regex,scope=None):
    for d in docs:
        if scope and d.doc_type not in scope: continue
        m=re.search(regex,d.text,re.IGNORECASE)
        if m: return d,m
    return None,None

def explicit(status,d,m,explanation='',reason=''):
    quote=snippet(d.text,m)
    return Finding(status,quote,d.url,d.doc_type,d.title,'regex',0.93,explanation,reason,detected_page(d.text,m.start()))

def absent_check(docs,term,scope='all',is_compliant=False):
    # Structured no-match record is a documented evidence artifact, not an invented quote.
    selected=[d for d in docs if scope=='all' or d.doc_type==scope]
    if not selected: return Finding(reason='Required document was not safely retrieved.')
    return Finding('PASS' if is_compliant else 'FAIL',
        f'ABSENCE CHECK: Searched {len(selected)} fully extracted source(s) for {term}; none found. Links and retrieval timestamp recorded.',
        selected[0].url,scope,selected[0].title,'absence-check',0.70,
        f'Automated complete-text absence check for {term}.',
        'An absence finding should be verified by a reviewer.')

def evidence_document(d):
    return Finding('PASS',f'DOCUMENT PRESENT: {d.title}; extracted {len(d.text)} characters.',d.url,d.doc_type,d.title,'retrieval',0.98,'The published document was retrieved and its text extracted.','')

def percentage_claims(doc,regex):
    result=[]
    for match in re.finditer(regex,doc.text,re.I):
        try: result.append((float(match.group(1)),match))
        except ValueError: pass
    return result

def evaluate(docs,complete=False,current_fpl_year=None):
    year=current_fpl_year or S.fpl_year
    kinds={typ:[d for d in docs if d.doc_type==typ and len(d.text)>20] for typ in ('application','summary','policy')}
    findings={c.id:Finding(reason='Not enough source evidence to decide safely.') for c in CRITERIA}
    for cid,typ in [('application_posted','application'),('summary_posted','summary'),('policy_posted','policy')]:
        if kinds[typ]: findings[cid]=evidence_document(kinds[typ][0])
        elif complete:
            # A working landing page does NOT prove no document is posted elsewhere: REVIEW.
            findings[cid]=Finding(reason=f'No {typ} link found on the checked page; human must confirm missing publication.')

    # Scope = ALL posted materials (not one document only).
    d,m=scan(docs,r'(?:must|shall|required to|need to).{0,70}(?:apply|submit|return).{0,60}(?:within|no later than|by).{0,12}\d{1,3}\s*(?:days?|months?)|(?:apply|submit|return).{0,40}(?:within|up to)\s*\d{1,3}\s*(?:days?|months?)|(?:up to|within)\s*\d{1,3}\s*(?:days?|months?).{0,100}(?:submit|apply|return)')
    if m: findings['no_deadline']=explicit('FAIL',d,m,'A possible deadline to apply was found.','Manual confirmation recommended: exclude notice and determination time limits.')
    elif complete and kinds['policy'] and kinds['application']: findings['no_deadline']=absent_check(docs,'prohibited time limits',is_compliant=True)
    d,m=scan(docs,r'(?:bank statements?|checking account statements?|savings account statements?|asset[s]? verification|proof of assets|real estate assets|liquid assets)')
    if m:
        excerpt=snippet(d.text,m,90)
        if re.search(r'(?:not|required to not|never|no need to|do not|without).{0,55}(?:bank statements?|asset)|(?:bank statements?|asset).{0,45}(?:not required|not requested)',excerpt,re.I):
            findings['no_asset_checks']=Finding('REVIEW',excerpt,d.url,d.doc_type,d.title,'regex',0.66,'The document mentions bank statements or assets in a negative/ambiguous context.','Check whether it prohibits or requires an asset check.',detected_page(d.text,m.start()))
        else:
            findings['no_asset_checks']=explicit('FAIL',d,m,'Possible prohibited asset documentation or checks.','CSSNY treats bank statements as evidence of non-compliance; legal scope requires confirmation.')
    elif complete and kinds['policy'] and kinds['application']: findings['no_asset_checks']=absent_check(docs,'asset-check or bank statement conditions',is_compliant=True)
    d,m=scan(docs,r'(?:ineligible|not eligible|excluded|must be (?:a|an) (?:U\.?S\.? citizen|lawful resident)).{0,100}(?:immigration status|undocumented|citizen|legal resident)|(?:immigration status|undocumented).{0,80}(?:ineligible|not eligible|excluded)')
    if m: findings['no_immigration_barrier']=explicit('FAIL',d,m,'A possible immigration-status eligibility exclusion appears.','Reviewer should check for negation or conditional context.')
    else:
        d,m=scan(docs,r'(?:immigration status (?:does not|will not|is not)|regardless of immigration status|without regard to immigration status)')
        if m: findings['no_immigration_barrier']=explicit('PASS',d,m,'Explicit non-discrimination statement.','')
        elif complete and kinds['policy']: findings['no_immigration_barrier']=absent_check(docs,'immigration exclusion',is_compliant=True)
    d,m=scan(docs,r'(?:primary service area|service area|counties served|serving (?:residents|patients) of)')
    if m: findings['psa_boundaries']=Finding('REVIEW',snippet(d.text,m),d.url,d.doc_type,d.title,'regex',0.6,'Service-area language was found.','Review geographic boundaries against current DOH 2007 criteria.',detected_page(d.text,m.start()))

    # APPLICATION SECTION: no policy/summary leakage.
    apps=kinds['application']; summaries=kinds['summary']
    if apps:
        d,m=scan(apps,r'(?:uniform (?:hospital )?financial assistance application|nys uniform financial assistance application)',{'application'})
        if m: findings['uniform_application']=Finding('REVIEW',snippet(d.text,m),d.url,d.doc_type,d.title,'regex',0.6,'Form identifies itself as uniform.','Compare every section with current official NYS application; name alone cannot establish completeness.',detected_page(d.text,m.start()))
        else: findings['uniform_application']=Finding(reason='Full equivalence to DOH Uniform Application not yet confirmed.')
        d,m=scan(apps,r'\(?\d{3}\)?[\-\s\.]\d{3}[\-\s\.]\d{4}|(?:email|contact us|financial assistance office).{0,50}[@:]')
        if m: findings['application_contact']=explicit('PASS',d,m,'Application includes contact information.','')
        elif complete: findings['application_contact']=absent_check(apps,'contact phone or email','application')
        d,m=scan(apps,r'(?:discount|sliding scale|waiv(?:e|er|ed)).{0,150}(?:income|poverty|fpl)|(?:income|poverty|fpl).{0,150}(?:discount|sliding scale)')
        if m:
            findings['application_tables']=Finding('REVIEW',snippet(d.text,m),d.url,d.doc_type,d.title,'regex',0.7,'Income and discount language appears.','Confirm a COMPLETE table is actually printed in the application, not just a description.',detected_page(d.text,m.start()))
        elif complete: findings['application_tables']=absent_check(apps,'income-and-discount table','application')
        fpl_years=set(); last_hit=None
        for d in apps:
            for m in re.finditer(r'(?:(20\d{2}).{0,30}(?:federal poverty|poverty level|poverty guideline|fpl)|(?:federal poverty|poverty level|poverty guideline|fpl).{0,30}(20\d{2}))',d.text,re.I):
                val=int(m.group(1) or m.group(2)); fpl_years.add(val); last_hit=(d,m)
        if len(fpl_years)==1:
            value=next(iter(fpl_years)); d,m=last_hit
            findings['application_fpl_year']=explicit('PASS' if value==year else 'FAIL',d,m,f'Application references {value}; applicable benchmark {year}.','')
        elif len(fpl_years)>1: findings['application_fpl_year']=Finding(reason='Multiple FPL years are referenced; reviewer should inspect tables.')
        else: findings['application_fpl_year']=Finding(reason=f'Cannot verify the applicable {year} FPL standard in the application.')
        # Only an explicitly identified ceiling, not an intermediate discount-band percentage.
        d,m=scan(apps,r'(?:eligible|eligibility|qualif(?:y|ies)|assistance|financial aid).{0,90}(?:up to|through|below|under|at or below)\s*(\d{2,3})\s*%\s*(?:of\s*(?:the\s*)?)?(?:fpl|federal poverty|poverty level)|(?:up to|through|below|at or below)\s*(\d{2,3})\s*%\s*(?:of\s*(?:the\s*)?)?(?:fpl|federal poverty|poverty level)')
        if m:
            threshold=int(m.group(1) or m.group(2))
            findings['application_max_fpl']=explicit('PASS' if threshold>=400 else 'FAIL',d,m,f'Explicit cutoff {threshold}% FPL.','Confirm this is the maximum, not one discount band.')
            if threshold<400: findings['application_max_fpl'].status='REVIEW'  # refuse to confuse tier with maximum
        d,m=scan(apps,r'(?:monthly|installment).{0,110}(?:no more than|not exceed|capped at|maximum of|limited to)\s*(\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(?:the\s*)?(?:gross\s*)?(?:monthly\s*)?income|(?:no more than|not exceed|capped at|maximum of)\s*(\d+(?:\.\d+)?)\s*%\s*of\s*(?:gross\s*)?monthly income')
        if m:
            val=float(m.group(1) or m.group(2))
            findings['application_installments']=explicit('PASS' if val<=5 else 'FAIL',d,m,f'Application explicitly states installment payment cap {val}%.','')
            if val<5: findings['application_installments'].reason='Verify cap is a payment cap rather than an unrelated fee.'
        elif complete: findings['application_installments']=absent_check(apps,'explicit 5% gross monthly income installment cap','application')

    # SUMMARY SECTION: no rescuing from application or policy.
    if summaries:
        d,m=scan(summaries,r'(?:primary service area|service area).{0,110}(?:includes|covers|consists of|is composed of|count(?:y|ies)|borough|region|area served|residents of)|(?:primary service area|service area)[:\s]+[A-Za-z ]{3,35} (?:County|counties)',{'summary'})
        if m: findings['summary_psa']=explicit('PASS',d,m,'Summary provides a service-area description.','Confirm boundaries with current DOH guidance.')
        elif scan(summaries,r'primary service area|service area',{'summary'})[1]:
            d,m=scan(summaries,r'primary service area|service area',{'summary'})
            findings['summary_psa']=Finding('REVIEW',snippet(d.text,m),d.url,d.doc_type,d.title,'regex',0.5,'Service area is mentioned but its geographic boundaries may not be described.','Verify whether summary describes the covered areas.')
        elif complete: findings['summary_psa']=absent_check(summaries,'primary service area description','summary')
        d,m=scan(summaries,r'(?:apply|application|submit|send|mail|drop off|pick up).{0,65}(?:online|website|call|phone|mail|fax|in person|office|email|at [\w.]+\.org)|(?:to apply|how to apply).{0,90}\d{3}[\-\s\.]\d{3}[\-\s\.]\d{4}')
        if m: findings['summary_application']=explicit('PASS',d,m,'Summary explains how to apply.','')
        elif complete: findings['summary_application']=absent_check(summaries,'instructions for applying','summary')
        d,m=scan(summaries,r'\d{2,3}\s*%\s*(?:of\s*(?:the\s*)?)?(?:fpl|federal poverty|poverty level)|(?:income|household).{0,60}\$[\d,]+|\$[\d,]+.{0,60}(?:income|household)')
        if m: findings['summary_income']=explicit('PASS',d,m,'Summary explains income thresholds.','')
        elif complete: findings['summary_income']=absent_check(summaries,'assistance income levels','summary')
    return findings
