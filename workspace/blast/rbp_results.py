"""Find RBPDB sequence motifs in the selected RNA segment.

Coordinates in result.out are 1-based and inclusive, as in BLAST output.
Unbounded repeats such as (U)(n) are skipped: RBPDB does not give a
minimum repeat count, so treating a single U as a binding site is misleading.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path


BASES = {
    "A": "A", "C": "C", "G": "G", "U": "U", "T": "U",
    "R": "[AG]", "Y": "[CU]", "S": "[GC]", "W": "[AU]",
    "K": "[GU]", "M": "[AC]", "B": "[CGU]", "D": "[AGU]",
    "H": "[ACU]", "V": "[ACG]", "N": "[ACGU]",
}


def bases_to_regex(value):
    return "".join(BASES[base] for base in value.upper())


def motif_to_regex(motif):
    """Compile the supported RBPDB IUPAC and bounded-repeat notation."""
    motif = motif.strip().upper().replace("T", "U")
    if not motif or motif == r"\N":
        return None
    parts = []
    i = 0
    while i < len(motif):
        if motif[i] in BASES:
            parts.append(BASES[motif[i]])
            i += 1
            continue
        if motif[i] != "(":
            return None
        close = motif.find(")", i + 1)
        if close < 0:
            return None
        group = motif[i + 1:close]
        alternatives = group.split("/")
        if not all(alt and all(base in BASES for base in alt) for alt in alternatives):
            return None
        atom = "(?:" + "|".join(bases_to_regex(alt) for alt in alternatives) + ")"
        i = close + 1
        if i < len(motif) and motif[i] == "(":
            repeat_end = motif.find(")", i + 1)
            if repeat_end < 0:
                return None
            repeat = motif[i + 1:repeat_end]
            if repeat == "N":
                return None
            if re.fullmatch(r"\d+(?:-\d+)?", repeat):
                limits = [int(number) for number in repeat.split("-")]
                if max(limits) > 100 or limits[0] > limits[-1]:
                    return None
                atom += "{" + ",".join(map(str, limits)) + "}"
                i = repeat_end + 1
        parts.append(atom)
    return re.compile("(?=(" + "".join(parts) + "))")


def find_sites(query, sequences, associations, proteins):
    rows = set()
    for sequence_id, motif in sequences:
        for alternative in motif.split(";"):
            pattern = motif_to_regex(alternative)
            if pattern is None:
                continue
            for match in pattern.finditer(query):
                site = match.group(1)
                if not site:
                    continue
                start = match.start() + 1
                end = start + len(site) - 1
                for protein_id in associations.get(sequence_id, ()):
                    name = proteins.get(protein_id)
                    if name:
                        rows.add((protein_id, name, start, end, site))
    return sorted(rows, key=lambda row: (row[2], row[3], row[1], row[0]))


def main():
    root = Path(__file__).resolve().parent
    query = "".join(root.joinpath("query.fa").read_text().split()).upper().replace("T", "U")
    if not re.fullmatch("[ACGUN]*", query):
        raise ValueError("RBP query contains unsupported nucleotides")

    with root.joinpath("sequence.csv").open(newline="") as handle:
        sequences = [(row[0], row[4]) for row in csv.reader(handle)]

    associations = defaultdict(set)
    with root.joinpath("mid.csv").open(newline="") as handle:
        for row in csv.reader(handle):
            associations[row[1]].add(row[0])

    with root.joinpath("protein.csv").open(newline="") as handle:
        protein_rows = list(csv.reader(handle))
    proteins = {row[0]: row[4] or row[1] for row in protein_rows}
    gene_ids = {row[0]: row[1] for row in protein_rows}

    results = find_sites(query, sequences, associations, proteins)
    output = root / "output"
    output.mkdir(exist_ok=True)
    with (output / "result.out").open("w", newline="") as result_file, (output / "hyperlink.out").open("w") as link_file:
        writer = csv.writer(result_file, lineterminator="\n")
        for protein_id, name, start, end, site in results:
            writer.writerow((name, start, end, site))
            link_file.write(gene_ids[protein_id] + "\n")


if __name__ == "__main__":
    main()
