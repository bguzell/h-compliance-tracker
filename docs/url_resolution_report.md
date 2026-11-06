# HFA hyperlink source-resolution audit — 6 November 2026

The user-provided historical hyperlink export contains **38 textual page titles, not usable web URLs**. An automated retrieval attempt against any such original cell would fail; it is not evidence that a hospital has failed to post financial assistance materials.

- All **212** historical facility records and grades remain unchanged in the original CSV files.
- All **38** deficient cells have a replacement *candidate* official-hospital or health-system URL in `data/seed/hfa_url_overrides.csv`. Every row preserves the original title, candidate URL, provenance type, and source used to identify the URL.
- Candidate evidence includes an official Nuvance policy summary explicitly naming the three Nuvance facilities, Rochester Regional Health's official financial-assistance policy list, independently published official hospital pages, and other official HFA URLs present in the CSSNY export.
- Some system-wide URL entries carry `SAME_SYSTEM_CANDIDATE` or `SYSTEM_POLICY_NAMES_PARENT`. **They are not verified to cover the named facility** and cannot receive compliance scores until a human confirms that applicability in currently retrieved documents.
- Other URL recovery types identify specific official pages or hospital documents but must still be visited by the actual updater. A source URL is never equivalent to proof of legal compliance.
- The build environment cannot make a 212-site live request; `verified_live_retrieval` remains `NO` for all 38 proposed URLs. These are *source-discovery candidates*, not live-verified statuses.

## Manual resolution workflow

1. Run `python -m src.cli refresh` in a network-enabled environment.
2. Inspect the hospital detail page and official source documents; do not assume one system-wide policy covers its affiliates.
3. For entries requiring facility-coverage review, obtain evidence from the actually retrieved source. Use the administrative `verify-source` command with an explanatory note.
4. Refresh the facility to recompute the 17 criteria on its verified sources. Audit each shared-system hospital separately.
5. Revisit unresolved names/locations and the one missing PFI/OCN record during NYSDOH roster reconciliation.

## Reproducibility

`tests/test_seed_links.py` checks that the 38 originally unusable values are exactly matched by the override table and that the seeded database has 212 distinct facilities. `tests/test_updater.py` verifies that shared-system candidates cannot inherit a grade or receive manual compliance decisions before explicit source verification.
