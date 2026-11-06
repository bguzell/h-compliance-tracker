from types import SimpleNamespace
from src.extractor import evaluate

def doc(text,typ='application',url='https://example.org/financial-assistance.pdf'):
    return SimpleNamespace(text=text,doc_type=typ,title='Test '+typ,url=url)

def test_missing_application_is_review_not_fabricated_fail():
    result=evaluate([doc('Financial assistance policy statement and application access details.','landing')],complete=True)
    assert result['application_posted'].status=='REVIEW'
    assert result['uniform_application'].status=='REVIEW'

def test_document_scope_separation():
    app=doc('Please call 212-555-1212 to apply. The 2025 FPL Guidelines apply.','application')
    policy=doc('Applicants may qualify up to 400% FPL. Monthly installments capped at 5% of gross monthly income.','policy')
    summary=doc('Learn more by calling the financial assistance office.','summary')
    r=evaluate([app,policy,summary],complete=True,current_fpl_year=2026)
    assert r['application_fpl_year'].status=='FAIL'
    assert r['application_installments'].status=='FAIL' # absent in *application* despite policy
    assert r['summary_income'].status=='FAIL' # policy does not rescue summary
    assert r['application_contact'].status=='PASS'

def test_explicit_deadline_and_asset_check():
    a=doc('You have up to 240 days after receiving services to submit your application. Provide two bank statements.','policy')
    res=evaluate([a],complete=False)
    assert res['no_deadline'].status=='FAIL'
    assert res['no_asset_checks'].status=='FAIL'

def test_immigration_exclusion_cannot_be_hidden():
    a=doc('Undocumented patients are ineligible for financial assistance.','policy')
    res=evaluate([a],complete=True)
    assert res['no_immigration_barrier'].status=='FAIL'

def test_current_fpl_and_installments():
    text='NYS Uniform Financial Assistance Application. 2026 FPL Guidelines. Applicants qualify up to 400% FPL. Monthly installments capped at 5% of gross monthly income.'
    res=evaluate([doc(text)],complete=True,current_fpl_year=2026)
    assert res['application_fpl_year'].status=='PASS'
    assert res['application_max_fpl'].status=='PASS'
    assert res['application_installments'].status=='PASS'
    assert res['uniform_application'].status=='REVIEW' # title is not evidence of ENTIRE document

def test_summary_psa_requires_summary_only():
    app=doc('Our Primary Service Area includes Kings County.',typ='policy')
    summary=doc('To apply for financial assistance, call 212-555-1212. Household incomes through 400% FPL are eligible.',typ='summary')
    r=evaluate([app,summary],complete=True)
    assert r['summary_psa'].status=='FAIL'
    assert r['summary_application'].status=='PASS'
    assert r['summary_income'].status=='PASS'

def test_unretrieved_docs_do_not_turn_into_absence_failures():
    r=evaluate([doc('Missing PDF','landing')],complete=False)
    assert all(f.status=='REVIEW' for f in r.values())

def test_every_decision_has_evidence():
    r=evaluate([doc('Application: call 212-555-1234. Uniform Financial Assistance Application 2026 FPL Guidelines. Monthly installment payments capped at 5% of gross monthly income.')],complete=True,current_fpl_year=2026)
    assert all(f.url and f.evidence for f in r.values() if f.status in ('PASS','FAIL'))


def test_negative_asset_language_is_not_false_fail():
    r=evaluate([doc('You do not need to provide bank statements when applying for assistance.','policy')],complete=True)
    assert r['no_asset_checks'].status!='FAIL'

def test_vague_summary_does_not_invent_income_thresholds():
    r=evaluate([doc('Your household income may determine eligibility for care.','summary')],complete=True)
    assert r['summary_income'].status!='PASS'
