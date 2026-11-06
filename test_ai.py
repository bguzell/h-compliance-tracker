from src.ai_extractor import verify_response

def test_fabricated_quote_discarded():
    payload={'facts':[{'field':'summary_psa','value':'YES','evidence':'There is no restriction','confidence':.99,'document_type':'summary'}]}
    assert verify_response(payload,'Our hospital helps patients.','summary')==[]

def test_quote_verified_but_not_grade():
    payload={'facts':[{'field':'summary_application','value':'YES','evidence':'Applications available online','confidence':.6,'document_type':'summary'}]}
    facts=verify_response(payload,'Applications available online for patients','summary')
    assert len(facts)==1
    assert not hasattr(facts[0],'grade')
