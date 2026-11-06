"""Explicit cross-document fact checks; do not hallucinate agreement from silence."""
import re
from dataclasses import dataclass
from .extractor import Finding

FACT_PATTERNS={
 'eligibility_ceiling':r'(?:eligible|eligibility|assistance).{0,80}(?:up to|through|below)\s*(\d{2,3})\s*%\s*(?:of\s*)?(?:the\s*)?(?:fpl|federal poverty|poverty level)',
 'installment_cap':r'(?:monthly|installment).{0,75}(?:capped at|not exceed|no more than)\s*(\d+(?:\.\d+)?)\s*%',
 'application_deadline':r'(?:apply|submit|return).{0,50}(?:within|up to)\s*(\d+)\s*days',
 'fpl_year':r'(?:(20\d{2}).{0,20}(?:fpl|poverty guideline|poverty level))',
 'discount_percent':r'(?:discount|waiver) (?:of|is|at|equals)?\s*(\d{1,3})\s*%',
 'hfa_contact_phone':r'(?:financial assistance|financial aid) (?:office|team|help(?:line)?|phone)?\s*(?:call|at|:)?\s*(\(?\d{3}\)?[\-\s\.]\d{3}[\-\s\.]\d{4})',
 'psa_county':r'primary service area (?:includes|is|covers)\s*([A-Za-z ]{3,35} County)',
}

@dataclass
class Mismatch:
    field:str; left_type:str; left_value:str; left_url:str; right_type:str; right_value:str; right_url:str

def semantic_claims(text):
    """Only direct explicit binary claims. Negated text is not taken as a positive."""
    claims={}
    if re.search(r'(?:regardless of immigration status|immigration status (?:shall|will|does) not|immigration status is not (?:an )?eligibility)',text,re.I):
        claims['immigration_rule']='allowed'
    if re.search(r'(?:ineligible|excluded|not eligible).{0,60}(?:immigration status|undocumented)|(?:immigration status|undocumented).{0,60}(?:ineligible|excluded|not eligible)',text,re.I):
        claims['immigration_rule']='excluded' if 'immigration_rule' not in claims else 'ambiguous'
    if re.search(r'(?:not required|do not require|no need to provide).{0,35}bank statements?',text,re.I):
        claims['bank_statement_rule']='not_required'
    if re.search(r'(?:must|require(?:d)?|submit|provide).{0,35}bank statements?',text,re.I):
        claims['bank_statement_rule']='required' if 'bank_statement_rule' not in claims else 'ambiguous'
    return claims

def compare(docs):
    mismatches=[]; compared=0
    facts={}
    for d in docs:
        if d.doc_type not in ('application','policy','summary','supplemental'): continue
        for field,pattern in FACT_PATTERNS.items():
            vals=set(m.group(1).strip().lower() for m in re.finditer(pattern,d.text,re.I))
            if len(vals)==1: facts.setdefault(field,[]).append((d,next(iter(vals))))
        for field,val in semantic_claims(d.text).items():
            if val!='ambiguous': facts.setdefault(field,[]).append((d,val))
    for field,items in facts.items():
        # Compare facts only when reported in *different* documents.
        urls={d.url for d,val in items}
        if len(urls)>=2: compared+=1
        if len(urls)<2: continue
        for ai,a in enumerate(items):
            for b in items[ai+1:]:
                if a[0].url==b[0].url:continue
                if a[1]!=b[1]: mismatches.append(Mismatch(field,a[0].doc_type,a[1],a[0].url,b[0].doc_type,b[1],b[0].url))
    return mismatches,compared

def assess_consistency(docs,complete):
    differences,compared=compare(docs)
    if differences:
        m=differences[0]
        evidence=f'CONFLICT: {m.field}: {m.left_type} {m.left_value} ({m.left_url}) vs {m.right_type} {m.right_value} ({m.right_url})'
        return Finding('FAIL',evidence,m.left_url,'cross_document','Cross-document comparison','deterministic',0.94,'Hospital documents disagree on a structured fact.','Confirm field semantics and whether figures refer to distinct tiers.'),differences
    if not complete or compared==0:
        return Finding(reason='No reliably comparable facts across at least two complete documents.'),[]
    return Finding('REVIEW',f'Compared {compared} structured fact types with no mismatches.',docs[0].url,'cross_document','Comparison','deterministic',0.75,'No disagreement found in the structured fields inspected.','Semantic discrepancies require review.'),[]
