# -*- coding: utf-8 -*- 
#
#     Gets a file from the  https://github.com/UniversalDependencies/UD_Estonian corpus
#    as an input and aligns all the sentences it contains with the corresponding sentences
#    from https://github.com/EstSyntax/EDT  corpus;
#
#     Outputs results as a cg3-conll file, which contains same sentences as corresponding
#    file from UD_Estonian corpus, but in cg format, rather than ud format;
#
#
from __future__ import unicode_literals, print_function

import re
import os, os.path
import codecs, sys
import argparse

from timeit import default_timer as timer

from pprint import pprint 

from estnltk.names import *
from estnltk import Text
from estnltk.core import PACKAGE_PATH, as_unicode

from estnltk.syntax.parsers import MaltParser
from estnltk.syntax.maltparser_support import CONLLFeatGenerator
#from estnltk.syntax.maltparser_support import convert_text_w_syntax_to_CONLL
from estnltk.syntax.utils import read_text_from_cg3_file

from adhoc_fixes import repair_cycles
from feature_generators import add_feature_generator_arguments_to_argparser
from feature_generators import convert_text_w_syntax_to_CONLL
from feature_generators import get_feature_generator


# Whether aligned sentences will be checked for identity
check_sentence_identity = True
# Whether an expection should be thrown on a sentence mismatch
exception_on_mismatch   = False
# Whether sent_id-s will be written to separate log files
log_sent_ids = True


def format_time( sec ):
    # Idea from:   http://stackoverflow.com/a/1384565
    if sec > 864000:
       raise Exception(' Unexpectedly, the value of seconds ',sec,' amounts more than a day! ')
    import time
    return time.strftime('%H:%M:%S', time.gmtime(sec))


def load_sentences_from_ud_corpus( file_name ):
    sentences = []
    comment_sent_id = re.compile('^#\s*sent_id\s(\S+)\s*$')
    sent_id        = None
    sentence_count = 0
    word_count     = 0
    tokens = []
    in_f = codecs.open(file_name, mode='r', encoding='utf-8')
    for line in in_f:
        # A comment line
        if line.startswith('#'):
            m = comment_sent_id.match(line)
            if m:
                sent_id = m.group(1)
            continue
        # Next sentence
        line = line.rstrip()
        if len(line) == 0 or re.match('^\s+$', line):
            if word_count != 0 and tokens:
                sentences.append( [sent_id, tokens])
                sentence_count += 1
            word_count = 0
            tokens     = []
            continue
        # Next token
        features = line.split('\t')
        if len(features) != 10:
            raise Exception(' In file '+in_file+', line with unexpected format: "'+line+'" ')
        selfLabel = features[0]
        token     = features[1]
        word_count += 1
        tokens.append( token )
    in_f.close()
    return sentences

arg_parser = argparse.ArgumentParser(description='''
  This script aligns CONLLU and CG3 format texts, and outputs sentences from the CONLLU input with the syntactic 
  annotations from the CG3 input.
 
  More specifically: the script extracts all the sentences from *.inforem files in <EDT_corpus_dir> that are also contained 
  in <CONLL_file> (aligns sentences using the sentence indices from <CONLL_file>), converts the extracted sentences into 
  CONLL format (the conversion includes some ad hoc fixes and the feature extraction), and rewrites the newly formatted 
  sentences into a new file.
''',\
epilog='''
  The script creates two output files: both files have the same base name as the input file <CONLL_file>, but different 
  extensions. The first file has extension .cg3-conll and contains all the extracted sentences in CONLL format, and the 
  second file has extension .sent_ids and it contains all indices of the extracted sentences, exactly in the same order 
  as sentences in the file with the extension .cg3-conll.
'''
)
arg_parser.add_argument("in_file", help="the .conllu format input file;", metavar='<CONLL_file>')
arg_parser.add_argument("in_dir",  help="the input directory containing EstCG *.inforem files",  metavar='<EDT_corpus_dir>')
add_feature_generator_arguments_to_argparser( arg_parser )
args = arg_parser.parse_args()
feat_generator = get_feature_generator( args, verbose=True )

aligned_sentences  = 0
aligned_tokens     = 0
missing_sentences  = 0
missing_tokens     = 0
mismatch_sentences = 0
if args.in_file and os.path.isfile(args.in_file) and args.in_dir and os.path.isdir(args.in_dir):
    start_time = timer()
    args_given = True
    sents = load_sentences_from_ud_corpus( args.in_file )
    out_file_name = re.sub('^(.+)\.([^.]+)$', '\\1.cg3-conll', args.in_file)
    # empty input file
    o_f = codecs.open( out_file_name, mode='w', encoding='utf-8' )
    o_f.close()
    edt_files = os.listdir( args.in_dir )
    # sort  sent_id-s  alphabetically
    sents = sorted( sents, key = lambda x : x[0] )
    opened_file_name = ''
    opened_file_text       = None
    opened_file_text_sents = None
    written_sent_ids = []
    for id, ud_sent in enumerate( sents ):
        # 1) Find the EDT file corresponding to the sent_id
        ud_sent_id = re.sub('^(.+)_(\d+)$', '\\1', ud_sent[0])
        ud_sent_nr = re.sub('^(.+)_(\d+)$', '\\2', ud_sent[0])
        if re.match('[0-9]+$', ud_sent_nr):
            ud_sent_nr = int(ud_sent_nr)
        edt_file   = None
        # check for existence of the file of the sentence
        for edt_in_file in sorted( edt_files ):
            if edt_in_file.endswith('.inforem'):
                edt_in_file_copy = (edt_in_file.replace('_', '')).lower()
                edt_in_file_copy = re.sub('^(aja|ilu|tea)(.+)$', '\\1_\\2', edt_in_file_copy)
                if edt_in_file_copy.startswith(ud_sent_id):
                    edt_file = edt_in_file
                    break
        if not edt_file:
            print('(!) Could not find EDT file corresponding to sent_id: ',ud_sent[0])
            missing_sentences += 1
            missing_tokens += len(ud_sent[1])
        else:
            # Open a new file if needed
            if opened_file_name != edt_file:
                opened_file_name = edt_file
                in_file_path = os.path.join( args.in_dir, opened_file_name )
                opened_file_text = read_text_from_cg3_file( \
                    in_file_path, fix_sent_tags=True, clean_up=True, fix_out_of_sent=True )
                opened_file_text_sents = list( opened_file_text.split_by( SENTENCES ) )
                #print(opened_file_name,len(opened_file_text_sents))
            if opened_file_text_sents:
                # Fetch the sentence from the opened file
                if not isinstance(ud_sent_nr, int):
                    raise Exception('Unexpected sent_id ', ud_sent)
                if ud_sent_nr < 0 or ud_sent_nr > len(opened_file_text_sents):
                    raise Exception('Unexpected sent_id ',ud_sent,' from file ',opened_file_name)
                edt_sent_text = opened_file_text_sents[ ud_sent_nr-1 ]
                if check_sentence_identity:
                    edt_sent_text_str = (edt_sent_text.text).replace('  ',' ')
                    ud_sent_text_str  = ' '.join(ud_sent[1])
                    if edt_sent_text_str != ud_sent_text_str:
                        print('(!) Mismatching sentences in '+opened_file_name+':', file = sys.stderr)
                        print('EDT:',edt_sent_text_str, file = sys.stderr)
                        print('UD: ',ud_sent_text_str, file = sys.stderr)
                        print('', file = sys.stderr)
                        mismatch_sentences += 1
                        if exception_on_mismatch:
                           raise Exception('(!) Error: mismatching sentences.')
                aligned_sentences += 1
                aligned_tokens    += len(ud_sent[1])
                # Convert the sentence to CONLL format
                edt_sent_text.tag_analysis()
                repair_cycles( edt_sent_text, ud_sent, layer=LAYER_VISLCG3 )
                conll_str = convert_text_w_syntax_to_CONLL( edt_sent_text, feat_generator, layer=LAYER_VISLCG3 )
                # Write results into the file
                o_f = codecs.open( out_file_name, mode='a', encoding='utf-8' )
                o_f.write(conll_str)
                o_f.write('\n')
                o_f.close()
                # Remember that the sentence was successfully written to file 
                written_sent_ids.append( ud_sent[0] )

    if log_sent_ids and written_sent_ids:
        # Log sent ids
        log_file_name = re.sub('^(.+)\.([^.]+)$', '\\1.sent_ids', args.in_file)
        o_f = codecs.open( log_file_name, mode='w', encoding='utf-8' )
        for line in written_sent_ids:
            o_f.write( '#'+line+'\n' )
        o_f.close()
        
    print( ' Aligned sentences: ', aligned_sentences, '   missing sentences: ',missing_sentences, '   mismatch sentences: ',mismatch_sentences )
    print( ' Aligned tokens:    ', aligned_tokens, '   missing tokens: ', missing_tokens)
    end_time = timer()
    print( ' Processing time: ', format_time(end_time-start_time))
else:
    print('(!) Invalid input arguments!')
    arg_parser.print_help()
