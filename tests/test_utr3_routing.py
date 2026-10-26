"""3-prime deployment routing and bundle checks, without GPU allocation."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "workspace/codon"))
import backend_server as backend
import tissue_utr3 as routing


class ThreePrimeRoutingTests(unittest.TestCase):
    def test_all_bundles_match_tissues_and_frozen_choices(self):
        manifest = json.loads((routing.MODEL_ROOT / "model_manifest.json").read_text())
        self.assertEqual(set(manifest["tissues"]), set(backend.TISSUES)-{"general"})
        self.assertEqual(sum(r["used_finetuned_model"] for r in manifest["tissues"].values()), 21)
        original_hash = manifest["general"]["weights_sha256"]
        inodes = set()
        for tissue in backend.TISSUES:
            directory = routing.resolve_tissue_model(tissue)
            weight = directory / "model.safetensors"
            self.assertFalse(weight.is_symlink())
            self.assertEqual(weight.stat().st_nlink, 1)
            inodes.add((weight.stat().st_dev, weight.stat().st_ino))
            meta = json.loads((directory / "selection_metadata.json").read_text())
            expected = manifest["general"] if tissue == "general" else manifest["tissues"][tissue]
            self.assertEqual(meta, expected)
            self.assertEqual(meta["tissue"], tissue)
            self.assertEqual(json.loads((directory / "generation_config.json").read_text()),
                             {"num_beams": 8, "length_penalty": 2.0, "min_length": 0, "max_length": 128})
            self.assertEqual(meta["weights_sha256"] == original_hash, not meta["used_finetuned_model"])
        self.assertEqual(len(inodes), 30)
        self.assertEqual(routing.resolve_tissue_model("0"), routing.resolve_tissue_model("general"))
        for tissue in ("../Brain", "..", "/tmp/Brain", "Unknown"):
            with self.assertRaises((ValueError, FileNotFoundError)):
                routing.resolve_tissue_model(tissue)

    def test_gpu_uuid_and_explicit_cpu_are_preserved(self):
        response = SimpleNamespace(returncode=0, stdout=json.dumps({"predictions": ["ACGT"]}), stderr="")
        for use_gpu in (True, False):
            with mock.patch.dict("os.environ", {"CUDA_VISIBLE_DEVICES": "GPU-selected-by-backend"}), mock.patch.object(routing.subprocess, "run", return_value=response) as run:
                self.assertEqual(routing.generate_tissue_utr3(["ATGTGA"], "Brain", use_gpu=use_gpu), ["ACGT"])
                self.assertEqual(run.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], "GPU-selected-by-backend" if use_gpu else "")
                self.assertIn(str(routing.MODEL_ROOT / "Brain"), run.call_args.args[0])
                self.assertEqual(json.loads(run.call_args.kwargs["input"])["sequences"], ["ATGTGA"])

    def test_separate_python_override_and_invalid_output(self):
        with mock.patch.dict("os.environ", {"MRNAVIEWER_UTR3_PYTHON": "/specific/dna/python"}):
            self.assertEqual(routing.inference_python(), "/specific/dna/python")
        for predictions in ([], [""], ["ACGU"]):
            response = SimpleNamespace(returncode=0, stdout=json.dumps({"predictions": predictions}), stderr="")
            with mock.patch.object(routing.subprocess, "run", return_value=response):
                with self.assertRaises(ValueError):
                    routing.generate_tissue_utr3(["ATGTGA"], "general")


if __name__ == "__main__":
    unittest.main()
