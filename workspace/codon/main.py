from __future__ import print_function
import time
import argparse
import random
import torch
import torch.autograd as autograd
import numpy as np
import os
from model.seqmodel import SeqModel
from utils.data import Data
from UTR import get_single_sequence
from tissue_utr5 import tissue_from_cds_model
try:
    import cPickle as pickle
except ImportError:
    import pickle

seed_num = 42
random.seed(seed_num)
torch.manual_seed(seed_num)
np.random.seed(seed_num)


def data_initialization(data):
    data.initial_feature_alphabets()
    data.build_alphabet(data.train_dir)
    data.build_alphabet(data.dev_dir)
    data.build_alphabet(data.test_dir)
    data.fix_alphabet()


def predict_check(pred_variable, gold_variable, mask_variable):
    """
        input:
            pred_variable (batch_size, sent_len): pred tag result, in numpy format
            gold_variable (batch_size, sent_len): gold result variable
            mask_variable (batch_size, sent_len): mask variable
    """
    pred = pred_variable.cpu().data.numpy()
    gold = gold_variable.cpu().data.numpy()
    mask = mask_variable.cpu().data.numpy()
    overlaped = (pred == gold)
    right_token = np.sum(overlaped * mask)
    total_token = mask.sum()
    # print("right: %s, total: %s"%(right_token, total_token))
    return right_token, total_token


def recover_label(pred_variable, gold_variable, mask_variable, label_alphabet, word_recover):
    """
        input:
            pred_variable (batch_size, sent_len): pred tag result
            gold_variable (batch_size, sent_len): gold result variable
            mask_variable (batch_size, sent_len): mask variable
    """

    pred_variable = pred_variable[word_recover]
    gold_variable = gold_variable[word_recover]
    mask_variable = mask_variable[word_recover]
    batch_size = gold_variable.size(0)
    seq_len = gold_variable.size(1)
    mask = mask_variable.cpu().data.numpy()
    pred_tag = pred_variable.cpu().data.numpy()
    gold_tag = gold_variable.cpu().data.numpy()
    batch_size = mask.shape[0]
    pred_label = []
    gold_label = []
    for idx in range(batch_size):
        pred = [label_alphabet.get_instance(pred_tag[idx][idy]) for idy in range(seq_len) if mask[idx][idy] != 0]
        gold = [label_alphabet.get_instance(gold_tag[idx][idy]) for idy in range(seq_len) if mask[idx][idy] != 0]
        assert(len(pred)==len(gold))
        pred_label.append(pred)
        gold_label.append(gold)
    return pred_label, gold_label


def recover_nbest_label(pred_variable, mask_variable, label_alphabet, word_recover):
    """
        input:
            pred_variable (batch_size, sent_len, nbest): pred tag result
            mask_variable (batch_size, sent_len): mask variable
            word_recover (batch_size)
        output:
            nbest_pred_label list: [batch_size, nbest, each_seq_len]
    """
    # exit(0)
    pred_variable = pred_variable[word_recover]
    mask_variable = mask_variable[word_recover]
    batch_size = pred_variable.size(0)
    seq_len = pred_variable.size(1)
    nbest = pred_variable.size(2)
    mask = mask_variable.cpu().data.numpy()
    pred_tag = pred_variable.cpu().data.numpy()
    batch_size = mask.shape[0]
    pred_label = []
    for idx in range(batch_size):
        pred = []
        for idz in range(nbest):
            each_pred = [label_alphabet.get_instance(pred_tag[idx][idy][idz]) for idy in range(seq_len) if mask[idx][idy] != 0]
            pred.append(each_pred)
        pred_label.append(pred)
    return pred_label


def evaluate(data, model, nbest=None):
    instances = data.raw_Ids
    nbest_pred_results = []
    pred_scores = []
    pred_results = []
    gold_results = []
    model.eval()  # eval model
    batch_size = data.HP_batch_size
    start_time = time.time()
    train_num = len(instances)
    total_batch = train_num//batch_size+1
    for batch_id in range(total_batch):  # get the sample size
        start = batch_id*batch_size
        end = (batch_id+1)*batch_size
        if end > train_num:
            end = train_num
        instance = instances[start:end]
        if not instance:
            continue
        batch_word, batch_features, batch_wordlen, batch_wordrecover, batch_label, mask = batchify_with_label(instance, data.HP_gpu, True)
        if nbest:
            scores, nbest_tag_seq = model.decode_nbest(batch_word, batch_features, batch_wordlen, mask, nbest)
            nbest_pred_result = recover_nbest_label(nbest_tag_seq, mask, data.label_alphabet, batch_wordrecover)
            nbest_pred_results += nbest_pred_result
            pred_scores += scores[batch_wordrecover].cpu().data.numpy().tolist()
            # select the best sequence to evalurate
            tag_seq = nbest_tag_seq[:, :, 0]
        else:
            tag_seq = model(batch_word, batch_features, batch_wordlen, mask)
        pred_label, gold_label = recover_label(tag_seq, batch_label, mask, data.label_alphabet, batch_wordrecover)
        pred_results += pred_label
        gold_results += gold_label
    decode_time = time.time() - start_time
    speed = len(instances)/decode_time
    if nbest:
        return speed, nbest_pred_results, pred_scores
    return speed, pred_results, pred_scores


def batchify_with_label(input_batch_list, gpu, volatile_flag=False):
    """
        input: list of words, chars and labels, various length. [[words,chars, labels],[words,chars,labels],...]
            words: word ids for one sentence. (batch_size, sent_len)
            chars: char ids for on sentences, various length. (batch_size, sent_len, each_word_length)
        output:
            zero padding for word and char, with their batch length
            word_seq_tensor: (batch_size, max_sent_len) Variable
            word_seq_lengths: (batch_size,1) Tensor
            char_seq_tensor: (batch_size*max_sent_len, max_word_len) Variable
            char_seq_lengths: (batch_size*max_sent_len,1) Tensor
            char_seq_recover: (batch_size*max_sent_len,1)  recover char sequence order
            label_seq_tensor: (batch_size, max_sent_len)
            mask: (batch_size, max_sent_len)
    """
    batch_size = len(input_batch_list)
    words = [sent[0] for sent in input_batch_list]
    features = [np.asarray(sent[1]) for sent in input_batch_list]
    feature_num = len(features[0][0])
    labels = [sent[2] for sent in input_batch_list]
    word_seq_lengths = torch.LongTensor(list(map(len, words)))
    max_seq_len = word_seq_lengths.max()
    with torch.no_grad():
        word_seq_tensor = autograd.Variable(torch.zeros((batch_size, max_seq_len))).long()
        label_seq_tensor = autograd.Variable(torch.zeros((batch_size, max_seq_len))).long()
    feature_seq_tensors = []
    for idx in range(feature_num):
        feature_seq_tensors.append(autograd.Variable(torch.zeros((batch_size, max_seq_len)), volatile=volatile_flag).long())
    with torch.no_grad():
        mask = autograd.Variable(torch.zeros((batch_size, max_seq_len))).byte()
    for idx, (seq, label, seqlen) in enumerate(zip(words, labels, word_seq_lengths)):
        word_seq_tensor[idx, :seqlen] = torch.LongTensor(seq)
        label_seq_tensor[idx, :seqlen] = torch.LongTensor(label)
        mask[idx, :seqlen] = torch.Tensor([1]*seqlen)
        for idy in range(feature_num):
            feature_seq_tensors[idy][idx,:seqlen] = torch.LongTensor(features[idx][:,idy])
    word_seq_lengths, word_perm_idx = word_seq_lengths.sort(0, descending=True)
    word_seq_tensor = word_seq_tensor[word_perm_idx]
    for idx in range(feature_num):
        feature_seq_tensors[idx] = feature_seq_tensors[idx][word_perm_idx]

    label_seq_tensor = label_seq_tensor[word_perm_idx]
    mask = mask[word_perm_idx]
    _, word_seq_recover = word_perm_idx.sort(0, descending=False)
    if gpu:
        word_seq_tensor = word_seq_tensor.cuda()
        for idx in range(feature_num):
            feature_seq_tensors[idx] = feature_seq_tensors[idx].cuda()
        word_seq_lengths = word_seq_lengths.cuda()
        word_seq_recover = word_seq_recover.cuda()
        label_seq_tensor = label_seq_tensor.cuda()
        mask = mask.cuda()
    return word_seq_tensor, feature_seq_tensors, word_seq_lengths, word_seq_recover, label_seq_tensor, mask


def load_model_decode(data):
    print("Load Model from file: ", data.model_dir)
    model = SeqModel(data)
    model.load_state_dict(torch.load(data.load_model_dir, map_location='cpu'))
    speed, pred_results, pred_scores = evaluate(data, model, data.nbest)
    return pred_results, pred_scores


def decorate(full_length, target_seq='GCCACC'):
    """
    decorate final sequence
    :param full_length: tuple of 5u, orf, 3u
    :param target_seq: attached 5u sequence
    :return:
    """
    seq_5u, orf, _ = full_length
    orf = orf + 'TGA'
    for i in range(1, len(target_seq)+1)[::-1]:
        if seq_5u[-i:] == target_seq[:i]:
            seq_5u += target_seq[i:]
            return seq_5u, orf, full_length[2]
    return seq_5u + target_seq, orf, full_length[2]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tuning with NCRF++')
    # parser.add_argument('--status', choices=['train', 'decode'], help='update algorithm', default='train')
    parser.add_argument('--config',  help='Configuration File')
    parser.add_argument('--tissue', help='5-prime and 3-prime UTR tissue, or general (default: infer from CDS config)')
    args = parser.parse_args()
    data = Data()
    data.HP_gpu = torch.cuda.is_available()
    data.read_config(args.config)
    status = data.status.lower()
    torch.backends.cudnn.enabled = False
    data.load(data.dset_dir)
    data.read_config(args.config)
    data.generate_instance()
    decode_results, pred_scores = load_model_decode(data)
    rna = data.write_nbest_decoded_results(decode_results, pred_scores)
    # input_seq, tokenizer_name, model_name_5u, model_name_3u, use_box, use_spe
    tissue = args.tissue if args.tissue is not None else tissue_from_cds_model(data.load_model_dir)
    full = get_single_sequence(rna, 'Codon_Tokenizer_text_bs', 'mbart-iitb-cc-5u-fbs', 'mbart-iitb-cc-3u-fbs', tissue=tissue)
    full = decorate(full)
    
    # Use decode_dir to determine output directory
    import os
    output_base = os.path.dirname(data.decode_dir) if data.decode_dir else "./sample_data"
    os.makedirs(output_base, exist_ok=True)
    
    f = open(os.path.join(output_base, "output_json.out"), 'w+')
    f.write("[\"" + full[0] + "\", \"" + full[1] + "\", \"" + full[2] + "\"]")
    f.close()
    f = open(os.path.join(output_base, "output_full.out"), 'w+')
    f.write(full[0])
    f.write(full[1])
    f.write(full[2])
    f.close()
    f = open(os.path.join(output_base, "output_5utr.out"), 'w+')
    f.write(full[0])
    f.close()
    f = open(os.path.join(output_base, "output_orf.out"), 'w+')
    f.write(full[1])
    f.close()
    f = open(os.path.join(output_base, "output_3utr.out"), 'w+')
    f.write(full[2])
    f.close()

