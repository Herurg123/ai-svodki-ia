from __future__ import annotations
import sys, unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"; sys.path.insert(0,str(SCRIPTS))
from ensure_story_coverage_policy import sanitize_diagnostic_url, sanitize_diagnostic_value
class Tests(unittest.TestCase):
 def test_aws(self):
  u="https://x.s3.amazonaws.com/a.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIAEXAMPLE%2Fscope&X-Amz-Date=20260814T010000Z&X-Amz-Security-Token=IQoJEXAMPLETEMPORARYTOKEN&X-Amz-Signature=deadbeef0123456789"
  r=sanitize_diagnostic_url(u); self.assertIn("X-Amz-Date=20260814T010000Z",r); self.assertNotIn("Credential",r); self.assertNotIn("Security-Token",r); self.assertNotIn("Signature",r); self.assertNotIn("ASIAEXAMPLE",r)
 def test_nested(self):
  d={"sources":[{"url":"https://x.test/a?token=abcdefghijklmnop&x=1"}]}; self.assertEqual(sanitize_diagnostic_value(d)["sources"][0]["url"],"https://x.test/a?x=1")
 def test_normal(self):
  u="https://www.reuters.com/world/a/?utm_source=search"; self.assertEqual(sanitize_diagnostic_url(u),u)
if __name__=="__main__": unittest.main()
