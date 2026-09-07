import copy
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'automation/scripts'))
import source_freshness as sf
from publication_evidence_adapters import first_party_evidence, github_release_api_url

FIX = json.loads((ROOT/'automation/fixtures/recall/publication-proof-2026-09-05.json').read_text())
HTML = (ROOT/'automation/fixtures/recall/yandex-date-proof-2026-09-04.html').read_text()
START = datetime.fromisoformat(FIX['window']['start_at'])
END = datetime.fromisoformat(FIX['window']['end_at'])


class PublicationAdapterTests(unittest.TestCase):
    def gate(self, index=0, body=HTML, final=None, release=None, end=END, candidate=None):
        candidate=copy.deepcopy(candidate or FIX['candidates'][index])
        url=candidate['primary_source']['url'];calls=[]
        def fetch(target):
            calls.append(target)
            if target==url:return body, final or url, 200
            if target==github_release_api_url(url):return json.dumps(release or FIX['release']),target,200
            raise AssertionError(target)
        report=sf.verify_candidate(candidate,start_at=START,end_at=end,fetcher=fetch)
        return candidate,report,calls

    def test_yandex_same_evidence_survives_real_gate(self):
        c,r,calls=self.gate()
        self.assertEqual(r['status'],'verified_fresh')
        self.assertEqual(c['recommendation'],'consider')
        self.assertEqual(len(calls),1)
        self.assertIn('yandex:url+visible-date',c['source_publication_evidence'])

    def test_generic_stale_metadata_wins_without_fallback(self):
        _,r,calls=self.gate(body='<meta property="article:published_time" content="2026-08-01T00:00:00Z">'+HTML)
        self.assertEqual(r['status'],'excluded_outside_window')
        self.assertEqual(len(calls),1)

    def test_yandex_requires_same_article_and_visible_date(self):
        url=FIX['yandex_url']
        for body,final in [('<h1>No date</h1>',url),('<h1>3 сентября 2026</h1>',url),
                           (HTML,'https://example.org/news'),(HTML,url+'&another=1')]:
            with self.subTest(final=final,body=body):
                self.assertIsNone(first_party_evidence(body,url,final,lambda _:self.fail('No fetch allowed')))

    def test_date_only_partial_cutoff_still_rejected(self):
        self.assertEqual(self.gate(end=datetime.fromisoformat('2026-09-04T03:57:22+03:00'))[1]['status'],'excluded_outside_window')

    def test_stale_event_prevents_source_fetch(self):
        c=copy.deepcopy(FIX['candidates'][0]);c.update(event_date='2026-08-25',event_at='2026-08-25T12:00:00Z',event_time_precision='datetime',event_origin_url=FIX['yandex_url'],event_evidence_kind='official_announcement',event_date_evidence='Original 2026-08-25')
        _,r,calls=self.gate(candidate=c)
        self.assertEqual(r['status'],'excluded_event_freshness_stale');self.assertEqual(calls,[])

    def test_github_exact_publication_api_identity(self):
        c,r,calls=self.gate(index=1,body='')
        self.assertEqual(r['status'],'verified_fresh');self.assertEqual(len(calls),2)
        self.assertIn('github-releases-api:published_at:',c['source_publication_evidence'])

    def test_github_rejects_drafts_wrong_identity_and_unknown_time(self):
        for patch in [{'draft':True},{'tag_name':'wrong'},{'html_url':'https://github.com/other/repo/releases/tag/x'},
                      {'published_at':None},{'published_at':'2026-09-04T12:00:00'}, {'published_at':'invalid'}]:
            with self.subTest(patch=patch):
                _,r,_=self.gate(index=1,body='',release={**FIX['release'],**patch})
                self.assertEqual(r['status'],'excluded_unverified_freshness')

    def test_github_exact_window_boundary_and_future(self):
        for timestamp,status in [(END.isoformat(),'verified_fresh'),('2026-09-05T01:00:00Z','excluded_outside_window')]:
            self.assertEqual(self.gate(index=1,body='',release={**FIX['release'],'published_at':timestamp})[1]['status'],status)

    def test_github_path_and_redirect_do_not_escape_identity(self):
        url=FIX['release']['html_url']
        for bad in [url.replace('github.com','github.com.evil.test'),url+'?x=1',url+'#x',url.replace('/releases/tag/','/tree/'),url.replace('https://','http://')]:
            self.assertIsNone(github_release_api_url(bad))
        endpoint=github_release_api_url(url)
        self.assertIsNone(first_party_evidence('',url,url,lambda _: (json.dumps(FIX['release']),endpoint+'/other',200)))

    def test_existing_exclusions_are_not_revived(self):
        c=copy.deepcopy(FIX['candidates'][0]);c['recommendation']='exclude'
        _,r,calls=self.gate(candidate=c)
        self.assertEqual(r['status'],'skipped');self.assertEqual(calls,[])

    def test_api_error_is_visible_and_fails_closed(self):
        c=copy.deepcopy(FIX['candidates'][1]);url=c['primary_source']['url']
        def fetch(target):
            if target==url:return '',url,200
            raise TimeoutError('offline timeout')
        r=sf.verify_candidate(c,start_at=START,end_at=END,fetcher=fetch)
        self.assertEqual(r['status'],'excluded_unverified_freshness')
        self.assertIn('TimeoutError',r['sources'][0]['error'])
