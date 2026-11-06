"""PDF/DOCX/HTML text extraction; OCR is last resort, never silently invented."""
import io,re,subprocess,shutil, tempfile
from pathlib import Path
from bs4 import BeautifulSoup

def clean(text): return re.sub(r'\s+',' ',text or '').strip()

def parse_pdf(content:bytes, allow_ocr:bool=False):
    import fitz
    pages=[]; methods=[]
    with fitz.open(stream=content,filetype='pdf') as doc:
        for i,page in enumerate(doc):
            body=clean(page.get_text(sort=True))
            if len(body)<75 and allow_ocr and shutil.which('tesseract'):
                # OCR on only those pages that failed native extraction, at lower DPI.
                try:
                    import pytesseract
                    from PIL import Image
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                    body=clean(pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes('png')))))
                    methods.append('ocr')
                except Exception:
                    methods.append('failed-ocr')
            else: methods.append('pdf-text' if body else 'scanned-no-text')
            pages.append(f'[Page {i+1}] {body}')
    return '\n'.join(pages), ','.join(sorted(set(methods)))

def parse_docx(content:bytes):
    from docx import Document
    d=Document(io.BytesIO(content))
    parts=[p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows: parts.append(' | '.join(c.text for c in row.cells))
    return clean('\n'.join(parts)),'docx-text'

def parse_html(content:bytes):
    soup=BeautifulSoup(content,'html.parser')
    for elem in soup(['script','style','noscript','svg','footer','nav','header']): elem.decompose()
    return clean(soup.get_text(separator=' ',strip=True)),'html-text'

def extract(content:bytes, media_type:str, url:str='', allow_ocr:bool=False):
    content_type=(media_type or '').lower(); url=url.lower().split('?')[0]
    if 'pdf' in content_type or url.endswith('.pdf'): return parse_pdf(content,allow_ocr)
    if 'wordprocessingml' in content_type or url.endswith('.docx'): return parse_docx(content)
    if 'html' in content_type or content.lstrip().startswith(b'<!') or b'<html' in content[:500].lower(): return parse_html(content)
    return '', 'unsupported'
