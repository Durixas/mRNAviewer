"""Check legacy CRF device flags without allocating or reserving a GPU."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from evaluate_checkpoint import configure_device, model_settings


class DeviceTests(unittest.TestCase):
    def test_cpu_never_selects_a_cuda_device(self):
        torch = Mock()
        torch.device.return_value = SimpleNamespace(type="cpu", index=None)
        configure_device(torch, "cpu")
        torch.cuda.set_device.assert_not_called()
        torch.cuda.is_available.assert_not_called()
        self.assertFalse(model_settings(Path(__file__).with_name("model_config.json"), 1).HP_gpu)

    def test_cuda_sets_current_logical_device_and_legacy_flag(self):
        torch = Mock()
        torch.device.return_value = SimpleNamespace(type="cuda", index=1)
        torch.cuda.is_available.return_value = True
        configure_device(torch, "cuda:1")
        torch.cuda.set_device.assert_called_once_with(1)
        self.assertTrue(model_settings(Path(__file__).with_name("model_config.json"), 1, gpu=True).HP_gpu)

    def test_unspecified_cuda_index_defaults_to_visible_device_zero(self):
        torch = Mock()
        torch.device.return_value = SimpleNamespace(type="cuda", index=None)
        torch.cuda.is_available.return_value = True
        configure_device(torch, "cuda")
        torch.cuda.set_device.assert_called_once_with(0)

    def test_unavailable_cuda_reports_error(self):
        torch = Mock()
        torch.device.return_value = SimpleNamespace(type="cuda", index=0)
        torch.cuda.is_available.return_value = False
        with self.assertRaises(ValueError):
            configure_device(torch, "cuda:0")
        torch.cuda.set_device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
