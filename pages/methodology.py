import streamlit as st
from src.criteria import CRITERIA
from src.standards import reference_standard
from src.config import S,SOURCE_DOH,SOURCE_DOH_HOSP,SOURCE_HFA_LAW,SOURCE_DOHSOCRATA

def render():
    st.title('Methodology and public limitations')
    st.info('AI assists with document extraction. Compliance grades are produced by transparent deterministic rules based on the CSSNY methodology and cited evidence. The model cannot assign grades.')
    st.markdown('''
### What this tool does
1. Starts with CSSNY’s **212-facility September 2025 baseline**, kept separate from today’s results.
2. Looks for official hospital financial-assistance materials and follows same-site links.
3. Extracts posted text from HTML, PDFs and DOCX. OCR can be enabled for scanned PDFs.
4. Applies rules within the correct document scope: application, summary, website overall, or cross-document comparison.
5. Displays source excerpts, explicit unknowns, and a human-review queue.
6. Stores *current* documents and minimal change metadata, not previous full versions.

### How to interpret a result
**PASS:** specific cited evidence supports the criterion, or a documented completeness-based absence check.

**FAIL:** specific evidence indicates a compliance gap, or a documented absence check for a required element.

**REVIEW:** missing pages, blocked scraping, low confidence, geographic interpretation, template equivalence, incomplete retrieval or disagreement needing human judgment.

**N/A:** applies only when a reviewer establishes that a requirement genuinely cannot apply. It is never a synonym for missing evidence.

A provisional grade counts confirmed FAILs but should **not** be treated as final. It can change after review.

### Major limitations
- The crawler cannot demonstrate that every possible page on a hospital website has been inspected; missing document links require human review.
- Naming a form “Uniform Application” does not establish that all required sections are present. That test remains under review unless compared to the official template.
- A service-area description alone does not prove its boundaries comply with NYSDOH guidance. Boundary compliance requires human review.
- Bank-statement language is flagged conservatively, because the 2025 CSSNY audit treats it as an impermissible asset check. Interpretation may require expert confirmation.
- AI-extracted phrases are not legal findings. This prototype does not make individual patient eligibility decisions.
- Retrieved documents may omit material hidden behind interactive portals. Failed retrieval is never converted to confirmed non-compliance.
- Non-English files need qualified language review; linked language names alone are not proof of translation completeness.
''')
    st.markdown('### Grade calculation')
    st.markdown('A = 0 errors; B = 1–3; C = 4–6; D = 7–9; F = 10+ or an automatic-fail criterion. If any criterion is REVIEW, the grade is provisional.')
    st.warning('**Unresolved CSSNY source conflict:** The methodology PDF requires an automatic F if a policy statement is missing. The 2025 spreadsheet does not consistently impose this rule: applying the PDF rule changes 17 historical grades. The software follows the written methodology for **new** records but preserves every 2025 grade untouched. CSSNY confirmation is still needed.')
    st.markdown(f'**Current FPL standard configured: {reference_standard()['year']}.** The NYSDOH hospital information page lists a {reference_standard()['year']} Uniform Application. This setting must be reverified when new state guidance is issued.')
    st.markdown('### Rule inventory')
    st.dataframe([{'ID':c.id,'CSSNY measure':c.label,'Evidence scope':c.scope,'2025 spreadsheet column':c.source_column} for c in CRITERIA],hide_index=True,use_container_width=True)
    st.markdown('### Official reference links')
    st.markdown(f'- [New York State Department of Health — Financial Aid Law]({SOURCE_DOH})\n- [NYSDOH Uniform Application and hospital guidance]({SOURCE_DOH_HOSP})\n- [New York Public Health Law §2807-k]({SOURCE_HFA_LAW})\n- [NYSDOH official facility geospatial registry]({SOURCE_DOHSOCRATA})')
    st.caption('2025 input: CSSNY manual audit and methodology provided with the challenge. Last source verification for application benchmark: November 2026. This is not legal advice.')
