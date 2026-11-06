"""Optional strictly evidence-validated semantic extraction (never assigns final grades)."""
import json,os
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

class AIFact(BaseModel):
    field: str
    value: str|None
    evidence: str
    source_page: str|None=None
    confidence: float=Field(ge=0,le=1)
    document_type: str

class AIResponse(BaseModel):
    facts: list[AIFact]

SYSTEM='You extract factual claims ONLY from the provided hospital document. If evidence is not explicit return UNKNOWN. Copy exact evidence verbatim. Never assign compliance grades. Return strict JSON object {"facts": [...]}.'

def verify_response(payload,source_text,source_type):
    if isinstance(payload,str): payload=json.loads(payload)
    parsed=AIResponse.model_validate(payload)
    valid=[]
    for f in parsed.facts:
        if f.document_type!=source_type: continue
        if f.value is None or f.value.upper()=='UNKNOWN': continue
        if not f.evidence or f.evidence not in source_text: continue
        valid.append(f)
    return valid

def extract_semantic(text,doc_type):
    provider=os.getenv('HFA_AI_PROVIDER','none').lower()
    if provider=='none': return []
    if provider=='openai_compatible':
        import httpx
        endpoint=os.environ['HFA_LLM_URL']
        key=os.environ['HFA_LLM_API_KEY']
        model=os.environ['HFA_LLM_MODEL']
        response=httpx.post(endpoint,headers={'Authorization':f'Bearer {key}'},json={'model':model,'temperature':0,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':f'Document type: {doc_type}\nDocument text:\n{text[:65000]}'}]},timeout=55)
        response.raise_for_status()
        return verify_response(response.json()['choices'][0]['message']['content'],text,doc_type)
    if provider=='bedrock':
        import boto3
        client=boto3.client('bedrock-runtime',region_name=os.getenv('AWS_REGION','us-east-1'))
        res=client.converse(modelId=os.environ['HFA_BEDROCK_MODEL'],messages=[{'role':'user','content':[{'text':SYSTEM+'\nType:'+doc_type+'\n'+text[:55000]}]}],inferenceConfig={'temperature':0,'maxTokens':1800})
        raw=''.join(i['text'] for i in res['output']['message']['content'] if 'text' in i)
        return verify_response(raw,text,doc_type)
    raise ValueError('Unsupported AI provider')
