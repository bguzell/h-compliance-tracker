"""Config and documented grading switches. Never check in live secrets."""
from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
def flag(key, default=True): return os.getenv(key, str(default)).lower() in ('1','true','yes','on')
load_dotenv(ROOT / '.env')

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('HFA_DATABASE_URL', 'sqlite:///' + str(ROOT / 'data/current/hfa_tracker.db'))
    user_agent: str = os.getenv('HFA_USER_AGENT', 'Hospital-FA-Research-Prototyper/0.1 (contact: team-contact@example.org)')
    timeout: float = float(os.getenv('HFA_REQUEST_TIMEOUT', '15'))
    max_documents: int = int(os.getenv('HFA_MAX_DOCUMENTS', '16'))
    fpl_year: int = int(os.getenv('HFA_CURRENT_FPL_YEAR', '2026'))
    admin_password: str = os.getenv('HFA_ADMIN_PASSWORD', '')
    auto_fail_missing_application: bool = flag('HFA_AUTO_FAIL_MISSING_APPLICATION')
    auto_fail_missing_uniform_application: bool = flag('HFA_AUTO_FAIL_MISSING_UNIFORM_APPLICATION')
    # CSSNY methodology p1; historical tracker did not apply it consistently
    auto_fail_missing_policy_statement: bool = flag('HFA_AUTO_FAIL_MISSING_POLICY_STATEMENT')

S = Settings()
SOURCE_HFA_LAW = 'https://www.nysenate.gov/legislation/laws/PBH/2807-K'
SOURCE_DOH = 'https://www.health.ny.gov/facilities/hospital/financial_assist/'
SOURCE_DOH_HOSP = SOURCE_DOH + 'hosp_info/'
SOURCE_DOHSOCRATA = 'https://health.data.ny.gov/resource/vn5v-hh5r.json'
