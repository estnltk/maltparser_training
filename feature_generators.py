# -*- coding: utf-8 -*- 
#

from __future__ import unicode_literals, print_function
from estnltk.names import *

from estnltk.core import PACKAGE_PATH
from estnltk.syntax.maltparser_support import _loadKSubcatRelations, _findKsubcatFeatures

from estnltk.syntax.parsers import MaltParser
from estnltk.syntax.maltparser_support import CONLLFeatGenerator as EstNLTKCONLLFeatGenerator

import re
import os, os.path
import codecs

# =============================================================================
# =============================================================================
#  Generating features to be used in CONLL
# =============================================================================
# =============================================================================

class CONLLFeatGenerator(object):
    ''' Class for generating CONLL format "features" from EstNLTK's sentences.

         More specifically, the generated "features" include fields ID, FORM,
        LEMMA, CPOSTAG, POSTAG, FEATS of a CONLL format line.
         At each feature-generation step, the generator gets a word and a
        sentence the word belongs to as an input, and generates features of the
        given word as an output;
    '''

    addAmbiguousPos  = False
    addVerbcGramm    = False
    addNomAdvVinf    = False
    addClauseBound   = False
    addSeSayingVerbs = False
    kSubCatRelsLex  = None
    kFeatures       = None
    vcFeatures      = None
    clbFeatures     = None
    sayingverbs     = None
    
    parseScope      = None

    def __init__( self, **kwargs):
       ''' Initializes CONLLFeatGenerator with the configuration given in
           the keyword arguments;

           Parameters
           -----------
           addAmbiguousPos : bool
                If True, the words having an ambiguous part-of-speech will have
                their POSTAG field (fine-grained POS tag) filled with a
                contatenation of all ambiguous POS tags; If False, POSTAG field
                is the same as CPOSTAG;
                Default: False
           addKSubCatRels : string
                If used, the argument value should contain a location of the
                _K_ subcategorization relations file -- a file that can be loaded
                via method _loadKSubcatRelations();
                Then the dictionary loaded from file is used to provide adposition
                type ("post" or "pre");
                Default: None
           addVerbChainGramm : bool
                If True, verb chains layer in the input Text object is used to
                extract multiword grammatical predicates ( 'olema' + nud_verb, 
                modal + infinite_verb,  phasal + infinite_verb,  negation ) and
                FEATS parts of the verbs beloning to these constructions are 
                populated with new features indicating the presence of these
                constructions;
                Default: False
           addNomAdvVinf : bool
                If True, verb chains layer in the input Text object is used to
                extract (verb,nom/adv,v_inf) triples, and FEATS parts of the verbs 
                beloning to these constructions are populated with new features 
                indicating the presence of these constructions;
                NB! (olema,nom/adv,v_inf) triples are excluded due to relations
                in these triples probably being unsystemized in training data;
                Default: False
           addClauseBound : bool
                If True, clause boundary markers from the input Text object are
                added as FEATS;
                Default: False
           addSeSayingVerbs : bool
                If True, verb chain and clause annotation is used to detect sentence
                ending saying verbs, and label 'se_saying_verb' is added to FEATS 
                part of each such verb.
                Default: False
           parseScope : str
                The smallest chunk of text to be parsed independently: a sentence 
                or a clause. If this parameter is set to 'clauses', then the input
                text is parsed clause-by-clause (instead of sentence-by-sentence
                parsing), and the results of the clause-wise parsing are clued back
                to sentence afterwards;
                Possible values: 'sentences', 'clauses'
                Default: 'sentences'
       '''
       self.parseScope = SENTENCES
       # ** Parse keyword arguments
       for argName, argVal in kwargs.items():
            if argName in ['addAmbiguousPos']:
                self.addAmbiguousPos = bool(argVal)
            elif argName in ['addVerbGramm', 'addVerbcGramm', 'addVerbchainGramm']:
                self.addVerbcGramm = bool(argVal)
            elif argName in ['addNomAdvVinf']:
                self.addNomAdvVinf = bool(argVal)
            elif argName in ['addClauseBound']:
                self.addClauseBound = bool(argVal)
            elif argName in ['addSeSayingVerbs']:
                self.addSeSayingVerbs = bool(argVal)
            elif argName in ['parseScope']:
                self.parseScope = argVal
            elif argName in ['addKSubCatRels', 'kSubCatRels']:
                if os.path.isfile(argVal):
                    # Load K subcategorization lexicon from file
                    self.kSubCatRelsLex = _loadKSubcatRelations( argVal )
                else:
                    raise Exception('(!) Lexicon file not found: ',argVal)


    def generate_features( self, sentence_text, wid ):
        ''' Generates and returns a list of strings, containing tab-separated
            features ID, FORM, LEMMA, CPOSTAG, POSTAG, FEATS of the word
            (the word with index *wid* from the given *sentence_text*).

            Parameters
            -----------
            sentence_text : estnltk.text.Text
                Text object corresponding to a single sentence.
                Words of the sentence, along with their morphological analyses,
                should be accessible via the layer WORDS.
                And each word should be a dict, containing morphological features
                in ANALYSIS part;

            wid : int
                Index of the word/token, whose features need to be generated;

        '''
        assert WORDS in sentence_text and len(sentence_text[WORDS])>0, \
               " (!) 'words' layer missing or empty in given Text!"
        sentence = sentence_text[WORDS]
        assert -1 < wid and wid < len(sentence), ' (!) Invalid word id: '+str(wid)

        # 1) Pre-process (if required)
        if wid == 0:
            #  *** Add adposition (_K_) type
            if self.kSubCatRelsLex:
                self.kFeatures = \
                    _findKsubcatFeatures( sentence, self.kSubCatRelsLex, addFeaturesToK = True )
            #  *** Add verb chain info
            if self.addVerbcGramm or self.addNomAdvVinf:
                self.vcFeatures = generate_verb_chain_features( sentence_text, \
                                                                addGrammPred=self.addVerbcGramm, \
                                                                addNomAdvVinf=self.addNomAdvVinf )
            #  *** Add sentence ending saying verbs
            if self.addSeSayingVerbs:
                self.sayingverbs = detect_sentence_ending_saying_verbs( sentence_text )
            #  *** Add clause boundary info
            if self.addClauseBound:
                self.clbFeatures = []
                for tag in sentence_text.clause_annotations:
                    if not tag:
                        self.clbFeatures.append( [] )
                    elif tag == EMBEDDED_CLAUSE_START:
                        self.clbFeatures.append( ['emb_cl_start'] )
                    elif tag == EMBEDDED_CLAUSE_END:
                        self.clbFeatures.append( ['emb_cl_end'] )
                    elif tag == CLAUSE_BOUNDARY:
                        self.clbFeatures.append (['clb'] )

        # 2) Generate the features
        estnltkWord = sentence[wid]
        # Pick the first analysis
        firstAnalysis = estnltkWord[ANALYSIS][0]
        strForm = []
        # *** ID
        strForm.append( str(wid+1) )
        strForm.append( '\t' )
        # *** FORM
        word_text = estnltkWord[TEXT]
        word_text = word_text.replace(' ', '_')
        strForm.append( word_text )
        strForm.append( '\t' )
        # *** LEMMA
        word_root = firstAnalysis[ROOT]
        word_root = word_root.replace(' ', '_')
        if len(word_root) == 0:
            word_root = "??"
        strForm.append( word_root )
        strForm.append( '\t' )
        # *** CPOSTAG
        strForm.append( firstAnalysis[POSTAG] )
        strForm.append( '\t' )
        # *** POSTAG
        finePos = firstAnalysis[POSTAG]
        if self.addAmbiguousPos and len(estnltkWord[ANALYSIS]) > 1:
            pos_tags = sorted(list(set([ a[POSTAG] for a in estnltkWord[ANALYSIS] ])))
            finePos  = '_'.join(pos_tags)
        #if self.kFeatures and wid in self.kFeatures:
        #    finePos += '_'+self.kFeatures[wid]
        strForm.append( finePos )
        strForm.append( '\t' )
        # *** FEATS  (grammatical categories)
        grammCats = []
        if len(firstAnalysis[FORM]) != 0:
            forms = firstAnalysis[FORM].split()
            grammCats.extend( forms )
        # add features from verb chains:
        if self.vcFeatures and self.vcFeatures[wid]:
            grammCats.extend( self.vcFeatures[wid] )
        # add features from clause boundaries:
        if self.addClauseBound and self.clbFeatures[wid]:
            grammCats.extend( self.clbFeatures[wid] )
        # add adposition type ("post" or "pre")
        if self.kFeatures and wid in self.kFeatures:
            grammCats.extend( [self.kFeatures[wid]] )
        # add saying verb features
        if self.sayingverbs and wid in self.sayingverbs:
            grammCats.extend( [self.sayingverbs[wid]] )
        # wrap up
        if not grammCats:
            grammCats = '_'
        else:
            grammCats = '|'.join( grammCats )
        strForm.append( grammCats )
        strForm.append( '\t' )
        return strForm

# =============================================================================
# =============================================================================
#  The set of predefined feature generators
#  (you can augment this set with your own generators to experiment with
#   different models)
# =============================================================================
# =============================================================================

feature_generators = [
{ 'flag':'--f01',  \
  'generator': MaltParser.load_default_feature_generator(), \
  'help': 'EstNLTK\'s feature generator (Default).'
},\
{ 'flag':'--f02_a', \
  'generator': CONLLFeatGenerator(parseScope='sentences'), \
  'help': 'The feature generator with settings: parseScope=sentences;'
},\
{ 'flag':'--f02_b', \
  'generator': CONLLFeatGenerator(parseScope='sentences',addAmbiguousPos=True), \
  'help': 'The feature generator with settings: parseScope=sentences, addAmbiguousPos=True;'
},\
{ 'flag':'--f03_a', \
  'generator': CONLLFeatGenerator(parseScope='sentences',addAmbiguousPos=True,addVerbcGramm=True), \
  'help': 'The feature generator with settings: parseScope=sentences, addAmbiguousPos=True, addVerbcGramm=True;',
},\
{ 'flag':'--f03_b', \
  'generator': CONLLFeatGenerator(parseScope='sentences',addAmbiguousPos=True,addVerbcGramm=True,addNomAdvVinf=True), \
  'help': 'The feature generator with settings: parseScope=sentences, addAmbiguousPos=True, addVerbcGramm=True, addNomAdvVinf=True;',
},\
{ 'flag':'--f03_c', \
  'generator': CONLLFeatGenerator(parseScope='sentences',addAmbiguousPos=True,addVerbcGramm=True,addNomAdvVinf=True, addClauseBound=True), \
  'help': 'The feature generator with settings: parseScope=sentences, addAmbiguousPos=True, addVerbcGramm=True, addNomAdvVinf=True, addClauseBound=True;',
},\
{ 'flag':'--f04', \
  'generator': CONLLFeatGenerator(parseScope='sentences',addAmbiguousPos=True,addVerbcGramm=True,addNomAdvVinf=True,addClauseBound=True,addSeSayingVerbs=True), \
  'help': 'The feature generator with settings: parseScope=sentences, addAmbiguousPos=True, addVerbcGramm=True, addNomAdvVinf=True, addClauseBound=True, addSeSayingVerbs=True;'
},\
{ 'flag':'--f05', \
  'generator': CONLLFeatGenerator(parseScope='clauses'), \
  'help': 'The feature generator with settings: parseScope=clauses;'
},\
{ 'flag':'--f06', \
  'generator': CONLLFeatGenerator(parseScope='clauses',addAmbiguousPos=True), \
  'help': 'The feature generator with settings: parseScope=clauses, addAmbiguousPos=True;'
},\
]

def add_feature_generator_arguments_to_argparser( argparser ):
    group = argparser.add_mutually_exclusive_group()
    for gen_id, generator in enumerate(feature_generators):
        group.add_argument(generator['flag'], dest='generator_id', action='store_const', const=gen_id, help=generator['help'])

def get_feature_generator( args, verbose=False ):
    args_as_dict = vars( args )
    generator_id = 0
    if 'generator_id' in args_as_dict and not args_as_dict['generator_id'] == None:
        generator_id = args_as_dict['generator_id']
    gen = feature_generators[generator_id]
    if verbose:
        print(' Using feature generator: '+str(gen['flag'])+' "'+str(gen['help'])+'"' )
    return gen['generator']

# =============================================================================
# =============================================================================
#  Converting data from estnltk JSON to CONLL
# =============================================================================
# =============================================================================

def _create_clause_based_dep_links( orig_text, layer=LAYER_CONLL ):
    '''  Rewrites dependency links in the text from sentence-based linking to clause-
        based linking: 
          *) words which have their parent outside-the-clause will become root 
             nodes (will obtain link value -1), and 
          *) words which have their parent inside-the-clause will have parent index
             according to word indices inside the clause;
         
    '''
    sent_start_index = 0
    for sent_text in orig_text.split_by( SENTENCES ):
        # 1) Create a mapping: from sentence-based dependency links to clause-based dependency links
        mapping = dict()
        cl_ind  = sent_text.clause_indices
        for wid, word in enumerate(sent_text[WORDS]):
            firstSyntaxRel = sent_text[layer][wid][PARSER_OUT][0]
            parentIndex    = firstSyntaxRel[1]
            if parentIndex != -1:
                if cl_ind[parentIndex] != cl_ind[wid]:
                    # Parent of the word is outside the current clause: make root 
                    # node from the current node 
                    mapping[wid] = -1
                else:
                    # Find the beginning of the clause 
                    clause_start = cl_ind.index( cl_ind[wid] )
                    # Find the index of parent label in the clause
                    j = 0
                    k = 0
                    while clause_start + j < len(cl_ind):
                        if clause_start + j == parentIndex:
                            break
                        if cl_ind[clause_start + j] == cl_ind[wid]:
                            k += 1
                        j += 1
                    assert clause_start + j < len(cl_ind), '(!) Parent index not found for: '+str(parentIndex)
                    mapping[wid] = k
            else:
                mapping[wid] = -1
        # 2) Overwrite old links with new ones
        for local_wid in mapping.keys():
            global_wid = sent_start_index + local_wid
            for syntax_rel in orig_text[layer][global_wid][PARSER_OUT]:
                syntax_rel[1] = mapping[local_wid]
        # 3) Advance the index for processing the next sentence
        sent_start_index += len(cl_ind)
    return orig_text


def __sort_analyses(sentence):
    ''' Sorts analysis of all the words in the sentence. 
        This is required for consistency, because by default, analyses are 
        listed in arbitrary order; '''
    for word in sentence:
        if ANALYSIS not in word:
            raise Exception( '(!) Error: no analysis found from word: '+str(word) )
        else:
            word[ANALYSIS] = sorted(word[ANALYSIS], \
                key=lambda x : "_".join( [x[ROOT],x[POSTAG],x[FORM],x[CLITIC]] ))
    return sentence


def convert_text_to_CONLL( text, feature_generator ):
    ''' Converts given estnltk Text object into CONLL format and returns as a 
        string.
        Uses given *feature_generator* to produce fields ID, FORM, LEMMA, CPOSTAG, 
        POSTAG, FEATS for each token.
        Fields to predict (HEAD, DEPREL) will be left empty.
        This method is used in preparing parsing & testing data for MaltParser.
        
        Parameters
        -----------
        text : estnltk.text.Text
            Morphologically analysed text from which the CONLL file is generated;
            
        feature_generator : CONLLFeatGenerator
            An instance of CONLLFeatGenerator, which has method *generate_features()* 
            for generating morphological features for a single token;
        
        The aimed format looks something like this:
        1	Öö	öö	S	S	sg|nom	_	xxx	_	_
        2	oli	ole	V	V	indic|impf|ps3|sg	_	xxx	_	_
        3	täiesti	täiesti	D	D	_	_	xxx	_	_
        4	tuuletu	tuuletu	A	A	sg|nom	_	xxx	_	_
        5	.	.	Z	Z	Fst	_	xxx	_	_
    '''
    from estnltk.text import Text
    if not isinstance( text, Text ):
        raise Exception('(!) Unexpected type of input argument! Expected EstNLTK\'s Text. ')
    try:
        granularity = feature_generator.parseScope
    except AttributeError:
        granularity = SENTENCES
    assert granularity in [SENTENCES, CLAUSES], '(!) Unsupported granularity: "'+str(granularity)+'"!'
    sentenceStrs = []
    for sentence_text in text.split_by( granularity ):
        sentence_text[WORDS] = __sort_analyses( sentence_text[WORDS] )
        for i in range(len( sentence_text[WORDS] )):
            # Generate features  ID, FORM, LEMMA, CPOSTAG, POSTAG, FEATS
            strForm = feature_generator.generate_features( sentence_text, i )
            # *** HEAD  (syntactic parent)
            strForm.append( '_' )
            strForm.append( '\t' )
            # *** DEPREL  (label of the syntactic relation)
            strForm.append( 'xxx' )
            strForm.append( '\t' )
            # *** PHEAD
            strForm.append( '_' )
            strForm.append( '\t' )
            # *** PDEPREL
            strForm.append( '_' )
            sentenceStrs.append( ''.join( strForm ) )
        sentenceStrs.append( '' )
    return '\n'.join( sentenceStrs )


def convert_text_w_syntax_to_CONLL( text, feature_generator, layer=LAYER_CONLL ):
    ''' Converts given estnltk Text object into CONLL format and returns as a 
        string.
        Uses given *feature_generator* to produce fields ID, FORM, LEMMA, CPOSTAG, 
        POSTAG, FEATS for each token.
        Fills fields to predict (HEAD, DEPREL) with the syntactic information from
        given *layer* (default: LAYER_CONLL).
        This method is used in preparing training data for MaltParser.
        
        Parameters
        -----------
        text : estnltk.text.Text
            Morphologically analysed text from which the CONLL file is generated;
            
        feature_generator : CONLLFeatGenerator
            An instance of CONLLFeatGenerator, which has method *generate_features()* 
            for generating morphological features for a single token;
        
        layer : str
            Name of the *text* layer from which syntactic information is to be taken.
            Defaults to LAYER_CONLL.
        
        The aimed format looks something like this:
        1	Öö	öö	S	S	sg|n	2	@SUBJ	_	_
        2	oli	ole	V	V	s	0	ROOT	_	_
        3	täiesti	täiesti	D	D	_	4	@ADVL	_	_
        4	tuuletu	tuuletu	A	A	sg|n	2	@PRD	_	_
        5	.	.	Z	Z	_	4	xxx	_	_
    '''
    from estnltk.text import Text
    if not isinstance( text, Text ):
        raise Exception('(!) Unexpected type of input argument! Expected EstNLTK\'s Text. ')
    assert layer in text, ' (!) The layer "'+layer+'" is missing form the Text object.'
    try:
        granularity = feature_generator.parseScope
    except AttributeError:
        granularity = SENTENCES
    assert granularity in [SENTENCES, CLAUSES], '(!) Unsupported granularity: "'+str(granularity)+'"!'
    sentenceStrs = []
    if granularity == CLAUSES:
        _create_clause_based_dep_links( text, layer )
    for sentence_text in text.split_by( granularity ):
        sentence_text[WORDS] = __sort_analyses( sentence_text[WORDS] )
        for i in range(len( sentence_text[WORDS] )):
            # Generate features  ID, FORM, LEMMA, CPOSTAG, POSTAG, FEATS
            strForm = feature_generator.generate_features( sentence_text, i )
            # Get syntactic analysis of the token
            syntaxToken    = sentence_text[layer][i]
            firstSyntaxRel = syntaxToken[PARSER_OUT][0]
            # *** HEAD  (syntactic parent)
            parentLabel = str( firstSyntaxRel[1] + 1 )
            strForm.append( parentLabel )
            strForm.append( '\t' )
            # *** DEPREL  (label of the syntactic relation)
            if parentLabel == '0':
                strForm.append( 'ROOT' )
                strForm.append( '\t' )
            else:
                strForm.append( firstSyntaxRel[0] )
                strForm.append( '\t' )
            # *** PHEAD
            strForm.append( '_' )
            strForm.append( '\t' )
            # *** PDEPREL
            strForm.append( '_' )
            sentenceStrs.append( ''.join( strForm ) )
        sentenceStrs.append( '' )
    return '\n'.join( sentenceStrs )


# =============================================================================
# =============================================================================
#  Converting data from CONLL to estnltk JSON
# =============================================================================
# =============================================================================

def align_CONLL_with_Text( lines, text, feature_generator, **kwargs ):
    ''' Aligns CONLL format syntactic analysis (a list of strings) with given EstNLTK's Text 
        object.
        Basically, for each word position in the Text object, finds corresponding line(s) in
        the CONLL format output;
        Returns a list of dicts, where each dict has following attributes:
          'start'   -- start index of the word in Text;
          'end'     -- end index of the word in Text;
          'sent_id' -- index of the sentence in Text, starting from 0;
          'parser_out' -- list of analyses from the output of the syntactic parser;

        Parameters
        -----------
        lines : list of str
            The input text for the pipeline; Should be the CONLL format syntactic analysis;
        text : Text
            EstNLTK Text object containing the original text that was analysed with
            MaltParser;
        feature_generator : CONLLFeatGenerator
            The instance of CONLLFeatGenerator, which was used for generating the input of 
            the MaltParser; If None, assumes a default feature-generator with the scope set
            to 'sentences';
        
        check_tokens : bool
            Optional argument specifying whether tokens should be checked for match 
            during the alignment. In case of a mismatch, an exception is raised.
            Default:False
            
        add_word_ids : bool
            Optional argument specifying whether each alignment should include attributes:
            * 'text_word_id' - current word index in the whole Text, starting from 0;
            * 'sent_word_id' - index of the current word in the sentence, starting from 0;
            Default:False
        
    ''' 
    from estnltk.text import Text
    if not isinstance( text, Text ):
        raise Exception('(!) Unexpected type of input argument! Expected EstNLTK\'s Text. ')
    if not isinstance( lines, list ):
        raise Exception('(!) Unexpected type of input argument! Expected a list of strings.')
    try:
        granularity = feature_generator.parseScope
    except (AttributeError, NameError):
        granularity = SENTENCES
    assert granularity in [SENTENCES, CLAUSES], '(!) Unsupported granularity: "'+str(granularity)+'"!'
    check_tokens = False
    add_word_ids = False
    for argName, argVal in kwargs.items() :
        if argName in ['check_tokens', 'check'] and argVal in [True, False]:
           check_tokens = argVal
        if argName in ['add_word_ids', 'word_ids'] and argVal in [True, False]:
           add_word_ids = argVal
    generalWID = 0
    sentenceID = 0
    # Collect clause indices for each sentence (if required)
    clause_indices = None
    if granularity == CLAUSES:
        c = 0
        all_clause_indices = text.clause_indices
        clause_indices = []
        for sentence_words in text.divide( layer=WORDS, by=SENTENCES ):
            clause_indices.append([])
            for wid, estnltkToken in enumerate( sentence_words ):
                clause_indices[-1].append( all_clause_indices[c] )
                c += 1
    # Iterate over the sentences and perform the alignment
    results = []
    j = 0
    for sentence_words in text.divide( layer=WORDS, by=SENTENCES ):
        tokens_to_collect = len( sentence_words )
        tokens_collected  = 0
        chunks      = [[]]
        while j < len(lines):
            maltparserToken = lines[j]
            if len( maltparserToken ) > 1 and '\t' in maltparserToken:
                # extend the existing clause chunk
                token_dict = { 't':maltparserToken, \
                               'w':(maltparserToken.split('\t'))[1] }
                chunks[-1].append( token_dict )
                tokens_collected += 1
            else:
                # create a new clause chunk
                if len(chunks[-1]) != 0:
                    chunks.append( [] )
            j += 1
            if tokens_to_collect == tokens_collected:
                break
        if tokens_to_collect != tokens_collected:  # a sanity check 
            raise Exception('(!) Unable to collect the following sentence from the output of MaltParser: "'+\
                                 str(sentence_words)+'"')
        # 2) Put the sentence back together
        if granularity == SENTENCES:
            # A. The easy case: sentence-wise splitting was used
            for wid, estnltkToken in enumerate( sentence_words ):
                maltparserToken = chunks[0][wid]['t']
                if check_tokens and estnltkToken[TEXT] != chunks[0][wid]['w']:
                    raise Exception("(!) A misalignment between Text and CONLL: ",\
                                    estnltkToken, maltparserToken )
                # Populate the alignment
                result_dict = { START:estnltkToken[START], END:estnltkToken[END], \
                                SENT_ID:sentenceID, PARSER_OUT: [maltparserToken] }
                if add_word_ids:
                    result_dict['text_word_id'] = generalWID # word id in the text
                    result_dict['sent_word_id'] = wid        # word id in the sentence
                results.append( result_dict )
                generalWID += 1
        elif granularity == CLAUSES:
            # B. The tricky case: clause-wise splitting was used
            results_by_wid = {}
            # B.1  Try to find the location of each chunk in the original text
            cl_ind = clause_indices[sentenceID]
            for chunk_id, chunk in enumerate(chunks):
                firstWord = chunk[0]['w']
                chunkLen  = len(chunk)
                estnltk_token_ids = []
                seen_clause_ids   = {}
                for wid, estnltkToken in enumerate( sentence_words ):
                    # Try to recollect tokens of the clause starting from location wid
                    if estnltkToken[TEXT] == firstWord and \
                       wid+chunkLen <= len(sentence_words) and cl_ind[wid] not in seen_clause_ids:
                        clause_index = cl_ind[wid]
                        i = wid
                        while i < len(sentence_words):
                            if cl_ind[i] == clause_index:
                                estnltk_token_ids.append( i )
                            i += 1
                    # Remember that we have already seen this clause 
                    # (in order to avoid start collecting from the middle of the clause)
                    seen_clause_ids[cl_ind[wid]] = 1
                    if len(estnltk_token_ids) == chunkLen:
                        break
                    else:
                        estnltk_token_ids = []
                if len(estnltk_token_ids) == chunkLen:
                    # Align the CONLL clause with the clause from the original estnltk Text
                    for wid, estnltk_wid in enumerate(estnltk_token_ids):
                        estnltkToken    = sentence_words[estnltk_wid]
                        maltparserToken = chunk[wid]['t']
                        if check_tokens and estnltkToken[TEXT] != chunk[wid]['w']:
                            raise Exception("(!) A misalignment between Text and CONLL: ",\
                                                 estnltkToken, maltparserToken )
                        # Convert indices: from clause indices to sentence indices
                        tokenFields = maltparserToken.split('\t')
                        if tokenFields[6] != '0':
                            in_clause_index = int(tokenFields[6])-1
                            assert in_clause_index in range(0, len(estnltk_token_ids)), \
                                   '(!) Unexpected clause index from CONLL: '+str(in_clause_index)+\
                                   ' \ '+str(len(estnltk_token_ids))
                            in_sent_index   = estnltk_token_ids[in_clause_index]+1
                            tokenFields[6]  = str(in_sent_index)
                        tokenFields[0] = str(estnltk_wid+1)
                        maltparserToken = '\t'.join(tokenFields)
                        # Populate the alignment
                        result_dict = { START:estnltkToken[START], END:estnltkToken[END], \
                                        SENT_ID:sentenceID, PARSER_OUT: [maltparserToken] }
                        results_by_wid[estnltk_wid] = result_dict
                else:
                    raise Exception('(!) Unable to locate the clause in the original input: '+str(chunk))
            if len(results_by_wid.keys()) != len(sentence_words):
                raise Exception('(!) Error in aligning Text and CONLL - token counts not matching:'+\
                                str(len(results_by_wid.keys()))+ ' vs '+str(len(sentence_words)) )
            # B.2  Put the sentence back together
            for wid in sorted(results_by_wid.keys()):
                if add_word_ids:
                    results_by_wid[wid]['text_word_id'] = generalWID # word id in the text
                    results_by_wid[wid]['sent_word_id'] = wid        # word id in the sentence
                results.append( results_by_wid[wid] )
                generalWID += 1
        sentenceID += 1
    return results


# =============================================================================
#  Verb chain features
# =============================================================================

def generate_verb_chain_features( sentence_text, addGrammPred=True, addNomAdvVinf=True ):
    if not sentence_text.is_tagged(VERB_CHAINS):
        sentence_text.tag_verb_chains()
    word_features = [[] for word in sentence_text[WORDS]]
    for vc in sentence_text[VERB_CHAINS]:
        if len( vc['phrase'] ) > 1:
            if addGrammPred:
                # Features marking multiword grammatical predicates:
                #  ** negation;
                #  ** composite tenses;
                #  ** modals & phasal verbs & other auxiliaries
                for vid, (wid, pat, root) in enumerate(zip(vc['phrase'],vc['pattern'],vc['roots'])):
                    if pat in ['ega', 'ei', 'ära']:
                        word_features[wid].append('neg_aux')
                        word_features[vc['phrase'][vid+1]].append('comp_main')
                    if vid == 0:
                        if root in ['saa', 'pida', 'või', 'näi', 'paist', 'tundu', 'tohti']:
                            if 'V_' in vc['morph'][vid+1]:
                                word_features[wid].append('aux')
                                word_features[vc['phrase'][vid+1]].append('comp_main')
                        if root in ['hakka', 'asu', 'jää']:
                            if 'V_' in vc['morph'][vid+1]:
                                word_features[vc['phrase'][vid+1]].append('comp_main')
                        if root in ['ole', 'pole']:
                            if 'V_' in vc['morph'][vid+1]:
                                word_features[wid].append('aux')
                            if 'V_nud' in vc['morph'][vid+1]:
                                word_features[vc['phrase'][vid+1]].append('comp_tense')
            if addNomAdvVinf:
                # Features marking nom/adv + vinf relations inside a verb chain:
                #   andma + aega + Vda       :  [andsime] talle [aega] järele [mõelda]
                #   leidma + võimalust + Vda :  Nad ei [leidnud] [võimalust] tööd [lõpetada]
                #   puuduma + mõte + Vda     :  [puudub] ju [mõte] [osta] kallis auto 
                if 'nom/adv' in vc['pattern']:
                    for vid, (wid, pat, root) in enumerate(zip(vc['phrase'],vc['pattern'],vc['roots'])):
                        # Note: we skip 'olema'-centric chains, as relations within these chains may
                        #       not be systematized in the training data ...
                        if pat == 'nom/adv' and not vc['pattern'][vid-1] in ['ole', 'pole']:
                            word_features[wid].append('nom_adv')
                            if vid-1 > -1:
                                word_features[vc['phrase'][vid-1]].append('parent_nom_adv')
                            if vid+1 < len(vc['phrase']):
                                word_features[vc['phrase'][vid+1]].append('vinf_nom_adv')
                                if vid+3 < len(vc['phrase']) and vc['phrase'][vid+2]=='&':
                                    word_features[vc['phrase'][vid+3]].append('vinf_nom_adv')
    return word_features

# =============================================================================
#  Sentence ending saying-verbs
# =============================================================================

def _get_clause_words( sentence_text, clause_id ):
    ''' Collects clause with index *clause_id* from given *sentence_text*.
        Returns a pair (clause, isEmbedded), where:
         *clause* is a list of word tokens in the clause;
         *isEmbedded* is a bool indicating whether the clause is embedded;
    '''
    clause = []
    isEmbedded = False
    indices = sentence_text.clause_indices
    clause_anno = sentence_text.clause_annotations
    for wid, token in enumerate(sentence_text[WORDS]):
        if indices[wid] == clause_id:
            if not clause and clause_anno[wid] == EMBEDDED_CLAUSE_START:
                isEmbedded = True
            clause.append((wid, token))
    return clause, isEmbedded

_pat_starting_quote = re.compile("^[\"\u00AB\u02EE\u030B\u201C\u201D\u201E].*$")
_pat_ending_quote   = re.compile("^.*[\"\u00BB\u02EE\u030B\u201C\u201D\u201E]$")

def _detect_quotes( sentence_text, wid, fromRight = True ):
    ''' Searches for quotation marks (both opening and closing) closest to 
        given location in sentence (given as word index *wid*);
        
        If *fromRight == True* (default), searches from the right (all the 
        words having index greater than *wid*), otherwise, searches from the 
        left (all the words having index smaller than *wid*);
        
        Returns index of the closest quotation mark found, or -1, if none was
        found;
    '''
    i = wid
    while (i > -1 and i < len(sentence_text[WORDS])):
        token = sentence_text[WORDS][i]
        if _pat_starting_quote.match(token[TEXT]) or \
           _pat_ending_quote.match(token[TEXT]):
            return i
        i += 1 if fromRight else -1
    return -1

from estnltk.mw_verbs.utils import WordTemplate

def detect_sentence_ending_saying_verbs( edt_sent_text ):
    ''' Detects cases where a saying verb (potential root of the sentence) ends the sentence.

        We use a simple heuristic: if the given sentence has multiple clauses, and the last main 
        verb in the sentence is preceded by ", but is not followed by ", then the main verb is 
        most likely a saying verb.
        
        Examples:
            " See oli ainult unes , " [vaidles] Jan .
            " Ma ei maga enam Joogaga ! " [protesteerisin] .
            " Mis mõttega te jama suust välja ajate ? " [läks] Janil nüüd juba hari punaseks .
            
        Note that the class of saying verbs is open, so we try not rely on a listing of verbs,
        but rather on the conventional usage patterns of reported speech, indicated by quotation 
        marks.
        
        Returns a dict containing word indexes of saying verbs;
    '''
    if not edt_sent_text.is_tagged( VERB_CHAINS ):
        edt_sent_text.tag_verb_chains()

    saying_verbs = {}
    if len(edt_sent_text[VERB_CHAINS]) < 2:
        # Skip sentences that do not have any chains, or 
        #                have only a single verb chain
        return saying_verbs

    patColon = WordTemplate({'partofspeech':'^[Z]$', 'text': '^:$'})
        
    for vid, vc in enumerate( edt_sent_text[VERB_CHAINS] ):
        #  
        #  Look only multi-clause sentences, where the last verb chain has length 1
        # 
        if len(vc['phrase']) == 1 and vid == len(edt_sent_text[VERB_CHAINS])-1:
            wid   = vc['phrase'][0]
            token = edt_sent_text[WORDS][wid]
            clause_id = vc[CLAUSE_IDX]
            # Find corresponding clause and locations of quotation marks
            clause, insideEmbeddedCl = _get_clause_words( edt_sent_text, clause_id )
            quoteLeft  = _detect_quotes( edt_sent_text, wid, fromRight = False )
            quoteRight = _detect_quotes( edt_sent_text, wid, fromRight = True )
            #
            #  Exclude cases, where there are double quotes within the same clause:
            #     ... ootab igaüks ,] [kuidas aga kähku tagasi " varrastusse " <saaks> .]
            #     ... miljonäre on ka nende seas ,] [kes oma “ papi ” mustas äris <teenivad>  .]
            #
            quotes_in_clause = []
            for (wid2, token2) in clause:
                if _pat_starting_quote.match(token2[TEXT]) or \
                    _pat_ending_quote.match(token2[TEXT]):
                    quotes_in_clause.append(wid2)
            multipleQuotes = len(quotes_in_clause) > 1 and quotes_in_clause[-1]==quoteLeft
            #    
            #  If the preceding double quotes are not within the same clause, and
            #     the verb is not within an embedded clause, and a quotation mark strictly
            #     precedes, but none follows, then we have most likely a saying verb:
            #         " Ma ei tea , " [kehitan] õlga .
            #         " Miks jumal meid karistab ? " [mõtles] sir Galahad .
            #         " Kaarsild pole teatavastki elusolend , " [lõpetasin] arutelu .
            #
            if not multipleQuotes and \
               not insideEmbeddedCl and \
               (quoteLeft != -1 and quoteLeft+1 == wid and quoteRight == -1):
                saying_verbs[wid] = 'se_saying_verb'
    return saying_verbs

