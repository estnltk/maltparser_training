# -*- coding: utf-8 -*- 
#
#    Trains MaltParser with given configuration and evaluates on the test corpus;
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
malt_parser_jar   = 'maltparser-1.9.0.jar'
train_corpus      = os.path.join('UD_Estonian-master', 'et-ud-train.cg3-conll')
test_corpus       = os.path.join('UD_Estonian-master', 'et-ud-test.cg3-conll')
test_empty_corpus = None
model_name        = 'estnltkECG'
java_loc          = 'java'
heap_size         = 'Xmx5048M'
configuration     = None
algorithm         = None

final_options_file = None
feature_model_file = None

arg_parser = argparse.ArgumentParser(description='''
  Trains a MaltParser model on the training data set with the given configuration, evaluates it on the test data set, and reports the accuracy.
  Note that if no configuration is given, the script attempts to build the model using the default configuration. The default configuration can be overridden by command line arguments.
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
arg_parser.add_argument("-i", "--train", default=train_corpus, \
                                         help="training corpus CONLL file (default: '"+train_corpus+"');", \
                                         metavar='<train_corpus>')
arg_parser.add_argument("-g", "--test",  default=test_corpus, \
                                         help="evaluation corpus CONLL file (default: '"+test_corpus+"');", \
                                         metavar='<test_corpus>')
arg_parser.add_argument("-te", "--test_empty",  default=test_empty_corpus, \
                                         help="evaluation corpus (CONLL file) without syntactic annotations (default: '"+str(test_empty_corpus)+"');", \
                                         metavar='<test_empty_corpus>')
arg_parser.add_argument("-F", "--final_options", default=final_options_file, \
                              help="final configuration file (finalOptionsFile.xml) with path (default: "+str(final_options_file)+");", \
                              metavar='<finalOptionsFile>')
arg_parser.add_argument("-f", "--feature_model", default=feature_model_file, \
                                                 help="feature model XML file with path (default: "+str(feature_model_file)+");", \
                                                 metavar='<feature_model_file>')
args = arg_parser.parse_args()
malt_parser_jar = args.maltparser_jar
if not args.maltparser_jar or not os.path.isfile(args.maltparser_jar):
   raise Exception('MaltParser jar not found: '+args.maltparser_jar)
train_corpus = args.train
if not args.train or not os.path.isfile(args.train):
   raise Exception('Train corpus not found: '+args.train)
test_corpus = args.test
if not args.test and not os.path.isfile(args.test):
   raise Exception('Test corpus not found: '+args.test)
test_empty_corpus = args.test_empty
if args.test_empty and not os.path.isfile(args.test_empty):
    raise Exception('Test corpus not found: '+args.test_empty)
feature_model_file = args.feature_model
if args.feature_model and not os.path.isfile(args.feature_model):
    raise Exception('Feature model file not found: '+args.feature_model)
final_options_file = args.final_options
if args.final_options and (not os.path.isfile(args.final_options) or \
                           not 'finalOptionsFile.xml' in args.final_options):
    raise Exception('Invalid final_options file: '+args.final_options)
heap_size = args.heap
if not heap_size.startswith('-'):
   heap_size = '-'+heap_size
model_name = args.name

model_name_opt  = '-c '+model_name
eval_out_file   = 'temp.eval.output.txt'

# =============================================================================
#    Perform cleanup
# =============================================================================
if os.path.exists(model_name+'.mco'):
    print('* Removing old model file: '+model_name+'.mco')
    os.unlink(model_name+'.mco')
if os.path.exists(eval_out_file):
    os.unlink(eval_out_file)
    
# =============================================================================
#    Train MaltParser
# =============================================================================
command = None

if not feature_model_file and not final_options_file:
    print ('** No configuration file given. Using the default configuration with command line args. ')
    command = java_loc + ' '+heap_size+' -jar '+malt_parser_jar+' '+model_name_opt+' -i '+train_corpus+' -m learn '
    if algorithm:
        command += ' -a '+algorithm
elif feature_model_file and final_options_file:
    print ('** Using optimization configuration from: '+final_options_file+' and '+feature_model_file+' ')
    command = java_loc + ' '+heap_size+' -jar '+malt_parser_jar+' '+model_name_opt+' -i '+train_corpus+' -m learn -f '+final_options_file+' -F '+feature_model_file
    if algorithm:
        command += ' -a '+algorithm

print ("  Executing:  "+command)
os.system(command)
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




