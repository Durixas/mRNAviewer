"""Keep BLAST rows and miRBase accession links in exactly the same order."""

import re
from pathlib import Path


def convert(raw_path, blast_path, accession_path, prefix):
    accession_pattern = re.compile(r"\b" + prefix + r"\d{7}\b")
    with raw_path.open() as source, blast_path.open("w") as matches, accession_path.open("w") as accessions:
        for line in source:
            columns = line.rstrip("\n").split("\t")
            if len(columns) != 13 or not columns[1].startswith("hsa-"):
                continue
            accession = accession_pattern.search(columns[12])
            if accession is None:
                raise ValueError("Missing miRBase accession for " + columns[1])
            matches.write("\t".join(columns[:12]) + "\n")
            accessions.write(accession.group() + "\n")


def main():
    output = Path(__file__).resolve().parent / "output"
    convert(output / "hairpin_raw.out", output / "hairpin.out", output / "acc_hairpin.out", "MI")
    convert(output / "mature_raw.out", output / "mature.out", output / "acc_mature.out", "MIMAT")


if __name__ == "__main__":
    main()
