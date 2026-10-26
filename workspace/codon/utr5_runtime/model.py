"""Load the evaluated DNABERT2 encoder / BERT decoder without Hub access."""
import json
from functools import partial

import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer, BertConfig, BertModel

from .beam_generation import BeamReadyBert2Bert, decode
from .dnabert2.bert_layers import BertModel as DNABertModel
from .nt_generation import BoundedDecoder


class TissueBert2Bert(torch.nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = BertConfig.from_dict(config["encoder"])
        self.encoder = DNABertModel(self.config)
        self.decoder = BertModel(BertConfig.from_dict(config["decoder"]))
        self.vocab_size = config["vocab_size"]
        self.lm_head = torch.nn.Linear(self.config.hidden_size, self.vocab_size, bias=False)
        for name in ("bos_token_id", "eos_token_id", "pad_token_id"):
            setattr(self, name, config[name])


def load_decoder(directory, device):
    config = json.loads((directory / "config.json").read_text())
    model = TissueBert2Bert(config)
    model.load_state_dict(load_file(str(directory / "model.safetensors")), strict=True)
    model.requires_grad_(False).to(device).eval()
    tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True,
                                              trust_remote_code=False)
    if (tokenizer.cls_token_id, tokenizer.sep_token_id, tokenizer.pad_token_id) != (model.bos_token_id, model.eos_token_id, model.pad_token_id):
        raise ValueError("Model and tokenizer special tokens differ")
    generation = json.loads((directory / "generation_config.json").read_text())
    wrapped = BeamReadyBert2Bert(model).eval()
    if "min_nt" in generation or "max_nt" in generation:
        if not all(k in generation for k in ("min_nt", "max_nt")):
            raise ValueError("Both nucleotide bounds must be supplied")
        return BoundedDecoder(wrapped, tokenizer, device=device), generation
    # 3′ UTR uses the same unbounded beam decoder as its frozen evaluation.
    return partial(decode, wrapped, tokenizer, device=device), generation
