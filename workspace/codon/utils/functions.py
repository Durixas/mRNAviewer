from __future__ import print_function
from __future__ import absolute_import
import sys
import numpy as np


def normalize_word(word):
    new_word = ""
    for char in word:
        if char.isdigit():
            new_word += '0'
        else:
            new_word += char
    return new_word


def read_instance(input_file, word_alphabet, label_alphabet, number_normalized, max_sent_length):
    in_lines = open(input_file, 'r').readlines()
    instence_texts, instence_Ids = [], []
    words, features, labels = [], [], []
    word_Ids, feature_Ids, label_Ids = [], [], []
    for line in in_lines:
        for word in line.strip()+'X':  # add terminal
            word = word.upper()
            if sys.version_info[0] < 3:
                word = word.decode('utf-8')
            if number_normalized:
                word = normalize_word(word)
            words.append(word)
            labels.append('j')  # fake label
            word_Ids.append(word_alphabet.get_index(word))
            label_Ids.append(label_alphabet.get_index('j'))  # fake label_id
            # get features for alignment
            feat_list = []
            feat_Id = []
            features.append(feat_list)
            feature_Ids.append(feat_Id)
        if (len(words) > 0) and (max_sent_length > 0):
            instence_texts.append([words, features, labels])
            instence_Ids.append([word_Ids, feature_Ids, label_Ids])
            words = []
            features = []
            labels = []
            word_Ids = []
            feature_Ids = []
            label_Ids = []
    return instence_texts, instence_Ids
