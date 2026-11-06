"""DB session factory; SQLite for prototype, PostgreSQL via DATABASE_URL later."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base
from .config import S

_engine = None

def engine(url=None):
    global _engine
    if url: return create_engine(url, future=True)
    if _engine is None:
        _engine = create_engine(S.database_url, future=True, connect_args={'check_same_thread':False} if S.database_url.startswith('sqlite') else {})
        if S.database_url.startswith('sqlite'):
            @event.listens_for(_engine,'connect')
            def sqlite_pragmas(connection, record):
                cur=connection.cursor(); cur.execute('PRAGMA foreign_keys=ON'); cur.execute('PRAGMA busy_timeout=5000'); cur.close()
    return _engine

def init_db(e=None): Base.metadata.create_all(e or engine())
def session_factory(e=None): return sessionmaker(bind=e or engine(), expire_on_commit=False, future=True)
