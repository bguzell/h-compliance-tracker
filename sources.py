"""Read-only public-source retriever, URL guardrails, conditional requests, bounded bytes."""
import ipaddress, socket, time
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import httpx
from .config import S

MAX_BYTES = 14 * 1024 * 1024
ALLOWED_SCHEMES=('https', 'http')

class SourceUnavailable(Exception): pass

def validate_url(url:str, enforce_public_dns=True):
    p=urlsplit((url or '').strip())
    if p.scheme not in ALLOWED_SCHEMES or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise SourceUnavailable('Unsupported or unsafe URL')
    if p.hostname.lower() in ('localhost','localhost.localdomain') or p.hostname.lower().endswith(('.local','.internal')):
        raise SourceUnavailable('Non-public hostname')
    if enforce_public_dns:
        try: infos=socket.getaddrinfo(p.hostname,None,proto=socket.IPPROTO_TCP)
        except OSError as exc: raise SourceUnavailable(f'DNS failed: {exc}') from exc
        for info in infos:
            try: ip=ipaddress.ip_address(info[4][0])
            except ValueError: raise SourceUnavailable('Invalid IP')
            if not ip.is_global: raise SourceUnavailable('Private or reserved IP')
    return url

def parent_domain(host):
    # Conservative: exact host or direct sibling under same registrable-like tail.
    h=(host or '').lower().removeprefix('www.')
    chunks=h.split('.')
    return '.'.join(chunks[-3:] if chunks[-2:] in (['co','uk'],['com','au']) else chunks[-2:])

def hospital_link_allowed(seed_url, candidate_url):
    a=urlsplit(seed_url); b=urlsplit(candidate_url)
    if b.scheme not in ALLOWED_SCHEMES: return False
    return parent_domain(a.hostname)==parent_domain(b.hostname)

class Fetcher:
    def __init__(self,transport=None, robots=True):
        self.client=httpx.Client(timeout=S.timeout,follow_redirects=False,headers={'User-Agent':S.user_agent,'Accept':'text/html,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document;q=0.9,*/*;q=0.3'},transport=transport)
        self.robots=robots; self.robot_cache={}
    def close(self): self.client.close()
    def can_fetch(self,url):
        if not self.robots: return True
        p=urlsplit(url); root=f'{p.scheme}://{p.netloc}'
        if root not in self.robot_cache:
            parser=RobotFileParser(); parser.set_url(root+'/robots.txt')
            try:
                # RobotFileParser internally uses urllib; if blocked conservatively allow
                # site fetch because robots endpoint was unreachable, but log it.
                parser.read(); self.robot_cache[root]=parser
            except Exception: self.robot_cache[root]=None
        r=self.robot_cache[root]
        return r is None or r.can_fetch(S.user_agent,url)
    def fetch(self,url,etag=None,last_modified=None, retries=2):
        validate_url(url)
        if not self.can_fetch(url): raise SourceUnavailable('robots.txt disallows fetch')
        headers={}
        if etag: headers['If-None-Match']=etag
        if last_modified: headers['If-Modified-Since']=last_modified
        for attempt in range(retries+1):
            try:
                here=url
                for redirect in range(5):
                    validate_url(here)
                    with self.client.stream('GET',here,headers=headers) as resp:
                        if resp.status_code in (301,302,303,307,308):
                            dest=urljoin(here,resp.headers.get('location',''))
                            if not hospital_link_allowed(url,dest): raise SourceUnavailable('Redirect crossed to an unapproved host')
                            here=dest; continue
                        if resp.status_code==304: return {'not_modified':True,'url':here,'headers':dict(resp.headers),'body':b'','type':''}
                        if resp.status_code in (429,500,502,503,504): raise httpx.HTTPStatusError('retryable upstream',request=resp.request,response=resp)
                        if resp.status_code>=400: raise SourceUnavailable(f'HTTP {resp.status_code}')
                        data=bytearray()
                        for chunk in resp.iter_bytes():
                            data.extend(chunk)
                            if len(data)>MAX_BYTES: raise SourceUnavailable('Document exceeds 14 MB safety limit')
                        return {'not_modified':False,'url':here,'headers':dict(resp.headers),'body':bytes(data),'type':resp.headers.get('content-type','').split(';')[0]}
                raise SourceUnavailable('Too many redirects')
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                if attempt>=retries: raise SourceUnavailable(f'Fetch error: {exc}') from exc
                time.sleep(min(2**attempt,3))
        raise SourceUnavailable('Retries exhausted')
