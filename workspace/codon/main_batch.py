from __future__ import print_function

import argparse
import json
import os
import random
import time

import numpy as np
import torch
from transformers import RobertaTokenizerFast, pipeline

import utils.codonBox as cb
from main import decorate, load_model_decode
from utils.codonBox import box_to_codon
from utils.data import Data
from tissue_utr5 import generate_tissue_utr5, tissue_from_cds_model
from tissue_utr3 import generate_tissue_utr3


seed_num = 42
random.seed(seed_num)
torch.manual_seed(seed_num)
np.random.seed(seed_num)


def decoded_results_to_orfs(data, predict_results, pred_scores):
    """Convert decoded label sequences for every input row into optimized ORFs."""
    sent_num = len(predict_results)
    content_list = data.raw_texts
    assert sent_num == len(content_list)
    assert sent_num == len(pred_scores)

    orfs = []
    for idx in range(sent_num):
        sent_length = len(predict_results[idx][0])
        rna = ""
        for idy in range(sent_length):
            rna += box_to_codon(content_list[idx][0][idy], predict_results[idx][0][idy])
        orfs.append(rna)
    return orfs


def write_decode_output(decode_dir, orfs):
    if not decode_dir:
        return
    with open(decode_dir, "w") as fout:
        for orf in orfs:
            fout.write(orf + "\n")


def write_sequence_outputs(output_base, full_records):
    os.makedirs(output_base, exist_ok=True)

    json_payload = full_records[0] if len(full_records) == 1 else full_records
    with open(os.path.join(output_base, "output_json.out"), "w") as fout:
        json.dump(json_payload, fout)

    output_map = {
        "output_full.out": [record[0] + record[1] + record[2] for record in full_records],
        "output_5utr.out": [record[0] for record in full_records],
        "output_orf.out": [record[1] for record in full_records],
        "output_3utr.out": [record[2] for record in full_records],
    }

    for filename, seqs in output_map.items():
        with open(os.path.join(output_base, filename), "w") as fout:
            for seq in seqs:
                fout.write(seq + "\n")


def build_utr_pipeline(tokenizer_name, model_name, gpu):
    tokenizer = RobertaTokenizerFast.from_pretrained(
        "./{}".format(tokenizer_name),
        max_len=512,
        additional_special_tokens=["<CDS>", "<5UTR>", "<3UTR>"],
    )
    device = 0 if gpu else -1
    return pipeline("translation", model=model_name, tokenizer=tokenizer, device=device)


def prepare_utr_inputs(orfs):
    return ["<CDS>" + cb.codon_to_box(orf) for orf in orfs]


def translate_batch(translator, batch_inputs, batch_size):
    results = translator(
        batch_inputs,
        return_text=True,
        max_length=512,
        batch_size=batch_size,
    )
    return [item["translation_text"] for item in results]


def generate_full_records_batched(orfs, batch_size, gpu, tissue='general'):
    generated_5u = generate_tissue_utr5(orfs, tissue, batch_size=batch_size, use_gpu=gpu)
    generated_3u = generate_tissue_utr3([orf + 'TGA' for orf in orfs], tissue,
                                     batch_size=batch_size, use_gpu=gpu)

    full_records = []
    total = len(orfs)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        print("Generating UTRs for batch {}-{} / {}...".format(start + 1, end, total), flush=True)
        batch_orfs = orfs[start:end]
        batch_5u = generated_5u[start:end]
        batch_3u = generated_3u[start:end]

        for seq_5u, orf, seq_3u in zip(batch_5u, batch_orfs, batch_3u):
            full_records.append(decorate((seq_5u, orf, seq_3u)))
    return full_records


def run(config, batch_size=None, use_gpu=True, require_gpu=False, tissue=None):
    gpu = bool(use_gpu and torch.cuda.is_available())
    if require_gpu and not gpu:
        raise RuntimeError("GPU was required, but torch.cuda.is_available() is False")
    if gpu:
        torch.cuda.set_device(0)

    data = Data()
    data.HP_gpu = gpu
    data.read_config(config)
    if batch_size is not None:
        data.HP_batch_size = int(batch_size)
    data.HP_gpu = gpu

    torch.backends.cudnn.enabled = False
    data.load(data.dset_dir)
    data.HP_gpu = gpu
    data.read_config(config)
    if batch_size is not None:
        data.HP_batch_size = int(batch_size)
    data.HP_gpu = gpu
    data.generate_instance()

    print(
        "Decode settings: sequences={}, batch_size={}, gpu={}".format(
            len(data.raw_Ids), data.HP_batch_size, data.HP_gpu
        ),
        flush=True,
    )
    decode_results, pred_scores = load_model_decode(data)
    orfs = decoded_results_to_orfs(data, decode_results, pred_scores)
    write_decode_output(data.decode_dir, orfs)

    start_time = time.time()
    selected_tissue = tissue if tissue is not None else tissue_from_cds_model(data.load_model_dir)
    full_records = generate_full_records_batched(orfs, data.HP_batch_size, data.HP_gpu, tissue=selected_tissue)

    output_base = os.path.dirname(data.decode_dir) if data.decode_dir else "./sample_data"
    write_sequence_outputs(output_base, full_records)
    print(
        "Batch complete: {} sequence(s), {:.2f}s".format(
            len(full_records), time.time() - start_time
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GPU batch codon optimization and full-length mRNA generation"
    )
    parser.add_argument("--config", help="Configuration File", required=True)
    parser.add_argument("--batch-size", type=int, help="Decode and UTR batch size")
    parser.add_argument("--tissue", help="5-prime and 3-prime UTR tissue, or general; defaults to CDS config")
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Run on CPU even when CUDA is available",
    )
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="Exit immediately if CUDA is unavailable",
    )
    args = parser.parse_args()
    run(
        args.config,
        batch_size=args.batch_size,
        use_gpu=not args.cpu,
        require_gpu=args.require_gpu,
        tissue=args.tissue,
    )
