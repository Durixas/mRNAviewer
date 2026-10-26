from __future__ import print_function
from __future__ import absolute_import
from .alphabet import Alphabet
from .functions import *
from .codonBox import box_to_codon

try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

START = "</s>"
UNKNOWN = "</unk>"
PADDING = "</pad>"


class Data:
    def __init__(self):
        self.MAX_SENTENCE_LENGTH = 500
        self.MAX_WORD_LENGTH = -1
        self.number_normalized = True
        self.norm_word_emb = False
        self.norm_char_emb = False
        self.word_alphabet = Alphabet('word')
        self.char_alphabet = Alphabet('character')

        self.feature_name = []
        self.feature_alphabets = []
        self.feature_num = len(self.feature_alphabets)
        self.feat_config = None

        self.label_alphabet = Alphabet('label',True)
        self.tagScheme = "NoSeg" ## BMES/BIO

        self.seg = True

        # I/O
        self.train_dir = None
        self.dev_dir = None
        self.test_dir = None
        self.raw_dir = None

        self.decode_dir = None
        self.dset_dir = None  # data vocabulary related file
        self.model_dir = None  # model save  file
        self.load_model_dir = None  # model load file

        self.word_emb_dir = None
        self.char_emb_dir = None
        self.feature_emb_dirs = []

        self.raw_texts = []
        self.raw_Ids = []

        self.pretrain_word_embedding = None
        self.pretrain_char_embedding = None
        self.pretrain_feature_embeddings = []

        self.label_size = 0
        self.word_alphabet_size = 0
        self.char_alphabet_size = 0
        self.label_alphabet_size = 0
        self.feature_alphabet_sizes = []
        self.feature_emb_dims = []
        self.norm_feature_embs = []
        self.word_emb_dim = 50
        self.char_emb_dim = 30

        # Networks
        self.word_feature_extractor = "LSTM"
        self.use_char = False
        self.char_feature_extractor = "CNN"
        self.use_crf = True
        self.nbest = None

        # Training
        self.average_batch_loss = False
        self.optimizer = "SGD"  # "SGD"/"AdaGrad"/"AdaDelta"/"RMSProp"/"Adam"
        self.status = "train"
        # Hyper parameters
        self.HP_cnn_layer = 4
        self.HP_iteration = 10000
        self.HP_batch_size = 10
        self.HP_char_hidden_dim = 50
        self.HP_hidden_dim = 200
        self.HP_dropout = 0.5
        self.HP_lstm_layer = 1
        self.HP_bilstm = True

        self.HP_gpu =True
        self.HP_lr = 0.015
        self.HP_lr_decay = 0.05
        self.HP_clip = None
        self.HP_momentum = 0
        self.HP_l2 = 1e-8

    def initial_feature_alphabets(self):
        items = open(self.train_dir, 'r').readline().strip('\n').split()
        total_column = len(items)
        if total_column > 2:
            for idx in range(1, total_column-1):
                feature_prefix = items[idx].split(']',1)[0]+"]"
                self.feature_alphabets.append(Alphabet(feature_prefix))
                self.feature_name.append(feature_prefix)
                print("Find feature: ", feature_prefix)
        self.feature_num = len(self.feature_alphabets)
        self.pretrain_feature_embeddings = [None]*self.feature_num
        self.feature_emb_dims = [20]*self.feature_num
        self.feature_emb_dirs = [None]*self.feature_num
        self.norm_feature_embs = [False]*self.feature_num
        self.feature_alphabet_sizes = [0]*self.feature_num
        if self.feat_config:
            for idx in range(self.feature_num):
                if self.feature_name[idx] in self.feat_config:
                    self.feature_emb_dims[idx] = self.feat_config[self.feature_name[idx]]['emb_size']
                    self.feature_emb_dirs[idx] = self.feat_config[self.feature_name[idx]]['emb_dir']
                    self.norm_feature_embs[idx] = self.feat_config[self.feature_name[idx]]['emb_norm']
        # exit(0)

    def build_alphabet(self, input_file):
        in_lines = open(input_file, 'r').readlines()
        for line in in_lines:
            if len(line) > 2:
                pairs = line.strip().split()
                word = pairs[0]
                if self.number_normalized:
                    word = normalize_word(word)
                label = pairs[-1]
                self.label_alphabet.add(label)
                self.word_alphabet.add(word)
                # build feature alphabet
                for idx in range(self.feature_num):
                    feat_idx = pairs[idx+1].split(']',1)[-1]
                    self.feature_alphabets[idx].add(feat_idx)
                for char in word:
                    self.char_alphabet.add(char)
        self.word_alphabet_size = self.word_alphabet.size()
        self.char_alphabet_size = self.char_alphabet.size()
        self.label_alphabet_size = self.label_alphabet.size()
        for idx in range(self.feature_num):
            self.feature_alphabet_sizes[idx] = self.feature_alphabets[idx].size()
        startS = False
        startB = False
        for label, _ in self.label_alphabet.iteritems():
            if "S-" in label.upper():
                startS = True
            elif "B-" in label.upper():
                startB = True
        if startB:
            if startS:
                self.tagScheme = "BMES"
            else:
                self.tagScheme = "BIO"

    def fix_alphabet(self):
        self.word_alphabet.close()
        self.char_alphabet.close()
        self.label_alphabet.close()
        for idx in range(self.feature_num):
            self.feature_alphabets[idx].close()

    def generate_instance(self):
        self.fix_alphabet()
        self.raw_texts, self.raw_Ids = read_instance(self.raw_dir, self.word_alphabet, self.label_alphabet, self.number_normalized, self.MAX_SENTENCE_LENGTH)

    def load(self, data_file):
        f = open(data_file, 'rb')
        tmp_dict = pickle.load(f)
        f.close()
        self.__dict__.update(tmp_dict)

    def save(self, save_file):
        f = open(save_file, 'wb')
        pickle.dump(self.__dict__, f, 2)
        f.close()

    def write_nbest_decoded_results(self, predict_results, pred_scores):
        fout = open(self.decode_dir, 'w')
        sent_num = len(predict_results)
        content_list = self.raw_texts
        assert(sent_num == len(content_list))
        assert(sent_num == len(pred_scores))
        rna = ''
        for idx in range(sent_num):
            sent_length = len(predict_results[idx][0])
            rna = ''
            for idy in range(sent_length):
                rna = rna + box_to_codon(content_list[idx][0][idy], predict_results[idx][0][idy])
            fout.write(rna+'\n')
        fout.close()
        print(f"Predict best result has been written into {self.decode_dir}")
        return rna

    def read_config(self, config_file):
        config = config_file_to_dict(config_file)
        # read data:
        the_item = 'train_dir'
        if the_item in config:
            self.train_dir = config[the_item]
        the_item = 'dev_dir'
        if the_item in config:
            self.dev_dir = config[the_item]
        the_item = 'test_dir'
        if the_item in config:
            self.test_dir = config[the_item]
        the_item = 'raw_dir'
        if the_item in config:
            self.raw_dir = config[the_item]
        the_item = 'decode_dir'
        if the_item in config:
            self.decode_dir = config[the_item]
        the_item = 'dset_dir'
        if the_item in config:
            self.dset_dir = config[the_item]
        the_item = 'model_dir'
        if the_item in config:
            self.model_dir = config[the_item]
        the_item = 'load_model_dir'
        if the_item in config:
            self.load_model_dir = config[the_item]

        the_item = 'word_emb_dir'
        if the_item in config:
            self.word_emb_dir = config[the_item]
        the_item = 'char_emb_dir'
        if the_item in config:
            self.char_emb_dir = config[the_item]

        the_item = 'MAX_SENTENCE_LENGTH'
        if the_item in config:
            self.MAX_SENTENCE_LENGTH = int(config[the_item])
        the_item = 'MAX_WORD_LENGTH'
        if the_item in config:
            self.MAX_WORD_LENGTH = int(config[the_item])

        the_item = 'norm_word_emb'
        if the_item in config:
            self.norm_word_emb = str2bool(config[the_item])
        the_item = 'norm_char_emb'
        if the_item in config:
            self.norm_char_emb = str2bool(config[the_item])
        the_item = 'number_normalized'
        if the_item in config:
            self.number_normalized = str2bool(config[the_item])

        the_item = 'seg'
        if the_item in config:
            self.seg = str2bool(config[the_item])
        the_item = 'word_emb_dim'
        if the_item in config:
            self.word_emb_dim = int(config[the_item])
        the_item = 'char_emb_dim'
        if the_item in config:
            self.char_emb_dim = int(config[the_item])

        # read network:
        the_item = 'use_crf'
        if the_item in config:
            self.use_crf = str2bool(config[the_item])
        the_item = 'use_char'
        if the_item in config:
            self.use_char = str2bool(config[the_item])
        the_item = 'word_seq_feature'
        if the_item in config:
            self.word_feature_extractor = config[the_item]
        the_item = 'char_seq_feature'
        if the_item in config:
            self.char_feature_extractor = config[the_item]
        the_item = 'nbest'
        if the_item in config:
            self.nbest = int(config[the_item])
        the_item = 'feature'
        if the_item in config:
            self.feat_config = config[the_item]  # feat_config is a dict

        # read training setting:
        the_item = 'optimizer'
        if the_item in config:
            self.optimizer = config[the_item]
        the_item = 'ave_batch_loss'
        if the_item in config:
            self.average_batch_loss = str2bool(config[the_item])
        the_item = 'status'
        if the_item in config:
            self.status = config[the_item]

        # read Hyper parameters:
        the_item = 'cnn_layer'
        if the_item in config:
            self.HP_cnn_layer = int(config[the_item])
        the_item = 'iteration'
        if the_item in config:
            self.HP_iteration = int(config[the_item])
        the_item = 'batch_size'
        if the_item in config:
            self.HP_batch_size = int(config[the_item])

        the_item = 'char_hidden_dim'
        if the_item in config:
            self.HP_char_hidden_dim = int(config[the_item])
        the_item = 'hidden_dim'
        if the_item in config:
            self.HP_hidden_dim = int(config[the_item])
        the_item = 'dropout'
        if the_item in config:
            self.HP_dropout = float(config[the_item])
        the_item = 'lstm_layer'
        if the_item in config:
            self.HP_lstm_layer = int(config[the_item])
        the_item = 'bilstm'
        if the_item in config:
            self.HP_bilstm = str2bool(config[the_item])

        the_item = 'gpu'
        if the_item in config:
            self.HP_gpu = str2bool(config[the_item])
        the_item = 'learning_rate'
        if the_item in config:
            self.HP_lr = float(config[the_item])
        the_item = 'lr_decay'
        if the_item in config:
            self.HP_lr_decay = float(config[the_item])
        the_item = 'clip'
        if the_item in config:
            self.HP_clip = float(config[the_item])
        the_item = 'momentum'
        if the_item in config:
            self.HP_momentum = float(config[the_item])
        the_item = 'l2'
        if the_item in config:
            self.HP_l2 = float(config[the_item])


def config_file_to_dict(input_file):
    config = {}
    fins = open(input_file, 'r').readlines()
    for line in fins:
        if len(line) > 0 and line[0] == "#":
            continue
        if "=" in line:
            pair = line.strip().split('#', 1)[0].split('=', 1)
            item = pair[0]
            if item == "feature":
                if item not in config:
                    feat_dict = {}
                    config[item] = feat_dict
                feat_dict = config[item]
                new_pair = pair[-1].split()
                feat_name = new_pair[0]
                one_dict = {}
                one_dict["emb_dir"] = None
                one_dict["emb_size"] = 10
                one_dict["emb_norm"] = False
                if len(new_pair) > 1:
                    for idx in range(1, len(new_pair)):
                        conf_pair = new_pair[idx].split('=')
                        if conf_pair[0] == "emb_dir":
                            one_dict["emb_dir"] = conf_pair[-1]
                        elif conf_pair[0] == "emb_size":
                            one_dict["emb_size"] = int(conf_pair[-1])
                        elif conf_pair[0] == "emb_norm":
                            one_dict["emb_norm"] = str2bool(conf_pair[-1])
                feat_dict[feat_name] = one_dict
                # print "feat",feat_dict
            else:
                if item in config:
                    print("Warning: duplicated config item found: %s, updated."%(pair[0]))
                config[item] = pair[-1]
    return config


def str2bool(string):
    if string == "True" or string == "true" or string == "TRUE":
        return True
    else:
        return False
