from pathlib import Path

# Keep the phrase intact so docs/tests and model instruction are unambiguous.
p = Path('automation/prompts/primary_recall_pass.md')
text = p.read_text(encoding='utf-8')
old = 'материалы через relative-\nfreshness cue:'
if old not in text:
    raise SystemExit('primary relative-freshness wrapped phrase not found')
p.write_text(text.replace(old, 'материалы через relative-freshness cue:', 1), encoding='utf-8')

# Hybrid prompt test: assert the new date-free contract instead of the old exact sentence.
p = Path('automation/tests/test_hybrid_search_completeness.py')
text = p.read_text(encoding='utf-8')
old = '        self.assertIn("Не используй after:, before:, site:", prompt)\n        self.assertNotIn("предпочтительная retrieval-подсказка: after:", prompt)\n'
new = '        self.assertIn("date-free natural-language", prompt)\n        self.assertIn("latest / recent / current / breaking", prompt)\n        self.assertIn("Не добавляй в query календарные даты", prompt)\n        self.assertNotIn("предпочтительная retrieval-подсказка: after:", prompt)\n'
if old not in text:
    raise SystemExit('hybrid old query assertion block not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Primary matrix tests: broad safety nets are intentionally source-neutral now.
p = Path('automation/tests/test_primary_recall_search.py')
text = p.read_text(encoding='utf-8')
old = '''    def test_high_signal_passes_have_disjoint_api_domain_filters(self):
        directions = {item["id"]: item for item in prs.PRIMARY_DIRECTIONS}
        self.assertEqual(
            tuple(directions["global_breaking"]["allowed_domains"]),
            prs.REUTERS_DOMAINS,
        )
        self.assertEqual(
            tuple(directions["major_agencies"]["allowed_domains"]),
            prs.BLOOMBERG_FT_DOMAINS,
        )
        self.assertEqual(
            tuple(directions["independent_missing_events"]["allowed_domains"]),
            prs.AP_DOMAINS,
        )
        self.assertEqual(
            set(prs.AGENCY_DOMAINS),
            set(prs.REUTERS_DOMAINS + prs.BLOOMBERG_FT_DOMAINS + prs.AP_DOMAINS),
        )
'''
new = '''    def test_broad_safety_nets_are_source_neutral_and_agency_route_is_additive(self):
        directions = {item["id"]: item for item in prs.PRIMARY_DIRECTIONS}
        self.assertEqual(tuple(directions["global_breaking"].get("allowed_domains") or ()), ())
        self.assertEqual(
            tuple(directions["major_agencies"].get("allowed_domains") or ()),
            prs.BLOOMBERG_FT_DOMAINS,
        )
        self.assertEqual(tuple(directions["independent_missing_events"].get("allowed_domains") or ()), ())
        self.assertEqual(
            set(prs.AGENCY_DOMAINS),
            set(prs.REUTERS_DOMAINS + prs.BLOOMBERG_FT_DOMAINS + prs.AP_DOMAINS),
        )
'''
if old not in text:
    raise SystemExit('primary old domain-route test not found')
text = text.replace(old, new, 1)
text = text.replace('        self.assertEqual(seen_domains["global_breaking"], prs.REUTERS_DOMAINS)\n', '        self.assertEqual(seen_domains["global_breaking"], ())\n', 1)
text = text.replace('        self.assertEqual(seen_domains["independent_missing_events"], prs.AP_DOMAINS)\n', '        self.assertEqual(seen_domains["independent_missing_events"], ())\n', 1)
p.write_text(text, encoding='utf-8')

# Sentinel test: assertions inside the mocked transport are swallowed by the
# production fail-closed path. Assert transport arguments after the call instead.
p = Path('automation/tests/test_recall_sentinel.py')
text = p.read_text(encoding='utf-8')
start = text.index('    def test_seventh_slot_is_one_source_agnostic_search(self) -> None:\n')
end = text.index('\n    def test_sentinel_is_not_used_when_pool_is_nonzero', start)
replacement = '''    def test_seventh_slot_is_one_source_agnostic_search(self) -> None:
        def fake_request(**kwargs):
            story = candidate(legal_scale="major")
            story["source_type"] = "technology_media"
            story["primary_source"] = {
                "title": "Exclusive: OpenAI slows release of Astra model citing cyber capabilities",
                "publisher": "Axios",
                "url": "https://www.axios.com/2026/08/07/openai-astra-model-delay-cybersecurity-risks",
            }
            story["verification_notes"] = "Axios report within the editorial window."
            return (
                {
                    "status": "complete",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [story],
                    "rejections": [],
                    "notes": "High-signal source-neutral story found.",
                },
                api_metadata("latest major artificial intelligence news"),
            )

        result, request = self.run_plan(complete_zero_plan(), fake_request)

        self.assertEqual(request.call_count, 1)
        call = request.call_args.kwargs
        self.assertEqual(call["maximum_web_search_calls"], 1)
        self.assertEqual(tuple(call["allowed_domains"]), ())
        self.assertIn("РОВНО ОДИН Web Search", call["prompt"])
        self.assertIn("latest major artificial intelligence news", call["prompt"])
        self.assertNotIn("Reuters latest major artificial intelligence news", call["prompt"])
        self.assertIn("Не расширяй и не переписывай", call["prompt"])
        self.assertIn("source-neutral recall sentinel", call["prompt"])
        self.assertIn("не должен быть привязан ни к OpenAI", call["prompt"])
        self.assertEqual(len(result["attempts"]), 7)
        sentinel = result["attempts"][-1]
        self.assertEqual(sentinel["search_strategy"], runtime.RECALL_SENTINEL_STRATEGY)
        self.assertEqual(
            sentinel["recall_sentinel_version"], runtime.RECALL_SENTINEL_VERSION
        )
        self.assertEqual(sentinel["allowed_domains"], [])
        self.assertEqual(sentinel["candidate_count"], 1)
        found = result["candidates"][0]
        self.assertEqual(found["audit_direction"], "recall_sentinel")
        self.assertEqual(found["category"], "security")
        self.assertEqual(found["primary_source"]["publisher"], "Axios")
        self.assertEqual(found["legal_scale"], "not_applicable")
        self.assertEqual(found["legal_scale_reason"], "")
        self.assertEqual(result["search_budget"]["completed_calls"], 7)
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)
'''
text = text[:start] + replacement + text[end:]
p.write_text(text, encoding='utf-8')

Path('.github/_tmp_fix_relative_tests.py').unlink()
