# -*- coding: utf-8 -*- 
#
#    Tests EstNLTK's VISLCG3Parser on the corpus;
#
from __future__ import unicode_literals, print_function

import sys, os, re, os.path, codecs
import argparse

from estnltk.names import *
from estnltk.syntax.parsers import VISLCG3Parser
from estnltk.syntax.utils import read_text_from_conll_file
from estnltk.syntax.maltparser_support import __sort_analyses
from estnltk.syntax.maltparser_support import CONLLFeatGenerator, convert_text_w_syntax_to_CONLL

from estnltk.syntax.vislcg3_syntax import SYNTAX_PIPELINE_1_4, SYNTAX_PIPELINE_ESTCG

def fetchResults( outputFile ):
    resultlines = []
    f = open(outputFile, 'r')
    for line in f:
        line = line.strip()
        if re.match('accuracy.+Token$', line):
            resultlines.append(line)
        if re.match('.+Row (mean|count)$', line):
            resultlines.append(line)
    f.close()
    return resultlines


# =============================================================================
#    Fetch command line arguments
# =============================================================================
vislcg3_cmd       = 'vislcg3'
test_corpus       = 'UD_Estonian-master\\et-ud-test.cg3-conll'
test_empty_corpus = None
force_disamb      = False
pipeline          = SYNTAX_PIPELINE_1_4
#pipeline          = SYNTAX_PIPELINE_ESTCG

arg_parser = argparse.ArgumentParser(description='''
  Evaluates EstNLTK's VISLCG3 based syntactic parser on the test data set, and reports the accuracy.
  Assumes that VISLCG3 is installed into the system and accessible by EstNTLK.
  Note that if no configuration is given, the script attempts to use the default configuration. The default configuration can be overridden by command line arguments.
''',\
epilog='''
  The script needs to be executed in a directory that contains MaltEval.jar, and it should be allowed to write files into that directory. 
  In the evaluation part, the script reports accuracy in terms of three metrics: LA, UAS and LAS.
'''
)
arg_parser.add_argument("-g", "--test",  default=test_corpus, \
                                         help="evaluation corpus CONLL file (default: '"+test_corpus+"');", \
                                         metavar='<test_corpus>')
arg_parser.add_argument("-te", "--test_empty",  default=test_empty_corpus, \
                                         help="evaluation corpus (CONLL file) without syntactic annotations (default: '"+str(test_empty_corpus)+"');", \
                                         metavar='<test_empty_corpus>')
arg_parser.add_argument("-v", "--vislcg",  default=vislcg3_cmd, \
                                           help="name of the vislcg3 executable with full path (default: '"+vislcg3_cmd+"');", \
                                           metavar='<vislcg3_cmd>')
arg_parser.add_argument("-d", "--disamb",  dest='force_disamb', action='store_true', \
                                           help="whether statistical morphological disambiguation should be performed (default: "+str(force_disamb)+");" )
arg_parser.set_defaults(force_disamb=force_disamb)
args = arg_parser.parse_args()
test_corpus = args.test
if not args.test and not os.path.isfile(args.test):
   raise Exception('Test corpus not found: '+args.test)
test_empty_corpus = args.test_empty
if args.test_empty and not os.path.isfile(args.test_empty):
    raise Exception('Test corpus not found: '+args.test_empty)
vislcg3_cmd  = args.vislcg
force_disamb = args.force_disamb

test_out_corpus = test_corpus+'.vislcg3-parsed'
in_corpus = test_empty_corpus if test_empty_corpus else test_corpus
print(' Contents from CONLL output: ', in_corpus, end=' ')
text = read_text_from_conll_file( in_corpus, keep_old=False )
allTokens = len(text[WORDS])
sentStart = len(text.sentence_texts)
print('    (words: ',allTokens,' sentences: ',sentStart, ')',end='\n')
if force_disamb:
    print(' Using EstNLTK disambiguation ...',end='\n')
    text = text.tag_analysis()
print()
del text[LAYER_CONLL]

print(' Parsing text with VISLCG3 ... ')
parser = VISLCG3Parser(vislcg_cmd=vislcg3_cmd, pipeline=pipeline)
parser.parse_text( text )

print(' Converting parsing results to CONLL ... ')
# Convert given text into CONLL string
conll_str = convert_text_w_syntax_to_CONLL( text, CONLLFeatGenerator(), layer=LAYER_VISLCG3 )

# Write results into the file
print('  --> ',test_out_corpus)
print()
o_f = codecs.open( test_out_corpus, mode='w', encoding='utf-8' )
o_f.write(conll_str)
o_f.write('\n')
o_f.close()

eval_out_file = 'temp.eval.output.txt'
java_loc      = 'java'

command = java_loc + ' -jar MaltEval.jar -s '+test_out_corpus+' -g '+test_corpus+' --Metric LAS;UAS;LA > '+eval_out_file
print ("  Executing:  "+command)
os.system(command)
resultLines = fetchResults( eval_out_file )
print( '\n'.join( resultLines ) )





