import streamlit as st
from sqlalchemy import select
from src.models import Hospital, CriterionResult, SourceDocument
from src.criteria import CRITERIA
from src.accessibility import grade_label,status_label
from src.config import SOURCE_HFA_LAW
from src.geo_facts import psa_county_mentions

def render(SF,selected=''):
    with SF() as session:
        hospitals=session.scalars(select(Hospital).order_by(Hospital.name)).all()
        if not hospitals: st.warning('No facilities imported.');return
        ids=[h.hospital_id for h in hospitals]
        value=selected if selected in ids else ids[0]
        chosen=st.selectbox('Choose hospital / facility',ids,index=ids.index(value),format_func=lambda ident:next(f'{h.name} — {h.city} ({h.hospital_id})' for h in hospitals if h.hospital_id==ident))
        h=session.get(Hospital,chosen)
        results={c.criterion_id:c for c in session.scalars(select(CriterionResult).where(CriterionResult.hospital_id==chosen)).all()}
        docs=session.scalars(select(SourceDocument).where(SourceDocument.hospital_id==chosen)).all()
        st.title(h.name)
        st.write(f'**{h.system or "Independent"}** · {h.address}, {h.city}, NY {h.zipcode}')
        if h.hfa_url:
            st.markdown(f'[Hospital financial-assistance source (check facility coverage)]({h.hfa_url})')
        else: st.error('Source URL is unresolved; official HFA page must be located.')
        if h.hfa_url_provenance in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT'):
            st.warning('This is a candidate shared-system page. Current findings remain under REVIEW until an authorized reviewer confirms it applies to this facility.')
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Current assessment',grade_label(h.grade,h.provisional))
        c2.metric('Criteria to review',h.review_count)
        c3.metric('Confirmed findings',h.noncompliant_count)
        c4.metric('2025 CSSNY grade',h.historical_grade or '—')
        st.warning('A score is not proof of legal non-compliance. The 2025 score is historical; current results are source-linked and remain provisional while evidence needs review.')
        st.caption(f'Current source: {h.source_status} · Last checked: {str(h.last_checked)[:19]+" UTC" if h.last_checked else "Not checked"} · Facility ID: {h.hospital_id}')
        if h.id_needs_reconciliation: st.error('Facility identifier missing from original CSSNY tracker. Reconcile with NYSDOH before claiming entity identity.')
        if h.last_error: st.info('Data collection warning: '+h.last_error)
        st.markdown('## All 17 CSSNY audit measures')
        group_order=[('website','Website and overall materials'),('cross_document','Document consistency'),('application','Financial-assistance application only'),('summary','Plain-language summary only')]
        for scope,heading in group_order:
            st.subheader(heading)
            for c in [item for item in CRITERIA if item.scope==scope]:
                finding=results.get(c.id)
                stat=finding.status if finding else 'REVIEW'
                with st.expander(f'{status_label(stat)} · {c.label}'):
                    st.markdown('**What the rule requires**')
                    st.write(c.requirement)
                    st.markdown('**Why this matters for patients**')
                    st.write(c.why)
                    st.markdown('**What we found**')
                    st.write(finding.explanation if finding and finding.explanation else 'Not enough verified source evidence yet.')
                    if finding and finding.review_reason and stat=='REVIEW':st.write('**Manual verification needed:** '+finding.review_reason)
                    st.markdown('**Evidence**')
                    st.write(finding.evidence if finding and finding.evidence else 'No verified excerpt. This measure remains under review.')
                    if finding and finding.source_url:
                        st.markdown(f'**Source document:** [{finding.source_document_title or "View source"}]({finding.source_url})')
                        st.caption(f'Origin: {finding.source_document_type or "unknown"} · {finding.source_page or "section unavailable"} · Method: {finding.extraction_method or "unknown"} · Retrieved: {str(finding.retrieved_at)[:19] if finding.retrieved_at else "unknown"} UTC')
                    st.markdown(f'[Read the applicable law or guidance]({c.law})')
        st.markdown('## Current documents inspected')
        if docs:
            for d in docs:
                st.markdown(f'- **{d.doc_type.upper()}** · [{d.title}]({d.url}) · {str(d.retrieved_at)[:19]} UTC · {d.language} · `{d.content_hash[:12] if d.content_hash else ""}`')
            langs=sorted({d.language for d in docs if d.language and d.language!='Not confirmed'})
            st.write('**Detected document languages:** '+(', '.join(langs) if langs else 'Not reliably determined'))
        else:st.info('No current documents have been collected. 2025 language availability is not treated as current.')
        st.caption(f'For research only. Language availability in the 2025 baseline: {h.historical_languages or "Not recorded"} (may have changed).')
        st.markdown('## Primary service area — county names found')
        psa_counties=sorted({county for d in docs for county in psa_county_mentions(d.extracted_text or '')})
        st.write(', '.join(psa_counties) if psa_counties else 'No county names reliably extracted near a primary-service-area statement.')
        st.caption('These are mentions in current posted documents, NOT an official or complete service-area boundary determination.')
        st.markdown('## Inconsistencies and review warnings')
        contradictions=[r for r in results.values() if r.criterion_id=='consistent']
        if contradictions and contradictions[0].status=='FAIL':st.error(contradictions[0].evidence or 'Conflicting materials detected')
        else:st.write('No verified contradiction has been established. This does not establish consistency.')
