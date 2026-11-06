"""Standalone worker. Keep this OUTSIDE Streamlit's request/render loop."""
from apscheduler.schedulers.blocking import BlockingScheduler
from .updater import refresh_many,light_check_many
from .geocoder import sync_roster
from .database import init_db
import logging

logging.basicConfig(level=logging.INFO)

def run():
    init_db()
    scheduler=BlockingScheduler(timezone='America/New_York')
    scheduler.add_job(refresh_many,'cron',day_of_week='sun',hour=3,id='weekly_full',max_instances=1,coalesce=True)
    scheduler.add_job(light_check_many,'cron',day_of_week='mon-sat',hour=3,kwargs={'days':1},id='daily_checks',max_instances=1,coalesce=True)
    scheduler.add_job(sync_roster,'cron',day='1',hour=5,id='monthly_roster',max_instances=1)
    scheduler.start()

if __name__=='__main__': run()
