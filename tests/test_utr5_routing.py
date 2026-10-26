"""Routing regressions; no GPU allocation and no model inference."""
import json
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
CODON = PROJECT / "workspace/codon"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(CODON))

import backend_server as backend
import UTR
import main_batch
import tissue_utr5 as routing


class ModelRoutingTests(unittest.TestCase):
    def test_all_bundles_and_fallbacks_are_independent(self):
        manifest = json.loads((routing.MODEL_ROOT / "model_manifest.json").read_text())
        self.assertEqual(set(manifest["tissues"]), set(backend.TISSUES)-{"general"})
        self.assertEqual(sum(not r["used_finetuned_model"] for r in manifest["tissues"].values()), 4)
        inodes = set()
        for tissue in backend.TISSUES:
            directory = routing.resolve_tissue_model(tissue)
            weight = directory / "model.safetensors"
            self.assertFalse(weight.is_symlink())
            self.assertEqual(weight.stat().st_nlink, 1)
            inodes.add((weight.stat().st_dev, weight.stat().st_ino))
            meta = json.loads((directory / "selection_metadata.json").read_text())
            self.assertEqual(meta["tissue"], tissue)
            self.assertEqual(json.loads((directory / "generation_config.json").read_text()), meta["generation_config"])
        self.assertEqual(len(inodes), 30)
        self.assertEqual(routing.resolve_tissue_model("0"), routing.resolve_tissue_model("general"))

    def test_cds_config_inference_supports_existing_backend(self):
        self.assertEqual(routing.tissue_from_cds_model("./cds_tissue_model/Brain/lstmcrf.model"), "Brain")
        self.assertEqual(routing.tissue_from_cds_model("./lstmcrf.113.model"), "general")
        for tissue in ("../Brain", "..", "/tmp/Brain", "Unknown"):
            with self.assertRaises((ValueError, FileNotFoundError)):
                routing.resolve_tissue_model(tissue)

    def test_general_and_tissue_use_bert2bert_for_both_regions(self):
        for tissue in ("general", "Brain", "Tonsil"):
            with self.subTest(tissue=tissue), mock.patch.object(UTR, "generate_tissue_utr5", return_value=["AAA"]) as gen, mock.patch.object(UTR, "generate_tissue_utr3", return_value=["TTT"]) as gen3, mock.patch.object(UTR, "get_utr", side_effect=AssertionError("Unexpected legacy BART call")):
                self.assertEqual(UTR.get_single_sequence("ATGGCC", "tok", "old5", "old3", tissue=tissue), ("AAA", "ATGGCC", "TTT"))
                gen.assert_called_once_with(["ATGGCC"], tissue)
                gen3.assert_called_once_with(["ATGGCCTGA"], tissue)

    def test_gpu_selection_is_inherited_and_cpu_is_honored(self):
        response = SimpleNamespace(returncode=0, stdout=json.dumps({"predictions": ["A"*150]}), stderr="")
        for use_gpu in (True, False):
            with mock.patch.dict("os.environ", {"CUDA_VISIBLE_DEVICES": "GPU-selected-by-backend"}), mock.patch.object(routing.subprocess, "run", return_value=response) as run:
                result = routing.generate_tissue_utr5(["ATGGCC"], "general", use_gpu=use_gpu)
                self.assertEqual(result, ["A"*150])
                self.assertEqual(run.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], "GPU-selected-by-backend" if use_gpu else "")
                self.assertIn(str(routing.MODEL_ROOT / "general"), run.call_args.args[0])
                self.assertEqual(json.loads(run.call_args.kwargs["input"])["sequences"], ["ATGGCC"])

    def test_batch_keeps_tissue_and_uses_both_bert2bert_regions(self):
        with mock.patch.object(main_batch, "generate_tissue_utr5", return_value=["AAA", "CCC"]) as gen, mock.patch.object(main_batch, "generate_tissue_utr3", return_value=["TTT", "GGG"]) as gen3, mock.patch.object(main_batch, "build_utr_pipeline", side_effect=AssertionError("Unexpected legacy BART call")):
            rows = main_batch.generate_full_records_batched(["ATG", "GCC"], 2, False, tissue="Brain")
            gen.assert_called_once_with(["ATG", "GCC"], "Brain", batch_size=2, use_gpu=False)
            gen3.assert_called_once_with(["ATGTGA", "GCCTGA"], "Brain", batch_size=2, use_gpu=False)
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(r[0].endswith("GCCACC") for r in rows))
            self.assertEqual([r[1] for r in rows], ["ATGTGA", "GCCTGA"])
            self.assertEqual([r[2] for r in rows], ["TTT", "GGG"])

    def test_backend_propagates_requested_tissue_to_inference(self):
        @contextmanager
        def lease():
            yield {"index": 0, "uuid": "GPU-test"}
        for tissue in ("general", "Brain"):
            with self.subTest(tissue=tissue), tempfile.TemporaryDirectory() as temp:
                codon = Path(temp)
                task_id = "11111111-111"
                task = backend.Task(task_id, "MA", tissue)
                def inference(*args, **kwargs):
                    (codon / "tasks" / task_id / "output_json.out").write_text(json.dumps(["AAA", "ATG", "TTT"]))
                    return SimpleNamespace(returncode=0, stderr="", stdout="")
                with mock.patch.object(backend, "CODON_DIR", codon), mock.patch.object(backend, "tasks", {task_id: task}), mock.patch.object(backend.gpu_scheduler, "lease", lease), mock.patch.object(backend.subprocess, "run", side_effect=inference) as run, mock.patch.object(backend, "run_rnafold"):
                    backend.run_optimization(task_id)
                    self.assertEqual(task.state, "DONE")
                    command = run.call_args.args[0]
                    self.assertEqual(command[-2:], ["--tissue", tissue])
                    self.assertEqual(run.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], "GPU-test")


if __name__ == "__main__":
    unittest.main()
