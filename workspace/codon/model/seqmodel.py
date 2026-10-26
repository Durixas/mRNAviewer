from __future__ import print_function
from __future__ import absolute_import
import torch
import torch.nn as nn
from .wordsequence import WordSequence
from .crf import CRF


class SeqModel(nn.Module):
    def __init__(self, data):
        super(SeqModel, self).__init__()
        self.use_crf = data.use_crf
        print("build network...")
        print("use_char: ", data.use_char)
        if data.use_char:
            print("char feature extractor: ", data.char_feature_extractor)
        print("word feature extractor: ", data.word_feature_extractor)
        print("use crf: ", self.use_crf)

        self.gpu = data.HP_gpu
        self.average_batch = data.average_batch_loss
        ## add two more label for downlayer lstm, use original label size for CRF
        label_size = data.label_alphabet_size
        data.label_alphabet_size += 2
        self.word_hidden = WordSequence(data)
        if self.use_crf:
            self.crf = CRF(label_size, self.gpu)

    def forward(self, word_inputs, feature_inputs, word_seq_lengths, mask):
        outs = self.word_hidden(word_inputs, feature_inputs, word_seq_lengths)
        batch_size = word_inputs.size(0)
        seq_len = word_inputs.size(1)
        if self.use_crf:
            scores, tag_seq = self.crf._viterbi_decode(outs, mask)
        else:
            outs = outs.view(batch_size * seq_len, -1)
            _, tag_seq  = torch.max(outs, 1)
            tag_seq = tag_seq.view(batch_size, seq_len)
            ## filter padded position with zero
            tag_seq = mask.long() * tag_seq
        return tag_seq

    def decode_nbest(self, word_inputs, feature_inputs, word_seq_lengths, mask, nbest):
        if not self.use_crf:
            print("Nbest output is currently supported only for CRF! Exit...")
            exit(0)
        outs = self.word_hidden(word_inputs, feature_inputs, word_seq_lengths)
        scores, tag_seq = self.crf._viterbi_decode_nbest(outs, mask, nbest)
        return scores, tag_seq

