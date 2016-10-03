# -*- coding: utf-8 -*- 
#
#    Tests given MaltParser's model on the corpus;
#

import sys, os, re, os.path
import argparse

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
malt_parser_jar   = 'maltparser-1.8.jar'
test_corpus       = os.path.join('UD_Estonian-master', 'et-ud-test.cg3-conll')
test_empty_corpus = None
model_name        = 'estnltkECG'
java_loc          = 'java'
heap_size         = 'Xmx5048M'

final_options_file = None
feature_model_file = None

arg_parser = argparse.ArgumentParser(description='''
  Evaluates given MaltParser's model on the test data set, and reports the accuracy.
  Note that if no configuration is given, the script attempts to use the default configuration. The default configuration can be overridden by command line arguments.
''',\
epilog='''
  The script needs to be executed in a directory that contains MaltEval.jar, the specified <maltparser_jar>, and it should be allowed to write files into that directory. 
  In the evaluation part, the script reports accuracy in terms of three metrics: LA, UAS and LAS.
'''
)
arg_parser.add_argument("-m", "--maltparser_jar", default=malt_parser_jar, \
                                        help="MaltParser's jar file to be used in training/evaluation (default: '"+malt_parser_jar+"');", \
                                        metavar='<maltparser_jar>')
arg_parser.add_argument("-n", "--name",  default=model_name, \
                                         help="name of the model (default: '"+model_name+"');", \
                                         metavar='<model_name>')
arg_parser.add_argument("-j", "--heap", default=heap_size, \
                                        help="Java heap size argument used in executing Java commands (default: '"+heap_size+"');", \
                                        metavar='<heap_size>')
arg_parser.add_argument("-g", "--test",  default=test_corpus, \
                                         help="evaluation corpus CONLL file (default: '"+test_corpus+"');", \
                                         metavar='<test_corpus>')
arg_parser.add_argument("-te", "--test_empty",  default=test_empty_corpus, \
                                         help="evaluation corpus (CONLL file) without syntactic annotations (default: '"+str(test_empty_corpus)+"');", \
                                         metavar='<test_empty_corpus>')
args = arg_parser.parse_args()
malt_parser_jar = args.maltparser_jar
if not args.maltparser_jar or not os.path.isfile(args.maltparser_jar):
   raise Exception('MaltParser jar not found: '+args.maltparser_jar)
test_corpus = args.test
if not args.test and not os.path.isfile(args.test):
   raise Exception('Test corpus not found: '+args.test)
test_empty_corpus = args.test_empty
if args.test_empty and not os.path.isfile(args.test_empty):
    raise Exception('Test corpus not found: '+args.test_empty)
heap_size = args.heap
if not heap_size.startswith('-'):
   heap_size = '-'+heap_size
model_name = args.name

model_name_opt  = '-c '+model_name
eval_out_file   = 'debug.output.txt'

if os.path.exists(model_name+'.mco'):
    # =============================================================================
    #    Evaluate MaltParser
    # =============================================================================
    print(' Parsing test corpus:')
    test_out_corpus = test_corpus+'.parsed'
    in_corpus = test_empty_corpus if test_empty_corpus else test_corpus
    command = java_loc + ' -jar '+malt_parser_jar+' '+model_name_opt+' -i '+in_corpus+' -o '+test_out_corpus+' -m parse '
    print ("  Executing:  "+command)
    os.system(command)
    
    command = java_loc + ' -jar MaltEval.jar -s '+test_out_corpus+' -g '+test_corpus+' --Metric LAS;UAS;LA > '+eval_out_file
    print ("  Executing:  "+command)
    os.system(command)
    resultLines = fetchResults( eval_out_file )
    print( '\n'.join( resultLines ) )
else:
    print(' (!) Unable to find the model file: '+model_name+'.mco')




