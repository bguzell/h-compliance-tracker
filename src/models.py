"""Current-only operational state; historical 2025 scores are clearly separate."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()
def utcnow(): return datetime.now(timezone.utc)

class Hospital(Base):
    __tablename__ = 'hospitals'
    hospital_id = Column(String, primary_key=True)
    pfi = Column(String)
    ocn = Column(String)
    ocn_pfi = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=False, index=True)
    system = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zipcode = Column(String)
    county = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    location_provenance = Column(String)
    hfa_url = Column(Text)
    hfa_url_provenance = Column(String, default="ORIGINAL_2025_CSSNY")
    id_needs_reconciliation = Column(Boolean, default=False)
    roster_status = Column(String, default='Not reconciled')
    # frozen original observations, not evidence of today's compliance
    historical_grade = Column(String)
    historical_error_count = Column(Integer)
    historical_auto_fail = Column(Boolean)
    historical_languages = Column(String)
    # today's results, empty until a successful public-source check
    grade = Column(String, nullable=True)
    provisional = Column(Boolean, default=True)
    noncompliant_count = Column(Integer, default=0)
    review_count = Column(Integer, default=17)
    last_checked = Column(DateTime(timezone=True))
    source_last_changed = Column(DateTime(timezone=True))
    current_page_hash = Column(String)
    source_status = Column(String, default='NOT_CHECKED')
    last_error = Column(Text)
    documents = relationship('SourceDocument', cascade='all, delete-orphan', back_populates='hospital')
    results = relationship('CriterionResult', cascade='all, delete-orphan', back_populates='hospital')

class SourceDocument(Base):
    __tablename__ = 'source_documents'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(String, ForeignKey('hospitals.hospital_id'), index=True)
    url = Column(Text, nullable=False)
    doc_type = Column(String, nullable=False)
    title = Column(String)
    language = Column(String)
    content_hash = Column(String)
    extracted_text = Column(Text)
    etag = Column(String)
    last_modified = Column(String)
    retrieved_at = Column(DateTime(timezone=True))
    extraction_method = Column(String)
    hospital = relationship('Hospital', back_populates='documents')

class CriterionResult(Base):
    __tablename__ = 'criterion_results'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(String, ForeignKey('hospitals.hospital_id'), index=True)
    criterion_id = Column(String, nullable=False)
    status = Column(String, default='REVIEW')
    evidence = Column(Text)
    source_url = Column(Text)
    source_document_type = Column(String)
    source_document_title = Column(String)
    source_page = Column(String)
    confidence = Column(Float)
    extraction_method = Column(String)
    explanation = Column(Text)
    review_reason = Column(Text)
    retrieved_at = Column(DateTime(timezone=True))
    source_hash = Column(String)
    hospital = relationship('Hospital', back_populates='results')
    __table_args__ = (UniqueConstraint('hospital_id','criterion_id',name='uq_hospital_criterion'),)

class ChangeEvent(Base):
    __tablename__ = 'change_events'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(String, ForeignKey('hospitals.hospital_id'), index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    criteria_changed = Column(Text)
    old_grade = Column(String)
    new_grade = Column(String)
    source_url = Column(Text)
    reason = Column(String)

class ReviewDecision(Base):
    __tablename__ = 'review_decisions'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(String, ForeignKey('hospitals.hospital_id'), index=True)
    criterion_id = Column(String, nullable=False)
    source_hash = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    reviewer_note = Column(Text)
    reviewer = Column(String)
    decided_at = Column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('hospital_id','criterion_id','source_hash',name='uq_review_source'),)

class RunLog(Base):
    __tablename__ = 'run_logs'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(String, index=True)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    outcome = Column(String)
    message = Column(Text)
