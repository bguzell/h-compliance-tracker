"""Usage: python -m src.cli seed | validate | roster | refresh [--limit N] | audit [--days N] | verify-source --hospital-id ID --evidence-url URL --note TEXT"""
import argparse,json,collections
from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from .seed import seed_database,read_baseline,hospital_id
from .grader import grade_from_error_count
from .database import session_factory,init_db
from .models import Hospital
from .geocoder import sync_roster
from .updater import refresh_many,light_check_many,verify_facility_source
from .standards import check_current_fpl

def validate_baseline():
    rows=read_baseline();mismatch=[];method_diff=[]; counts=collections.Counter()
    for row in rows:
        grade=grade_from_error_count(int(row['Noncompliant Categories Count']),row['Automatic Fail?'].upper()=='TRUE')
        expected=row['COMPLIANCE GRADE'].strip();counts[expected]+=1
        if grade!=expected: mismatch.append({'id':hospital_id(row),'expected':expected,'actual':grade})
        # CSSNY PDF says missing policy statement is automatic F; compare to historical tracker.
        method_auto=row['Automatic Fail?'].upper()=='TRUE' or row['Policy Statement Posted'].strip().lower()=='no'
        new_grade=grade_from_error_count(int(row['Noncompliant Categories Count']),method_auto)
        if new_grade!=expected: method_diff.append({'id':hospital_id(row),'name':row['Hospital Name'],'original':expected,'pdf_rule':new_grade})
    return {'facilities':len(rows),'baseline_grades':dict(counts),'historical_grade_mismatches':mismatch,'pdf_automatic_fail_discrepancies':method_diff,'discrepancy_count':len(method_diff)}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['seed','validate','roster','refresh','audit','fpl-standard','daily','verify-source'])
    p.add_argument('--limit',type=int);p.add_argument('--days',type=int,default=1)
    args=p.parse_args()
    if args.command=='verify-source':
        if not all([args.hospital_id,args.evidence_url,args.note]):p.error('verify-source requires --hospital-id --evidence-url --note')
        print('Facility source verified:',verify_facility_source(args.hospital_id,args.evidence_url,args.note))
    elif args.command=='seed': print(f'Imported {seed_database()} historical facilities (not current compliance grades)')
    elif args.command=='validate': print(json.dumps(validate_baseline(),indent=2))
    elif args.command=='roster':
        init_db();print(json.dumps(sync_roster(),indent=2))
    elif args.command=='fpl-standard': print(json.dumps(check_current_fpl(),indent=2))
    elif args.command=='daily':
        init_db();print(json.dumps(light_check_many(limit=args.limit,days=args.days),indent=2))
    elif args.command in ('refresh','audit'):
        init_db();res=refresh_many(limit=args.limit,only_stale_days=args.days if args.command=='audit' else None)
        print(json.dumps({'total':len(res),'outcomes':dict(collections.Counter(x.get('source_status') for x in res)),'results':res},indent=2))

if __name__=='__main__': main()
