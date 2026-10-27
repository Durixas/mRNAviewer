"""Position-based codon accuracy for the released CDS test partitions.

This module intentionally has no third-party dependencies.
"""
import csv
import gzip
import hashlib
from collections import defaultdict
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPOSITORY / "data/extracted/cds_tissue_data"
STOP_CODONS = {"TAA", "TAG", "TGA"}
# Synonymous codon-box labels used by iDRO. The terminal X/w represents any stop.
CODONS = {
    "F": dict(zip("ab", ("TTT", "TTC"))),
    "L": dict(zip("cdbfhg", ("TTA", "TTG", "CTT", "CTC", "CTA", "CTG"))),
    "S": dict(zip("bfhgjr", ("TCT", "TCC", "TCA", "TCG", "AGT", "AGC"))),
    "Y": dict(zip("ch", ("TAT", "TAC"))),
    "C": dict(zip("dg", ("TGT", "TGC"))), "W": {"k": "TGG"},
    "P": dict(zip("flmn", ("CCT", "CCC", "CCA", "CCG"))),
    "H": dict(zip("hm", ("CAT", "CAC"))),
    "Q": dict(zip("or", ("CAA", "CAG"))),
    "R": dict(zip("gnrsuq", ("CGT", "CGC", "CGA", "CGG", "AGA", "AGG"))),
    "I": dict(zip("chi", ("ATT", "ATC", "ATA"))), "M": {"j": "ATG"},
    "T": dict(zip("hmor", ("ACT", "ACC", "ACA", "ACG"))),
    "N": dict(zip("io", ("AAT", "AAC"))),
    "K": dict(zip("tu", ("AAA", "AAG"))),
    "V": dict(zip("dgjk", ("GTT", "GTC", "GTA", "GTG"))),
    "A": dict(zip("gnrs", ("GCT", "GCC", "GCA", "GCG"))),
    "D": dict(zip("jr", ("GAT", "GAC"))),
    "E": dict(zip("uq", ("GAA", "GAG"))),
    "G": dict(zip("ksqp", ("GGT", "GGC", "GGA", "GGG"))),
    "X": {"w": "TAA"},
}


def open_text(path, mode="rt"):
    path = Path(path)
    return gzip.open(path, mode, newline="") if path.suffix == ".gz" else path.open(mode.replace("t", ""), newline="")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_test_file(path):
    """Read every blank-separated block, without the web raw-reader's dummy labels."""
    blocks, current = [], []
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        values = line.split()
        if len(values) != 2 or len(values[0]) != 1 or len(values[1]) != 1:
            raise ValueError("Malformed amino-acid/label line {}:{}".format(path, line_number))
        aa, label = values
        if label not in CODONS.get(aa, {}):
            raise ValueError("Unknown amino-acid/label pair {}:{}: {}".format(path, line_number, values))
        current.append((aa, label))
    if current:
        blocks.append(current)
    for index, pairs in enumerate(blocks, 1):
        if len(pairs) < 2 or pairs[-1] != ("X", "w") or any(aa == "X" for aa, _ in pairs[:-1]):
            raise ValueError("Expected a single terminal X/w in {} record {}".format(path, index))
    if not blocks:
        raise ValueError("No test sequences in {}".format(path))
    return blocks


def load_records(data_root=DEFAULT_DATA, tissues=None):
    data_root = Path(data_root)
    available = sorted(p.parent.name for p in data_root.glob("*/test.txt"))
    if not available:
        raise ValueError("No */test.txt under {}; extract the released data first".format(data_root))
    tissues = tissues or available
    if len(set(tissues)) != len(tissues) or set(tissues) - set(available):
        raise ValueError("Duplicate or unavailable tissue names")
    records = []
    for tissue in sorted(tissues):
        for index, pairs in enumerate(read_test_file(data_root / tissue / "test.txt"), 1):
            records.append({"tissue": tissue, "test_sequence": index,
                            "protein": "".join(aa for aa, _ in pairs[:-1]),
                            "reference_labels": "".join(label for _, label in pairs),
                            "reference_cds": "".join(CODONS[aa][label] for aa, label in pairs)})
    return records


def normalize_dna(sequence):
    sequence = "".join(sequence.split()).upper().replace("U", "T")
    if set(sequence) - set("ACGT"):
        raise ValueError("CDS predictions must contain only A/C/G/T/U and whitespace")
    return sequence


def score_cds(prediction, record):
    """No alignment or truncation of the denominator. Extra predicted codons are ignored.

    Missing or incomplete codons count as wrong. Any complete stop codon at the
    reference stop position counts as correct, preserving the X/w definition.
    """
    prediction = normalize_dna(prediction)
    predicted = [prediction[i:i + 3] for i in range(0, len(prediction) - 2, 3)]
    reference = record["reference_cds"]
    coding_total = len(reference) // 3 - 1
    coding_correct = sum(i < len(predicted) and predicted[i] == reference[i * 3:i * 3 + 3]
                         for i in range(coding_total))
    stop_correct = int(len(predicted) > coding_total and predicted[coding_total] in STOP_CODONS)
    return coding_correct + stop_correct, coding_total + 1, coding_correct, coding_total, stop_correct


def score_labels(prediction, record):
    labels = "".join(prediction.split())
    reference = record["reference_labels"]
    correct = [i < len(labels) and labels[i] == label for i, label in enumerate(reference)]
    return sum(correct), len(reference), sum(correct[:-1]), len(reference) - 1, int(correct[-1])


def score_rows(records, predictions, model, allow_subset=False):
    expected = {(r["tissue"], r["test_sequence"]): r for r in records}
    indexed = {}
    for row in predictions:
        key = (row["tissue"], int(row["test_sequence"]))
        if key in indexed:
            raise ValueError("Duplicate prediction key: {}".format(key))
        if key not in expected:
            raise ValueError("Prediction is outside the requested test set: {}".format(key))
        indexed[key] = row
    if not allow_subset and set(indexed) != set(expected):
        raise ValueError("Missing {} test predictions".format(len(set(expected) - set(indexed))))
    if not indexed:
        raise ValueError("No predictions")
    totals = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    scored = []
    for key in sorted(indexed):
        record, row = expected[key], indexed[key]
        if row.get("protein") and row["protein"] != record["protein"]:
            raise ValueError("Protein differs from test partition: {}".format(key))
        if row.get("reference_cds"):
            original = normalize_dna(row["reference_cds"])
            reference = record["reference_cds"]
            if original[:-3] != reference[:-3] or original[-3:] not in STOP_CODONS:
                raise ValueError("Reference differs from test partition: {}".format(key))
        counts = (score_labels(row["predicted_labels"], record) if row.get("predicted_labels")
                  else score_cds(row["predicted_cds"], record))
        for i, value in enumerate(counts + (1,)):
            totals[key[0]][i] += value
        scored.append({**record, **row, "correct_positions": counts[0], "total_positions": counts[1],
                       "coding_correct_codons": counts[2], "coding_total_codons": counts[3],
                       "stop_correct": counts[4]})
    metric_rows = []
    for tissue, values in sorted(totals.items()):
        correct, total, coding_correct, coding_total, stop_correct, sequences = values
        metric_rows.append({"tissue": tissue, "test_acc": correct / total,
                            "correct_positions": correct, "total_positions": total,
                            "test_sequences": sequences,
                            "coding_codon_acc_excluding_stop": coding_correct / coding_total,
                            "coding_correct_codons": coding_correct, "coding_total_codons": coding_total,
                            "stop_correct_sequences": stop_correct, "model": model})
    return metric_rows, scored


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write an empty table")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with open_text(path, "wt") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
