from __future__ import print_function
from __future__ import absolute_import
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from .wordrep import WordRep

class WordSequence(nn.Module):
    def __init__(self, data):
        super(WordSequence, self).__init__()
        print("build word sequence feature extractor: %s..."%(data.word_feature_extractor))
        self.gpu = data.HP_gpu
        self.use_char = data.use_char
        self.droplstm = nn.Dropout(data.HP_dropout)
        self.bilstm_flag = data.HP_bilstm
        self.lstm_layer = data.HP_lstm_layer
        self.wordrep = WordRep(data)
        self.input_size = data.word_emb_dim
        for idx in range(data.feature_num):
            self.input_size += data.feature_emb_dims[idx]
        # The LSTM takes word embeddings as inputs, and outputs hidden states
        # with dimensionality hidden_dim.
        if self.bilstm_flag:
            lstm_hidden = data.HP_hidden_dim // 2
        else:
            lstm_hidden = data.HP_hidden_dim

        self.word_feature_extractor = data.word_feature_extractor
        if self.word_feature_extractor == "GRU":
            self.lstm = nn.GRU(self.input_size, lstm_hidden, num_layers=self.lstm_layer, batch_first=True, bidirectional=self.bilstm_flag)
        elif self.word_feature_extractor == "LSTM":
            self.lstm = nn.LSTM(self.input_size, lstm_hidden, num_layers=self.lstm_layer, batch_first=True, bidirectional=self.bilstm_flag)
        # The linear layer that maps from hidden state space to tag space
        self.hidden2tag = nn.Linear(data.HP_hidden_dim, data.label_alphabet_size)

        if self.gpu:
            self.droplstm = self.droplstm.cuda()
            self.hidden2tag = self.hidden2tag.cuda()
            self.lstm = self.lstm.cuda()

    def forward(self, word_inputs, feature_inputs, word_seq_lengths):
        """
            input:
                word_inputs: (batch_size, sent_len)
                word_seq_lengths: list of batch_size, (batch_size,1)
                char_inputs: (batch_size*sent_len, word_length)
                char_seq_lengths: list of whole batch_size for char, (batch_size*sent_len, 1)
                char_seq_recover: variable which records the char order information, used to recover char order
            output:
                Variable(batch_size, sent_len, hidden_dim)
        """
        word_represent = self.wordrep(word_inputs, feature_inputs, word_seq_lengths)
        # word_embs (batch_size, seq_len, embed_size)
        packed_words = pack_padded_sequence(word_represent, word_seq_lengths.cpu().numpy(), True)
        hidden = None
        lstm_out, hidden = self.lstm(packed_words, hidden)
        lstm_out, _ = pad_packed_sequence(lstm_out)
        # lstm_out (seq_len, seq_len, hidden_size)
        feature_out = self.droplstm(lstm_out.transpose(1, 0))
        # feature_out (batch_size, seq_len, hidden_size)
        outputs = self.hidden2tag(feature_out)
        return outputs
