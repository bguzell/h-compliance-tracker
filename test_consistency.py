from types import SimpleNamespace
from src.consistency import compare,assess_consistency

def doc(typ,text):return SimpleNamespace(doc_type=typ,text=text,url=f'https://hospital.example.org/{typ}',title=typ)

def test_conflicting_fpl_sources():
    ds=[doc('application','Financial assistance eligibility up to 400% FPL.'),doc('policy','Financial assistance eligibility up to 300% FPL.')]
    result,conflicts=assess_consistency(ds,True)
    assert result.status=='FAIL' and conflicts
    assert '400' in result.evidence and '300' in result.evidence

def test_no_proof_of_consistency_returns_review():
    result,conflicts=assess_consistency([doc('application','Hello'),doc('policy','Hi')],True)
    assert result.status=='REVIEW' and not conflicts
