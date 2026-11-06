from src.geo_facts import psa_county_mentions,COUNTIES

def test_counties_only_from_service_area():
    result=psa_county_mentions('Our hospital is in Albany County. Primary Service Area includes Kings County and Queens County.')
    assert result==['Kings','Queens']

def test_county_names_unrelated_are_not_inferred():
    assert psa_county_mentions('Financial assistance in Albany County.')==[]
