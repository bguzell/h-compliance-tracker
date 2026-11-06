"""Deterministic CSSNY grades. REVIEW never becomes an unqualified final grade."""
from dataclasses import dataclass
from .config import S

@dataclass(frozen=True)
class GradeResult:
    grade: str | None
    provisional: bool
    fail_count: int
    review_count: int
    label: str

def grade_from_error_count(n: int, automatic_fail: bool=False) -> str:
    if automatic_fail or n >= 10: return 'F'
    if n == 0: return 'A'
    if n <= 3: return 'B'
    if n <= 6: return 'C'
    return 'D'

def grade_criteria(statuses: dict[str,str], auto_fail: dict[str,bool] | None=None) -> GradeResult:
    rules=auto_fail if auto_fail is not None else {'application_posted':S.auto_fail_missing_application,'uniform_application':S.auto_fail_missing_uniform_application,'policy_posted':S.auto_fail_missing_policy_statement}
    vals=list(statuses.values())
    for value in vals:
        if value not in ('PASS','FAIL','REVIEW','N/A'): raise ValueError(value)
    f=vals.count('FAIL'); r=vals.count('REVIEW')
    # Explicit fail is needed before imposing automatic F. Incomplete/unknown is never an auto fail.
    auto=any(enabled and statuses.get(cid)=='FAIL' for cid,enabled in rules.items())
    g=grade_from_error_count(f,auto)
    if r:
        if not any(x in ('PASS','FAIL') for x in vals):
            return GradeResult(None,True,f,r,f'Grade pending review · {r} criteria')
        return GradeResult(g,True,f,r,f'Provisional {g} · {r} require review')
    return GradeResult(g,False,f,r,f'Grade {g}')
