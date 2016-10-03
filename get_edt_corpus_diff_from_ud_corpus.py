# -*- coding: utf-8 -*- 
#
#     Gets sentences from EDT corpus that are different from given sentences from 
#    UD_Estonian ( expectedly files "dev" and "test"):
#
#     *) At first, finds all sentences that are common to given files from 
#        https://github.com/UniversalDependencies/UD_Estonian corpus and the
#        whole https://github.com/EstSyntax/EDT corpus;
#     *) Then extracts the remaining sentences from https://github.com/EstSyntax/EDT 
#        corpus as the diff sentences;
#
#     Outputs results as a "et-train-diff.cg3-conll" file the different sentences;
#
#
from __future__ import unicode_literals, print_function

import re, json
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
from estnltk.syntax.maltparser_support import convert_text_w_syntax_to_CONLL
from estnltk.syntax.utils import read_text_from_cg3_file

from adhoc_fixes import repair_cycles
from feature_generators import add_feature_generator_arguments_to_argparser
from feature_generators import get_feature_generator

# Whether aligned sentences will be checked for identity
check_sentence_identity = True
# Whether an expection should be thrown on a sentence mismatch
exception_on_mismatch   = False
# Whether sent_id-s will be written to separate log files
log_sent_ids = True

OUT_FILE_NAME = "et-train-diff"


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
  This script aligns CONLLU and CG3 format texts, and outputs sentences from the CG3 input that were not present in
  the CONLLU input.
  
  More specifically: the script takes <EDT_corpus_dir> and a list of CONLL file names (<CONLL_file1>, <CONLL_file2>, ...) 
  as input arguments, finds all the sentences from <EDT_corpus_dir> that are also in the CONLL files (aligns sentences using 
  the sentence indices from <CONLL_file>), extracts sentences from <EDT_corpus_dir> that were left unaligned in the previous 
  phase, converts the extracted sentences into CONLL format (the conversion includes some ad hoc fixes and the feature 
  extraction), and rewrites the newly formatted sentences into a new file.
''',\
epilog='''
  The script creates two output files: the file "et-train-diff.cg3-conll" containing all the extracted sentences in CONLL 
  format, and the file "et-train-diff.sent_ids" containing all indices of the extracted sentences, exactly in the same order 
  as sentences in the file with the extension .cg3-conll.
  Note that the keyword arguments -o / --out_file can be used to change the base name of the input files.
'''
)
arg_parser.add_argument("in_dir",   help="the input directory containing EstCG *.inforem files;",  metavar='<EDT_corpus_dir>')
arg_parser.add_argument("in_files", nargs='+', help="a list of *.CONLLU files;",  metavar='<CONLL_file>')
arg_parser.add_argument("-o", "--out_file", default=OUT_FILE_NAME, \
                                        help="the name part for the output files (defaults to name: '"+OUT_FILE_NAME+"');",  
                                        metavar='<out_file_name>')
add_feature_generator_arguments_to_argparser( arg_parser )
# *** Collect input arguments 
args = arg_parser.parse_args()
in_files = [ f for f in args.in_files if os.path.isfile(f) and re.match('.+(\.conllu?)$', f) ]
OUT_FILE_NAME = args.out_file
feat_generator = get_feature_generator( args, verbose=True )

aligned_sentences  = 0
aligned_tokens     = 0
missing_sentences  = 0
missing_tokens     = 0
mismatch_sentences = 0
args_given = False
if os.path.isdir( args.in_dir ) and in_files:
    # *** Process
    start_time = timer()
    #
    # 1) find all sentences that are common to EDT and UD_Estonian
    #  
    args_given = True
    sents = []
    for in_file in in_files:
        print (' Loading input sentences: ', in_file,'...' )
        sents1 = load_sentences_from_ud_corpus( in_file )
        sents.extend( sents1 )
    common_sents = dict()
    edt_files = os.listdir( args.in_dir )
    # sort  sent_id-s  alphabetically
    sents = sorted( sents, key = lambda x : x[0] )
    opened_file_name = ''
    opened_file_text       = None
    opened_file_text_sents = None
    for id, ud_sent in enumerate( sents ):
        # 1) Find the EDT file corresponding to the sent_id
        ud_sent_id = re.sub('^(.+)_(\d+)$', '\\1', ud_sent[0])
        ud_sent_nr = re.sub('^(.+)_(\d+)$', '\\2', ud_sent[0])
        if re.match('[0-9]+$', ud_sent_nr):
            ud_sent_nr = int(ud_sent_nr)
        edt_file = None
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
                # Record the common sentence
                key = (opened_file_name, ud_sent_nr-1)
                common_sents[key] = 1
        
    print()
    print(' 1) Aligning phase completed: ')
    print()
    print( ' Aligned sentences: ', aligned_sentences, '   missing sentences: ',missing_sentences, '   mismatch sentences: ',mismatch_sentences )
    print( ' Aligned tokens:    ', aligned_tokens, '   missing tokens: ', missing_tokens)
    print( ' Common sentences:  ', len(common_sents.keys()))
    print()
        
    #
    # 2) find all sentences that are in EDT, but not in UD_Estonian
    #
    out_file_name = os.path.join( os.path.dirname(in_files[0]), OUT_FILE_NAME+'.cg3-conll' )
    # empty input file
    o_f = codecs.open( out_file_name, mode='w', encoding='utf-8' )
    o_f.close()
    written_sent_ids = []
    uncommon_tokens  = 0
    common_sents_checkup = 0
    for edt_in_file in sorted( edt_files ):
        if edt_in_file.endswith('.inforem'):
            in_file_path = os.path.join( args.in_dir, edt_in_file )
            opened_file_text = read_text_from_cg3_file( \
                    in_file_path, fix_sent_tags=True, clean_up=True, fix_out_of_sent=True )
            opened_file_text_sents = list( opened_file_text.split_by( SENTENCES ) )
            for id, edt_sent_text in enumerate(opened_file_text_sents):
                key = (edt_in_file, id)
                if key not in common_sents:
                    # Convert the sentence to CONLL format
                    edt_sent_text.tag_analysis()
                    ud_sent = [ '', edt_sent_text.word_texts ]
                    repair_cycles( edt_sent_text, ud_sent, layer=LAYER_VISLCG3 )
                    conll_str = convert_text_w_syntax_to_CONLL( edt_sent_text, feat_generator, layer=LAYER_VISLCG3 )
                    # Write results into the file
                    o_f = codecs.open( out_file_name, mode='a', encoding='utf-8' )
                    o_f.write(conll_str)
                    o_f.write('\n')
                    o_f.close()
                    # Remember that the sentence was successfully written to file 
                    uncommon_tokens += len(edt_sent_text.words)
                    written_sent_ids.append( '#'+edt_in_file+'__'+str(id) )
                else: 
                    common_sents_checkup += 1
    print()
    print(' 2) Differentiating phase completed: ')
    print()
    print( ' Common sentences [CHK]:  ', common_sents_checkup )
    print( '     Uncommon sentences:  ', len(written_sent_ids) )
    print( '         tokens covered:  ', uncommon_tokens)
    print()
    if log_sent_ids and written_sent_ids:
        # Log sent ids
        log_file_name = re.sub('^(.+)\.([^.]+)$', '\\1.sent_ids', out_file_name)
        o_f = codecs.open( log_file_name, mode='w', encoding='utf-8' )
        for line in written_sent_ids:
            o_f.write( '#'+line+'\n' )
        o_f.close()
        
    end_time = timer()
    print( ' Processing time: ', format_time(end_time-start_time) )
else:
    if not in_files:
        print('(!) Input *.CONLLU files not found. Please check if the file locations and extensions are correct.')
    print('(!) Invalid input arguments!')
    arg_parser.print_help()

