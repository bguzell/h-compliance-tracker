"""Check applicable FPL year against NYSDOH official Uniform Application listing."""
import json,re
from datetime import datetime,timezone
from .config import ROOT,S,SOURCE_DOH_HOSP
from bs4 import BeautifulSoup
from .sources import Fetcher

STATE_FILE=ROOT/'data/current/fpl_standard.json'

def discover_guideline_year(html):
    soup=BeautifulSoup(html,'html.parser')
    # Year must be attached to current official uniform application listing.
    sections=soup.get_text(' ',strip=True)
    years=[]
    for m in re.finditer(r'\b(20\d{2})\b',sections):
        nearby=sections[m.end():m.end()+270]
        if re.search(r'Hospital Financial Assistance Application',nearby,re.I): years.append(int(m.group(1)))
    return max(years) if years else None

def check_current_fpl(fetcher=None):
    own=fetcher is None; fetcher=fetcher or Fetcher()
    try:
        res=fetcher.fetch(SOURCE_DOH_HOSP)
        year=discover_guideline_year(res['body'])
        if not year or year<2024 or year>datetime.now(timezone.utc).year+1:
            raise ValueError('Official page did not expose a credible current application year')
        STATE_FILE.parent.mkdir(exist_ok=True,parents=True)
        data={'year':year,'source':SOURCE_DOH_HOSP,'verified_utc':datetime.now(timezone.utc).isoformat(),'method':'DOH published application listing'}
        STATE_FILE.write_text(json.dumps(data,indent=2))
        return data
    finally:
        if own: fetcher.close()

def reference_standard():
    if STATE_FILE.exists():
        try:
            d=json.loads(STATE_FILE.read_text())
            if 2024<=int(d['year'])<=datetime.now(timezone.utc).year+1:return d
        except (ValueError,KeyError,TypeError):pass
    return {'year':S.fpl_year,'source':SOURCE_DOH_HOSP,'verified_utc':None,'method':'Configured fallback; verify against current DOH guidance'}
