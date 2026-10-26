def codon_to_box(seq):
    w = ''
    for s in [seq[i: i+3] for i in range(0, len(seq), 3)]:
        if s == 'TTT':
            w += 'a'
        elif s == 'TTC':
            w += 'b'
        elif s == 'TTA':
            w += 'c'
        elif s == 'TTG':
            w += 'd'
        elif s == 'TCT':
            w += 'b'
        elif s == 'TCC':
            w += 'f'
        elif s == 'TCA':
            w += 'h'
        elif s == 'TCG':
            w += 'g'
        elif s == 'TAT':
            w += 'c'
        elif s == 'TAC':
            w += 'h'
        elif s == 'TAA':
            w += 'w'
        elif s == 'TAG':
            w += 'w'
        elif s == 'TGT':
            w += 'd'
        elif s == 'TGC':
            w += 'g'
        elif s == 'TGA':
            w += 'w'
        elif s == 'TGG':
            w += 'k'
        elif s == 'CTT':
            w += 'b'
        elif s == 'CTC':
            w += 'f'
        elif s == 'CTA':
            w += 'h'
        elif s == 'CTG':
            w += 'g'
        elif s == 'CCT':
            w += 'f'
        elif s == 'CCC':
            w += 'l'
        elif s == 'CCA':
            w += 'm'
        elif s == 'CCG':
            w += 'n'
        elif s == 'CAT':
            w += 'h'
        elif s == 'CAC':
            w += 'm'
        elif s == 'CAA':
            w += 'o'
        elif s == 'CAG':
            w += 'r'
        elif s == 'CGT':
            w += 'g'
        elif s == 'CGC':
            w += 'n'
        elif s == 'CGA':
            w += 'r'
        elif s == 'CGG':
            w += 's'
        elif s == 'ATT':
            w += 'c'
        elif s == 'ATC':
            w += 'h'
        elif s == 'ATA':
            w += 'i'
        elif s == 'ATG':
            w += 'j'
        elif s == 'ACT':
            w += 'h'
        elif s == 'ACC':
            w += 'm'
        elif s == 'ACA':
            w += 'o'
        elif s == 'ACG':
            w += 'r'
        elif s == 'AAT':
            w += 'i'
        elif s == 'AAC':
            w += 'o'
        elif s == 'AAG':
            w += 'u'
        elif s == 'AAA':
            w += 't'
        elif s == 'AGT':
            w += 'j'
        elif s == 'AGC':
            w += 'r'
        elif s == 'AGA':
            w += 'u'
        elif s == 'AGG':
            w += 'q'
        elif s == 'GTT':
            w += 'd'
        elif s == 'GTC':
            w += 'g'
        elif s == 'GTA':
            w += 'j'
        elif s == 'GTG':
            w += 'k'
        elif s == 'GCT':
            w += 'g'
        elif s == 'GCC':
            w += 'n'
        elif s == 'GCA':
            w += 'r'
        elif s == 'GCG':
            w += 's'
        elif s == 'GAT':
            w += 'j'
        elif s == 'GAC':
            w += 'r'
        elif s == 'GAA':
            w += 'u'
        elif s == 'GAG':
            w += 'q'
        elif s == 'GGT':
            w += 'k'
        elif s == 'GGC':
            w += 's'
        elif s == 'GGA':
            w += 'q'
        elif s == 'GGG':
            w += 'p'
    return w


def box_to_codon(seq_aa, seq_box):
    s = ''
    for i in range(len(seq_aa)):
        line = f'{seq_aa[i]} {seq_box[i]}'
        if line == 'F a':
            s = s + 'TTT'
        elif line == 'F b':
            s = s + 'TTC'
        elif line == 'L c':
            s = s + 'TTA'
        elif line == 'L d':
            s = s + 'TTG'
        elif line == 'S b':
            s = s + 'TCT'
        elif line == 'S f':
            s = s + 'TCC'
        elif line == 'S h':
            s = s + 'TCA'
        elif line == 'S g':
            s = s + 'TCG'
        elif line == 'Y c':
            s = s + 'TAT'
        elif line == 'Y h':
            s = s + 'TAC'
        elif line == 'X w':
            s = s + 'TAA'
        elif line == 'C d':
            s = s + 'TGT'
        elif line == 'C g':
            s = s + 'TGC'
        elif line == 'W k':
            s = s + 'TGG'
        elif line == 'L b':
            s = s + 'CTT'
        elif line == 'L f':
            s = s + 'CTC'
        elif line == 'L h':
            s = s + 'CTA'
        elif line == 'L g':
            s = s + 'CTG'
        elif line == 'P f':
            s = s + 'CCT'
        elif line == 'P l':
            s = s + 'CCC'
        elif line == 'P m':
            s = s + 'CCA'
        elif line == 'P n':
            s = s + 'CCG'
        elif line == 'H h':
            s = s + 'CAT'
        elif line == 'H m':
            s = s + 'CAC'
        elif line == 'Q o':
            s = s + 'CAA'
        elif line == 'Q r':
            s = s + 'CAG'
        elif line == 'R g':
            s = s + 'CGT'
        elif line == 'R n':
            s = s + 'CGC'
        elif line == 'R r':
            s = s + 'CGA'
        elif line == 'R s':
            s = s + 'CGG'
        elif line == 'I c':
            s = s + 'ATT'
        elif line == 'I h':
            s = s + 'ATC'
        elif line == 'I i':
            s = s + 'ATA'
        elif line == 'M j':
            s = s + 'ATG'
        elif line == 'T h':
            s = s + 'ACT'
        elif line == 'T m':
            s = s + 'ACC'
        elif line == 'T o':
            s = s + 'ACA'
        elif line == 'T r':
            s = s + 'ACG'
        elif line == 'N i':
            s = s + 'AAT'
        elif line == 'N o':
            s = s + 'AAC'
        elif line == 'K u':
            s = s + 'AAG'
        elif line == 'K t':
            s = s + 'AAA'
        elif line == 'S j':
            s = s + 'AGT'
        elif line == 'S r':
            s = s + 'AGC'
        elif line == 'R u':
            s = s + 'AGA'
        elif line == 'R q':
            s = s + 'AGG'
        elif line == 'V d':
            s = s + 'GTT'
        elif line == 'V g':
            s = s + 'GTC'
        elif line == 'V j':
            s = s + 'GTA'
        elif line == 'V k':
            s = s + 'GTG'
        elif line == 'A g':
            s = s + 'GCT'
        elif line == 'A n':
            s = s + 'GCC'
        elif line == 'A r':
            s = s + 'GCA'
        elif line == 'A s':
            s = s + 'GCG'
        elif line == 'D j':
            s = s + 'GAT'
        elif line == 'D r':
            s = s + 'GAC'
        elif line == 'E u':
            s = s + 'GAA'
        elif line == 'E q':
            s = s + 'GAG'
        elif line == 'G k':
            s = s + 'GGT'
        elif line == 'G s':
            s = s + 'GGC'
        elif line == 'G q':
            s = s + 'GGA'
        elif line == 'G p':
            s = s + 'GGG'
        elif line == 'N w':
            s = s + 'AAC'
        elif line == 'E w':
            s = s + 'GAA'
        else:
            print(f'wrong: {line}')
    return s


if __name__ == '__main__':
    k = []
    with open('../data/tran_c5.txt') as f:
        lines = f.read().split('\n')
        for index, line in enumerate(lines):
            line = line.strip()
            box = codon_to_box(line)
            k.append(box)
            print(box)
    with open('../data/box.source', 'w') as f:
        for i in k:
            f.write(i+'\n')
    pass
