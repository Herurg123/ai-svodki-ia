from pathlib import Path

# Source-health must follow the new source-neutral routing: a verified fresh
# agency candidate in ANY completed Primary direction is evidence of healthy
# agency retrieval. Publisher-slot placement is no longer an invariant.
p = Path('automation/scripts/normalize_digest_artifact.py')
text = p.read_text(encoding='utf-8')
old_const = '''SOURCE_ANCHOR_DIRECTIONS = (
    "global_breaking",
    "major_agencies",
    "independent_missing_events",
)
'''
if old_const not in text:
    raise SystemExit('old SOURCE_ANCHOR_DIRECTIONS constant not found')
text = text.replace(old_const, '', 1)
old_block = '''    # Starting with the 2026-08-13 incident, merely consulting a Bloomberg author
    # page or an old newsletter is no longer sufficient evidence that the broad
    # news layer is healthy. When modern diagnostics contain an effective window,
    # require at least one source-anchor pass to show an in-window agency article.
    # Reuters/Bloomberg/FT usually expose YYYY-MM-DD in the URL; AP can satisfy
    # the same check through a verified raw candidate whose published_date is in
    # the window. Legacy Primary artifacts without search_window keep their older
    # compatibility behavior.
    window_days = _primary_window_dates(primary)
    if window_days is not None:
        start_day, end_day = window_days
        anchor_directions = [
            item
            for item in directions
            if isinstance(item, dict)
            and item.get("direction_id") in SOURCE_ANCHOR_DIRECTIONS
        ]
        if not any(
            _direction_has_fresh_agency_evidence(
                item, start_day=start_day, end_day=end_day
            )
            for item in anchor_directions
        ):
            raise NormalizationError(
                "Primary Recall source-health degraded: broad source-anchor passes "
                "не подтвердили ни одного свежего Reuters/AP/Bloomberg/FT материала "
                "в effective window; служебные, author и старые newsletter URL не "
                "считаются доказательством свежего agency retrieval."
            )
'''
new_block = '''    # Merely consulting a Bloomberg author page or an old newsletter is not
    # sufficient evidence that current-news retrieval is healthy. With the
    # source-neutral routing introduced after the 2026-08-14 live experiment,
    # publisher placement is no longer an invariant: a fresh Reuters/AP/
    # Bloomberg/FT candidate may legitimately be discovered by security,
    # business, regional, developer or another thematic Primary direction.
    # Therefore modern diagnostics require fresh agency evidence anywhere in the
    # completed 12-pass Primary matrix, not specifically in former anchor slots.
    # Legacy Primary artifacts without search_window keep compatibility behavior.
    window_days = _primary_window_dates(primary)
    if window_days is not None:
        start_day, end_day = window_days
        if not any(
            _direction_has_fresh_agency_evidence(
                item, start_day=start_day, end_day=end_day
            )
            for item in directions
            if isinstance(item, dict)
        ):
            raise NormalizationError(
                "Primary Recall source-health degraded: ни одно из 12 Primary-направлений "
                "не подтвердило свежий Reuters/AP/Bloomberg/FT материал в effective "
                "window; служебные, author и старые newsletter URL не считаются "
                "доказательством свежего agency retrieval."
            )
'''
if old_block not in text:
    raise SystemExit('old source-health anchor block not found')
text = text.replace(old_block, new_block, 1)
p.write_text(text, encoding='utf-8')

# Regression test: stale agency route still fails, but a verified FT candidate
# in a thematic pass proves Primary source health.
p = Path('automation/tests/test_digest_artifact_primary_normalization.py')
text = p.read_text(encoding='utf-8')
text = text.replace('self.assertIn("свежего Reuters/AP/Bloomberg/FT", str(ctx.exception))', 'self.assertIn("Reuters/AP/Bloomberg/FT", str(ctx.exception))', 1)
marker = '''    def test_current_dated_reuters_article_is_fresh_source_health_evidence(self):
'''
insert = '''    def test_fresh_agency_candidate_in_thematic_direction_is_source_health_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.bloomberg.com/authors/EXAMPLE/example-author",
                ],
                other_sources=["https://openai.com/index/example"],
                with_search_window=True,
            )
            primary_path = artifact / "primary-recall.json"
            primary = json.loads(primary_path.read_text(encoding="utf-8"))
            primary["directions"].append(
                {
                    "direction_id": "security_safety",
                    "web_search_calls_completed": 1,
                    "raw_candidates": [
                        {
                            "published_date": "2026-08-12",
                            "primary_source": {
                                "url": "https://www.ft.com/content/fresh-security-story"
                            },
                        }
                    ],
                    "api": {"consulted_sources": []},
                }
            )
            write_json(primary_path, primary)
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )

'''
if marker not in text:
    raise SystemExit('normalizer test insertion marker not found')
text = text.replace(marker, insert + marker, 1)
p.write_text(text, encoding='utf-8')

# Documentation: fresh-agency health is matrix-wide, not tied to former anchors.
for path in ['AGENTS.md', 'README.md', 'automation/README.md']:
    p = Path(path)
    value = p.read_text(encoding='utf-8')
    note = '''\nSource-health после перехода на source-neutral routing проверяет свежую Reuters/AP/Bloomberg/FT evidence по **всей 12-pass Primary matrix**, а не только в `global_breaking`/`major_agencies`/`independent_missing_events`: тематический pass вправе первым обнаружить сильный agency-материал. При этом `major_agencies` всё равно обязан завершить свою search operation и иметь хотя бы один consulted source, а общий anti-junk gate по источникам не ослабляется.\n'''
    if note.strip() not in value:
        value += '\n' + note
    p.write_text(value, encoding='utf-8')

Path('.github/_tmp_fix_source_health_scope.py').unlink()
