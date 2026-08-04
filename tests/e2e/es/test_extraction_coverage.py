"""E2E: languages/es/combined_es.txt offset coverage stays aligned with FR.

``languages/es/lang.yaml`` documents that ES is "an extraction at every offset
present in combined_fr.txt". In practice ES lags slightly behind FR (FR keeps
growing as new dialogue is fixed) — this guards that the gap stays small and
doesn't silently widen, which would mean the ES reference extraction was
never re-run after a batch of new FR offsets landed.

Baseline measured on this ROM/combined pair: 258 FR offsets missing from ES,
2 ES offsets not in FR. The ES reference intentionally lags behind newly
authored FR entries; the threshold leaves headroom while still catching a
real regression (e.g. combined_es.txt truncated or regenerated against a
stale ref).
"""

MAX_MISSING_FROM_ES = 300
MAX_EXTRA_IN_ES = 25
MIN_ES_ENTRIES = 20000
DEFAULT_PC_BOX_PREFIX_OFFSET = 0x4186CD


class TestExtractionCoverage:
    def test_es_has_a_meaningful_number_of_entries(self, es_combined_entries):
        assert len(es_combined_entries) >= MIN_ES_ENTRIES, (
            f"combined_es.txt only has {len(es_combined_entries)} entries — "
            f"expected at least {MIN_ES_ENTRIES}"
        )

    def test_es_covers_default_pc_box_prefix(self, es_combined_entries):
        assert es_combined_entries[DEFAULT_PC_BOX_PREFIX_OFFSET] == "Box"

    def test_es_coverage_close_to_fr_offsets(
        self, es_combined_entries, fr_combined_entries
    ):
        missing = set(fr_combined_entries) - set(es_combined_entries)
        assert len(missing) <= MAX_MISSING_FROM_ES, (
            f"{len(missing)} FR offsets are missing from combined_es.txt "
            f"(baseline ~109, threshold {MAX_MISSING_FROM_ES}) — "
            "re-run scripts/extract_combined_rom.py --lang ES to refresh the reference"
        )

    def test_es_has_few_offsets_absent_from_fr(
        self, es_combined_entries, fr_combined_entries
    ):
        extra = set(es_combined_entries) - set(fr_combined_entries)
        assert len(extra) <= MAX_EXTRA_IN_ES, (
            f"{len(extra)} combined_es.txt offsets are not present in "
            f"combined_fr.txt (baseline ~2, threshold {MAX_EXTRA_IN_ES})"
        )
