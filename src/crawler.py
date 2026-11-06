"""Same-hospital source discovery. A missing or inaccessible document is *not* proof of violation."""
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from urllib.parse import urljoin, urlsplit, urldefrag
from bs4 import BeautifulSoup
from .sources import Fetcher, SourceUnavailable, hospital_link_allowed
from .pdf_parser import extract
from .config import S

@dataclass
class CrawledDocument:
    url: str
    doc_type: str
    title: str
    language: str
    text: str
    content_hash: str
    etag: str|None
    last_modified: str|None
    method: str
    retrieved_at: datetime

@dataclass
class CrawlResult:
    documents: list[CrawledDocument]
    errors: list[str]
    complete: bool
    unavailable: bool=False
    unchanged: bool=False

def doc_type_of(label,url):
    s=(label+' '+url).lower().replace('_',' ').replace('-',' ')
    if any(q in s for q in ['plain language','policy summary','plain-language','plain_language','plainlanguage','easy read']): return 'summary'
    if any(q in s for q in ['uniform application','financial assistance application','financial aid application','charity care application','faf application','apply for financial aid']): return 'application'
    if any(q in s for q in ['financial assistance policy','financial aid policy','charity care policy','policy statement','financial assistance policies']): return 'policy'
    if any(q in s for q in ['financial assistance','financial aid','charity care','discount program']): return 'supplemental'
    return 'other'

def language_of(s):
    languages=['Spanish','Arabic','Bengali','Chinese','French','Haitian Creole','Hindi','Italian','Japanese','Korean','Nepali','Polish','Russian','Urdu','Yiddish','Burmese','Portuguese','English']
    return next((lang for lang in languages if lang.lower() in s.lower()), 'Not confirmed')

def discover_links(content,base_url):
    soup=BeautifulSoup(content,'html.parser'); found=[]; seen=set()
    for a in soup.find_all('a',href=True):
        dest=urldefrag(urljoin(base_url,a.get('href','')))[0]
        label=' '.join(a.stripped_strings).strip() or a.get('title','')
        if not hospital_link_allowed(base_url,dest): continue
        typ=doc_type_of(label,dest)
        # PDFs, DOCX, and specifically labeled assistance pages only.
        if typ=='other' or dest in seen: continue
        if dest.rstrip('/')==base_url.rstrip('/'): continue
        seen.add(dest); found.append((dest,typ,label or dest,language_of(label+' '+dest)))
    # specific docs first, then supplemental; a site may link dozens of identical language copies
    ranks={'application':0,'summary':1,'policy':2,'supplemental':3}
    return sorted(found,key=lambda item:(ranks.get(item[1],4),item[0]))

def crawl_hospital(url,fetcher=None,existing=None,allow_ocr=False):
    own=fetcher is None
    fetcher=fetcher or Fetcher()
    existing=existing or {}
    docs=[]; errors=[]
    def convert(url,typ,title,lang,raw):
        txt,method=extract(raw['body'],raw['type'],raw['url'],allow_ocr)
        if not txt or len(txt)<65: errors.append(f'{typ}: insufficient extractable text: {url}')
        docs.append(CrawledDocument(raw['url'],typ,title,lang,txt,sha256(raw['body']).hexdigest(),raw['headers'].get('etag'),raw['headers'].get('last-modified'),method,datetime.now(timezone.utc)))
    try:
        prev=existing.get(url)
        landing=fetcher.fetch(url,etag=prev.etag if prev else None,last_modified=prev.last_modified if prev else None)
        if landing['not_modified']:
            # Revalidate known docs separately only if the landing already exists.
            if not prev: return CrawlResult([],['304 but no local content'],False,True)
            landing=dict(url=url,type='text/html',body=prev.extracted_text.encode(),headers={})
            # Existing plain extracted text has no links! Re-using it would incorrectly imply zero docs.
            # Use a full landing refresh to enumerate links.
            landing=fetcher.fetch(url)
        convert(url,'landing','Financial assistance webpage','Not confirmed',landing)
        candidates=discover_links(landing['body'],landing['url'])[:S.max_documents]
        # If list truncated, completeness impossible.
        all_candidates=discover_links(landing['body'],landing['url'])
        if len(all_candidates)>S.max_documents: errors.append(f'Too many document links ({len(all_candidates)}) to check within configured limit')
        for doc_url,typ,title,lang in candidates:
            try:
                raw=fetcher.fetch(doc_url)
                if raw['not_modified']: raw=fetcher.fetch(doc_url)
                convert(doc_url,typ,title,lang,raw)
            except SourceUnavailable as exc: errors.append(f'{doc_url}: {exc}')
        return CrawlResult(docs,errors,complete=not errors)
    except SourceUnavailable as exc:
        return CrawlResult([], [f'Landing page {url}: {exc}'],False,True)
    finally:
        if own: fetcher.close()
