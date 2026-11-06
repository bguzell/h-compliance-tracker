"""Public interface: 2025 historical baseline is NEVER labeled current compliance."""
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import select,func
from src.database import init_db,session_factory
from src.models import Hospital,ChangeEvent,SourceDocument,CriterionResult
from src.criteria import CRITERIA
from src.config import S
from src.standards import reference_standard
from src.accessibility import grade_label

st.set_page_config(page_title='NY Hospital Financial Assistance Tracker',page_icon='🏥',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1340px}
h1,h2,h3{letter-spacing:-.025em;color:#18343a}
a{color:#12636d !important;text-decoration:underline}
.stMetric{background:#fff;border:1px solid #d8e3e0;border-radius:12px;padding:12px}
[data-testid="stSidebar"]{background:#edf4f2}
[data-testid="stExpander"]{border:1px solid #d5e1de;border-radius:12px}
div[data-testid="stMarkdownContainer"] p{line-height:1.6}
*:focus-visible{outline:3px solid #b15b00!important;outline-offset:2px!important}
</style>''',unsafe_allow_html=True)

@st.cache_resource
def boot():
    init_db(); return session_factory()

@st.cache_data(ttl=30)
def load_hospitals():
    with boot()() as session:
        hs=session.scalars(select(Hospital).order_by(Hospital.name)).all()
        languages={}
        for hid,lang in session.execute(select(SourceDocument.hospital_id,SourceDocument.language)).all():
            if lang and lang!='Not confirmed':languages.setdefault(hid,set()).add(lang)
        results={}
        for hid,cid,status in session.execute(select(CriterionResult.hospital_id,CriterionResult.criterion_id,CriterionResult.status)).all():
            results.setdefault(hid,{})[cid]=status
        return [dict(id=h.hospital_id,name=h.name,system=h.system,city=h.city,address=h.address,county=h.county or '',historical=h.historical_grade,grade=h.grade,provisional=bool(h.provisional),source_status=h.source_status,review_count=h.review_count,lat=h.latitude,lon=h.longitude,url=h.hfa_url,link_provenance=h.hfa_url_provenance,langs=h.historical_languages or '',current_languages=sorted(languages.get(h.hospital_id,[])),criterion_results=results.get(h.hospital_id,{}),checked=str(h.last_checked)[:16] if h.last_checked else '') for h in hs]

def overview():
    st.title('Are New York hospitals meeting their financial-assistance obligations?')
    st.write('A public-interest tracker of the financial-assistance information hospitals make available, designed to help advocates identify barriers affecting low-income patients.')
    st.info('**Evidence status:** The September 2025 CSSNY review is historical. Current grades are provisional until current hospital documents have been retrieved and reviewed. This tool does not determine anyone’s personal eligibility.')
    records=load_hospitals()
    if not records:
        st.warning('The database is empty. Run `python -m src.cli seed` once.');return
    df=pd.DataFrame(records)
    st.markdown('### Current monitoring status')
    audited=df[df.source_status.isin(['CURRENT','PARTIAL_REVIEW'])]
    final=audited[~audited.provisional]
    gradeA=(final.grade=='A').sum(); needs_review=(df.review_count>0).sum()
    recently=df[df.checked!='']
    cols=st.columns(5)
    cols[0].metric('Facilities in roster',len(df),help='212 hospitals in the 2025 baseline; current roster verification runs separately.')
    cols[1].metric('Fully verified A',str(gradeA),help='Current A grades with no unresolved review. Historical grades excluded.')
    cols[2].metric('Require verification',int(needs_review))
    cols[3].metric('Checked this cycle',len(recently))
    cols[4].metric('Current verified A rate',f'{gradeA/len(final):.1%}' if len(final) else 'Not yet available')
    with st.expander('How should I read these results?'):
        st.write('PASS means the document evidence supports the requirement. FAIL means the system found a potential gap. REVIEW means evidence is missing, ambiguous or incomplete. A provisional grade cannot be treated as a legal finding.')
    st.markdown('### Explore the hospitals')
    left,right=st.columns([1,1])
    with left: search=st.text_input('Search by hospital name',placeholder='Start typing a hospital…')
    with right: grade_filter=st.selectbox('2025 historical grade (comparison only)',['All','A','B','C','D','F'])
    cols=st.columns(3)
    systems=sorted(x for x in df.system.fillna('').unique() if x)
    with cols[0]: system=st.selectbox('Hospital system',['All']+systems)
    with cols[1]:
        counties=sorted(x for x in df.county.unique() if x)
        county=st.selectbox('County (only reconciled)',['All']+counties)
    with cols[2]: status=st.selectbox('Current evidence status',['All','NOT_CHECKED','CURRENT','PARTIAL_REVIEW','UNAVAILABLE','URL_UNRESOLVED'])
    filtered=df.copy()
    if search: filtered=filtered[filtered.name.str.contains(search,case=False,regex=False,na=False)]
    if grade_filter!='All':filtered=filtered[filtered.historical==grade_filter]
    if system!='All': filtered=filtered[filtered.system==system]
    if county!='All':filtered=filtered[filtered.county==county]
    if status!='All':filtered=filtered[filtered.source_status==status]
    cols=st.columns(3)
    with cols[0]: criterion=st.selectbox('Specific CSSNY measure',['All']+[c.label for c in CRITERIA])
    with cols[1]: criterion_status=st.selectbox('Measure result',['Any','PASS','FAIL','REVIEW','N/A'])
    with cols[2]:
        all_langs=sorted({lang for record in records for lang in record['current_languages']})
        lang=st.selectbox('Current material language',['All']+all_langs)
    if lang!='All': filtered=filtered[filtered.current_languages.apply(lambda langs:lang in langs)]
    if criterion!='All':
        cid=next(c.id for c in CRITERIA if c.label==criterion)
        filtered=filtered[filtered.criterion_results.apply(lambda results:results.get(cid,'REVIEW')==criterion_status if criterion_status!='Any' else cid in results)]
    elif criterion_status!='Any':
        filtered=filtered[filtered.criterion_results.apply(lambda results:criterion_status in results.values())]
    st.caption(f'{len(filtered)} facilities match. Historical grade is not today’s grade.')
    mapped=filtered[filtered.lat.notna() & filtered.lon.notna()]
    st.markdown('#### New York State facility map')
    if len(mapped):
        plot=mapped.copy()
        plot['Current finding']=plot.apply(lambda x:('Provisional ' if x['provisional'] else '')+(x['grade'] or 'REVIEW — unchecked'),axis=1)
        plot['2025 grade']=plot['historical']
        fig=px.scatter_mapbox(plot,lat='lat',lon='lon',hover_name='name',hover_data={'system':True,'city':True,'address':True,'Current finding':True,'2025 grade':True,'lat':False,'lon':False},color='Current finding',zoom=5,center={'lat':42.7,'lon':-75.3},height=430)
        fig.update_layout(mapbox_style='open-street-map',margin=dict(l=0,r=0,t=0,b=0),legend=dict(orientation='h'))
        st.plotly_chart(fig,use_container_width=True)
        st.caption('Dots display only facilities with coordinates matched to official New York State records. Select the facility in the accessible table below for its evidence.')
    else:
        st.info('Map markers will appear after official NYSDOH facility coordinates are reconciled (`python -m src.cli roster`). No approximate locations have been invented.')
    display=filtered[['name','city','system','historical','grade','review_count','source_status','checked','url','id']].copy()
    display['grade']=display['grade'].fillna('Pending review')
    display.columns=['Hospital','City','System','2025 grade','Current grade (provisional)','Reviews','Source status','Last checked (UTC)','HFA source (unverified)','Facility ID']
    st.dataframe(display,hide_index=True,use_container_width=True,height=420,column_config={'HFA source (unverified)':st.column_config.LinkColumn('HFA source (unverified)',display_text='View official source'),'Facility ID':st.column_config.TextColumn('Facility ID')})
    if len(filtered):
        option=st.selectbox('Open hospital evidence record',options=filtered.id.tolist(),format_func=lambda value:next((f'{r["name"]} — {r["city"]} ({r["id"]})' for r in records if r['id']==value),value))
        if st.button('View 17 compliance measures',type='primary'):
            st.query_params['hospital_id']=option; st.rerun()
    st.markdown('### September 2025 CSSNY audit — historical benchmark')
    st.caption('Historical statistics are shown as a fixed comparison baseline; they do not represent current compliance.')
    hist=df.historical.value_counts().reindex(['A','B','C','D','F'],fill_value=0)
    fig=px.bar(x=hist.index,y=hist.values,labels={'x':'CSSNY historical grade','y':'Number of facilities'},text=hist.values)
    fig.update_traces(marker_color='#17656e',textposition='outside');fig.update_layout(showlegend=False,height=260,margin=dict(l=0,r=0,t=15,b=0))
    st.plotly_chart(fig,use_container_width=True)
    st.markdown('### Recent verified updates')
    with boot()() as session:
        recent=session.execute(select(ChangeEvent,Hospital.name).join(Hospital,ChangeEvent.hospital_id==Hospital.hospital_id).order_by(ChangeEvent.timestamp.desc()).limit(8)).all()
        for event,name in recent:
            st.write(f'**{str(event.timestamp)[:16]} UTC · {name}** — {event.reason}; {event.old_grade or "pending"} → {event.new_grade or "pending"}')
    if not recent: st.caption('No live-source refreshes yet. Start the separate updater to populate this feed.')

SF=boot()
selected=st.query_params.get('hospital_id','')
section=st.sidebar.radio('Navigate',['Dashboard','Hospital detail','Methodology','Review queue'],index=1 if selected else 0)
st.sidebar.markdown('**Current FPL reference: '+str(reference_standard()['year'])+'**')
st.sidebar.caption('Year shown from checked NYSDOH guidance where available; otherwise a configured fallback requiring verification.')
if section=='Dashboard': overview()
elif section=='Hospital detail':
    from pages.hospital_detail import render
    render(SF,selected)
elif section=='Methodology':
    from pages.methodology import render
    render()
else:
    from pages.review_queue import render
    render(SF)
