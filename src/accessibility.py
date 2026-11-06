"""Screen-reader-compatible text states, plain-language labels."""
STATUS={'PASS':'PASS — Requirement appears met','FAIL':'FAIL — Potential compliance gap','REVIEW':'REVIEW — Human verification required','N/A':'N/A — Not applicable'}
GRADE_DESC={'A':'No confirmed compliance errors','B':'1–3 confirmed errors','C':'4–6 confirmed errors','D':'7–9 confirmed errors','F':'10+ errors or automatic-fail condition'}

def status_label(status): return STATUS.get(status,'Not checked')
def grade_label(grade,provisional=True):
    return ('Provisional ' if provisional else '')+(grade or 'Pending review')
