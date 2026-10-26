"""Real HF beam search for the custom DNABERT2 encoder/decoder.

The upstream generate() ignores num_beams and all length kwargs. This adapter
uses the trained modules unchanged and supplies HF's cache reordering API.
"""
import torch
from transformers import PreTrainedModel, PretrainedConfig, GenerationConfig
from transformers.generation import GenerationMixin
from transformers.modeling_outputs import Seq2SeqLMOutput, BaseModelOutput


class EncoderOutputAdapter(torch.nn.Module):
    main_input_name = "input_ids"

    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, input_ids, attention_mask=None, **kwargs):
        output = self.encoder(input_ids=input_ids, attention_mask=attention_mask, return_dict=True)
        hidden = output[0] if isinstance(output, tuple) else output.last_hidden_state
        return BaseModelOutput(last_hidden_state=hidden)


class BeamReadyBert2Bert(PreTrainedModel, GenerationMixin):
    config_class = PretrainedConfig
    main_input_name = "input_ids"
    _supports_cache_class = False

    def __init__(self, trained):
        config = PretrainedConfig(is_encoder_decoder=True, vocab_size=trained.vocab_size,
                                  bos_token_id=trained.bos_token_id,
                                  decoder_start_token_id=trained.bos_token_id,
                                  eos_token_id=trained.eos_token_id,
                                  pad_token_id=trained.pad_token_id)
        super().__init__(config)
        self.trained = trained
        self.encoder_adapter = EncoderOutputAdapter(trained.encoder)
        self.beam_reorder_calls = 0
        self.generation_config = GenerationConfig.from_model_config(config)

    def get_encoder(self):
        return self.encoder_adapter

    def forward(self, input_ids=None, attention_mask=None, decoder_input_ids=None,
                encoder_outputs=None, past_key_values=None, use_cache=True,
                return_dict=True, **kwargs):
        encoded = encoder_outputs[0]
        out = self.trained.decoder(input_ids=decoder_input_ids,
                                   encoder_hidden_states=encoded,
                                   encoder_attention_mask=attention_mask,
                                   past_key_values=past_key_values,
                                   use_cache=use_cache, return_dict=True)
        return Seq2SeqLMOutput(logits=self.trained.lm_head(out.last_hidden_state),
                              past_key_values=out.past_key_values)

    def prepare_inputs_for_generation(self, input_ids, past_key_values=None,
                                      attention_mask=None, encoder_outputs=None, **kwargs):
        return {"decoder_input_ids": input_ids[:, -1:] if past_key_values is not None else input_ids,
                "past_key_values": past_key_values, "attention_mask": attention_mask,
                "encoder_outputs": encoder_outputs, "use_cache": True}

    def _reorder_cache(self, past_key_values, beam_idx):
        self.beam_reorder_calls += 1
        return tuple(tuple(t.index_select(0, beam_idx.to(t.device)) for t in layer)
                     for layer in past_key_values)


def decode(model, tokenizer, sources, config, device):
    encoded = tokenizer(sources, padding=True, truncation=True,
                        max_length=512, return_tensors="pt").to(device)
    encoded = {key: encoded[key] for key in ("input_ids", "attention_mask")}
    if config["max_length"] > model.trained.decoder.config.max_position_embeddings:
        raise ValueError("Requested length exceeds trained decoder position embeddings")
    with torch.inference_mode():
        ids = model.generate(**encoded, **config, do_sample=False,
                             early_stopping=True if config["num_beams"] > 1 else False)
    predictions = []
    for tokens in ids.tolist():
        if model.config.eos_token_id in tokens:
            tokens = tokens[:tokens.index(model.config.eos_token_id)]
        predictions.append("".join(tokenizer.decode(tokens, skip_special_tokens=True).split()).upper())
    return predictions


def configurations():
    configs = {"greedy": {"num_beams": 1, "length_penalty": 1.0, "min_length": 0, "max_length": 128}}
    for alpha in (0.0, 0.6, 1.0, 1.5, 2.0):
        name = f"beam4_lp{alpha:g}".replace(".", "p")
        configs[name] = {"num_beams": 4, "length_penalty": alpha, "min_length": 0, "max_length": 128}
    for length in (64, 96):
        configs[f"beam4_max{length}"] = {"num_beams": 4, "length_penalty": 1.0, "min_length": 0, "max_length": length}
    for minimum in (16, 32, 64):
        configs[f"beam4_min{minimum}"] = {"num_beams": 4, "length_penalty": 1.0, "min_length": minimum, "max_length": 128}
    for alpha in (1.0, 2.0):
        configs[f"beam8_lp{alpha:g}"] = {"num_beams": 8, "length_penalty": alpha, "min_length": 0, "max_length": 128}
    return configs
