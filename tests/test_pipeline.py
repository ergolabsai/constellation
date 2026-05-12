from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from constellation.pipeline import run_pipeline
from constellation.util import read_json


ROOT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def test_shumlak_smoke_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            summary = run_pipeline(ROOT / "corpora" / "shumlak", out)
            self.assertEqual(summary["papers"], 3)
            self.assertGreaterEqual(summary["claims"], 7)
            self.assertGreater(summary["edges"], 0)
            self.assertLess(summary["final_residual"], summary["initial_residual"])
            self.assertTrue((out / "report.md").exists())

    def test_claim_rewrite_preserves_in_regime_strength(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_pipeline(ROOT / "corpora" / "shumlak", out)
            claim = read_json(out / "claims" / "S_02.json")
            self.assertEqual(claim["x_final"][0], 1.0)
            self.assertLess(claim["x_final"][1], 1.0)
            self.assertTrue(claim["rewrite_history"])

    def test_evidence_core_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_pipeline(ROOT / "corpora" / "shumlak", out)
            evidence = read_json(out / "evidence" / "ev_angus_m1_not_stabilized.json")
            self.assertTrue(evidence["core"]["locked"])
            self.assertEqual(evidence["core"]["dimensions"][0]["value"], 0.0)


if __name__ == "__main__":
    unittest.main()

