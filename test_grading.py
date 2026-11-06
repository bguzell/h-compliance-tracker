import pytest
from src.grader import grade_from_error_count,grade_criteria
from src.cli import validate_baseline
from src.criteria import CRITERIA

@pytest.mark.parametrize('n,grade',[(0,'A'),(1,'B'),(3,'B'),(4,'C'),(6,'C'),(7,'D'),(9,'D'),(10,'F'),(17,'F')])
def test_threshold(n,grade):assert grade_from_error_count(n)==grade

def test_auto_fail_policy_documented():
    s={c.id:'PASS' for c in CRITERIA};s['policy_posted']='FAIL'
    assert grade_criteria(s).grade=='F'
    assert grade_criteria(s,{'policy_posted':False}).grade=='B'

def test_review_is_never_a_final_grade():
    s={c.id:'REVIEW' for c in CRITERIA}
    v=grade_criteria(s);assert v.grade is None and v.provisional and v.review_count==17
    s['summary_income']='PASS';v=grade_criteria(s)
    assert v.provisional and v.review_count==16

def test_baseline_distribution_and_discrepancy():
    result=validate_baseline()
    assert result['facilities']==212
    assert result['baseline_grades']=={'A':14,'B':116,'C':31,'D':10,'F':41}
    assert result['historical_grade_mismatches']==[]
    assert result['discrepancy_count']==17
