"""The 17 CSSNY binary audit fields, separated by their originating documents."""
from dataclasses import dataclass
from .config import SOURCE_HFA_LAW, SOURCE_DOH

@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    scope: str
    source_column: str
    requirement: str
    why: str
    law: str = SOURCE_HFA_LAW

CRITERIA = [
 Criterion('application_posted','Application posted','website','Application Posted','A financial assistance application must be available to patients.','Without a form, patients may not know how to request help.'),
 Criterion('summary_posted','Policy summary posted','website','Policy Summary Posted (as PDF, or on landing page)','A plain-language summary of assistance must be available.','A short explanation helps patients find support quickly.'),
 Criterion('policy_posted','Policy statement posted','website','Policy Statement Posted','The financial assistance policy must be publicly accessible.','Patients and advocates need to see the hospital’s rules.'),
 Criterion('consistent','Information consistent across posted documents','cross_document','Consistent across posted documents (Y/N)','The hospital’s posted materials should provide consistent information.','Different thresholds or deadlines can confuse patients.'),
 Criterion('psa_boundaries','Primary service area boundaries','website','Primary Service Area boundaries compliant with 2007 guidelines?','Service area boundaries must meet applicable state guidance.','Inappropriate boundaries can exclude underserved communities.'),
 Criterion('no_deadline','No prohibited submission deadline','website','No time limit to submit?','Patients may apply at any point during collections.','A short deadline can prevent patients from receiving aid.'),
 Criterion('no_asset_checks','No prohibited asset checks','website','No evidence of asset checks','Avoid prohibited asset screening as defined by CSSNY’s audit.','Demanding unnecessary financial records can deter applications.'),
 Criterion('no_immigration_barrier','No immigration-status exclusion','website','No mention of immigration status as a barrier','Immigration status must not determine eligibility.','Immigration barriers could wrongly exclude vulnerable patients.'),
 Criterion('uniform_application','Complete NYS Uniform Application','application','ENTIRE Uniform Application','Use the complete current NYS Uniform Financial Assistance Application.','Incomplete forms can hide important patient rights.',SOURCE_DOH),
 Criterion('application_contact','Application contact information','application','Contact information included in application','The application should clearly provide contact information.','Patients need to know whom to ask for help.'),
 Criterion('application_tables','Application income and discount tables','application','Income & Discount Tables Incuded in Application','The application should include income and discount information.','Patients need to understand the help they might qualify for.'),
 Criterion('application_fpl_year','Current FPL year in application','application','2025 FPL Guidelines','The application should reflect the currently applicable state FPL guidance.','Outdated tables may cause patients to misjudge eligibility.',SOURCE_DOH),
 Criterion('application_max_fpl','At least 400% FPL eligibility','application','Max FPL (compliant is =/>400%)','Assistance must cover eligible patients through at least 400% FPL.','A lower cutoff could wrongly turn away people needing help.'),
 Criterion('application_installments','Installments capped at 5%','application','Installments capped at 5% of monthly income','The application must explicitly state the 5% gross monthly income payment cap, per CSSNY audit.','Unaffordable payment plans can push people into debt.'),
 Criterion('summary_psa','Service area described in summary','summary','Primary Service Area described in summary? ','The plain-language summary must describe the primary service area.','Patients should know whether they live in the area covered.'),
 Criterion('summary_application','How to apply described in summary','summary','Means of applying for assistance explained','The summary must explain how to apply for assistance.','Help is less accessible if patients cannot find the next step.'),
 Criterion('summary_income','Income thresholds described in summary','summary','Income levels used to determine assistance','The summary must explain what income levels determine help.','Patients should be able to understand eligibility without legal training.'),
]
BY_ID = {r.id:r for r in CRITERIA}
assert len(CRITERIA)==17
