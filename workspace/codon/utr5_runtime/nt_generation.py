"""Reference-independent nucleotide bounds for genuine HF beam generation."""
import torch
from transformers import LogitsProcessor, LogitsProcessorList


class NucleotideBounds(LogitsProcessor):
    def __init__(self, model, tokenizer, low, high, device):
        pieces = ["".join(tokenizer.decode([i], skip_special_tokens=True).split()).upper()
                  for i in range(model.config.vocab_size)]
        self.lengths = torch.tensor([len(p) for p in pieces], device=device)
        self.valid = torch.tensor([bool(p) and not(set(p)-set("ACGT")) for p in pieces], device=device)
        self.low, self.high = low, high
        self.eos = model.config.eos_token_id
        for special in (model.config.bos_token_id, model.config.pad_token_id, self.eos):
            assert self.lengths[special].item() == 0

    def __call__(self, input_ids, scores):
        lengths = self.lengths[input_ids].sum(dim=1)
        allowed = self.valid[None, :] & (lengths[:, None]+self.lengths[None, :] <= self.high)
        allowed[:, self.eos] = lengths >= self.low
        return scores.masked_fill(~allowed, -float("inf"))


class BoundedDecoder:
    def __init__(self, model, tokenizer, device="cuda"):
        self.model, self.tokenizer, self.device = model, tokenizer, device
        self.processors = {}

    def __call__(self, sources, config):
        low, high = config["min_nt"], config["max_nt"]
        key = (low, high)
        if key not in self.processors:
            self.processors[key] = NucleotideBounds(self.model, self.tokenizer, low, high, self.device)
        kwargs = {k: v for k, v in config.items() if k not in ("min_nt", "max_nt")}
        features = self.tokenizer(sources, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            ids = self.model.generate(**{k: features[k] for k in ("input_ids", "attention_mask")},
                **kwargs, do_sample=False, early_stopping=True,
                logits_processor=LogitsProcessorList([self.processors[key]]))
        predictions = []
        for tokens in ids.tolist():
            if self.model.config.eos_token_id in tokens:
                tokens = tokens[:tokens.index(self.model.config.eos_token_id)]
            pred = "".join(self.tokenizer.decode(tokens, skip_special_tokens=True).split()).upper()
            if not low <= len(pred) <= high or set(pred)-set("ACGT"):
                raise ValueError("Generated DNA violates nucleotide bounds")
            predictions.append(pred)
        return predictions
