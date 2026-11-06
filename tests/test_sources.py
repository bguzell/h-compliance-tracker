import pytest
from src.sources import validate_url,SourceUnavailable,hospital_link_allowed
from src.crawler import doc_type_of,discover_links
from src.pdf_parser import parse_pdf

def test_block_private_or_unsafe_urls():
    for url in ['file:///etc/passwd','http://127.0.0.1/x','http://localhost/a','https://test.local/private']:
        with pytest.raises(SourceUnavailable):validate_url(url)

def test_same_site_only():
    assert hospital_link_allowed('https://www.hospital.org/aid','https://hospital.org/docs/form.pdf')
    assert not hospital_link_allowed('https://hospital.org/aid','https://other-hospital.org/pdf')

def test_document_discovery_rejects_cross_domain():
    html=b'<a href="/financial-assistance-application.pdf">Apply</a><a href="https://attacker.example/financial-assistance-application.pdf">Other</a>'
    links=discover_links(html,'https://hospital.org/aid')
    assert len(links)==1 and links[0][1]=='application'

def test_scanned_pdf_is_detected_without_ocr():
    import fitz
    d=fitz.open();d.new_page();payload=d.tobytes();d.close()
    text,method=parse_pdf(payload,allow_ocr=False)
    assert 'scanned-no-text' in method
