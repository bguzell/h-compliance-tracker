"""Conservative PSA county mention extraction. Mention != legally validated service area."""
import re
COUNTIES = '''Albany Allegany Bronx Broome Cattaraugus Cayuga Chautauqua Chemung Chenango Clinton Columbia Cortland Delaware Dutchess Erie Essex Franklin Fulton Genesee Greene Hamilton Herkimer Jefferson Kings Lewis Livingston Madison Monroe Montgomery Nassau New York Niagara Oneida Onondaga Ontario Orange Orleans Oswego Otsego Putnam Queens Rensselaer Richmond Rockland St. Lawrence Saratoga Schenectady Schoharie Schuyler Seneca Steuben Suffolk Sullivan Tioga Tompkins Ulster Warren Washington Wayne Westchester Wyoming Yates'''
# Keep multiword counties intact; prevent false guesses from 'New York State' alone.
_COUNTY_NAMES=['St. Lawrence','New York'] + [x for x in COUNTIES.replace('St. Lawrence','').replace('New York','').split() if x]
assert len(_COUNTY_NAMES)==62

def psa_county_mentions(text):
    if not text: return []
    segments=[]
    for m in re.finditer(r'primary service area|\bPSA\b',text,re.I):
        segments.append(text[m.end():m.end()+500])
    seen=[]
    for chunk in segments:
        for name in _COUNTY_NAMES:
            # County or Counties notation plus explicit name; exclude unrelated state references.
            pattern=r'(?<!\w)'+re.escape(name)+r'\s+(?:County|Counties)\b'
            if re.search(pattern,chunk,re.I) and name not in seen:seen.append(name)
    return sorted(seen)
