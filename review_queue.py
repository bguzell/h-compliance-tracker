import hmac
import streamlit as st
from sqlalchemy import select
from src.models import Hospital,CriterionResult
from src.criteria import BY_ID
from src.config import S
from src.updater import record_review

def render(SF):
    st.title('Evidence review queue')
    st.write('For authorized community reviewers. Each decision is tied to the current content hash and is invalidated when hospital documents change.')
    if not S.admin_password:
        st.error('Reviewer actions are disabled until HFA_ADMIN_PASSWORD is set in the environment.');return
    if 'review_auth' not in st.session_state:st.session_state['review_auth']=False
    if not st.session_state['review_auth']:
        candidate=st.text_input('Reviewer password',type='password')
        if st.button('Unlock review queue'):
            if hmac.compare_digest(candidate,S.admin_password):st.session_state['review_auth']=True;st.rerun()
            else:st.error('Incorrect password')
        return
    with SF() as session:
        q=session.execute(select(CriterionResult,Hospital).join(Hospital,CriterionResult.hospital_id==Hospital.hospital_id).where(CriterionResult.status=='REVIEW').order_by(Hospital.name).limit(2500)).all()
        st.metric('Criteria awaiting verification',len(q))
        options=[(result.hospital_id,result.criterion_id) for result,h in q]
        if not options:
            st.success('No criteria awaiting review.');return
        choice=st.selectbox('Find a review case',options,format_func=lambda pair: next((f'{h.name}: {BY_ID[r.criterion_id].label}' for r,h in q if r.hospital_id==pair[0] and r.criterion_id==pair[1]),str(pair)))
        r,h=next((r,h) for r,h in q if r.hospital_id==choice[0] and r.criterion_id==choice[1])
        st.subheader(h.name+' — '+BY_ID[r.criterion_id].label)
        st.write('**Reason:**',r.review_reason or 'Requires confirmation')
        st.write('**Automated finding:**',r.explanation or 'Unresolved')
        st.write('**Evidence:**',r.evidence or 'No source evidence retrieved')
        if r.source_url: st.markdown(f'[Open original source]({r.source_url})')
        st.caption(f'Extraction: {r.extraction_method or "N/A"}; confidence: {r.confidence if r.confidence is not None else "N/A"}; source hash: {r.source_hash or "none"}')
        note=st.text_area('Reviewer reasoning / evidence note (required)')
        decision=st.selectbox('Judgment',['REVIEW','PASS','FAIL'])
        pending_source=h.hfa_url_provenance in ('SAME_SYSTEM_CANDIDATE','SYSTEM_POLICY_NAMES_PARENT')
        if pending_source: st.warning('Shared-system source coverage has not been verified for this facility. Use the administrator `verify-source` command after examining the official facility documents.')
        can_decide=bool(not pending_source and len(note.strip())>=20 and h.current_page_hash and h.source_status in ('CURRENT','PARTIAL_REVIEW'))
        if st.button('Record reviewed decision',disabled=not can_decide,type='primary'):
            try:
                record_review(h.hospital_id,r.criterion_id,h.current_page_hash,decision,note)
                st.success('Saved source-bound decision; grade recomputed.');st.cache_data.clear();st.rerun()
            except ValueError as exc: st.error(str(exc))
        if not can_decide: st.caption('At least 20 characters of reasoning and a current successfully retrieved hospital landing page are required. If no quote exists, the note becomes a cited human absence check.')
