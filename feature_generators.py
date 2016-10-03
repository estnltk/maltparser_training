# -*- coding: utf-8 -*- 
#

from __future__ import unicode_literals, print_function
from estnltk.names import *

from estnltk.core import PACKAGE_PATH
from estnltk.syntax.maltparser_support import _loadKSubcatRelations, _findKsubcatFeatures

from estnltk.syntax.parsers import MaltParser
from estnltk.syntax.maltparser_support import CONLLFeatGenerator as EstNLTKCONLLFeatGenerator

import re, json
import os, os.path
import codecs
import tempfile
import subprocess

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
                Default: True
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
       '''
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
{ 'flag':'--f02', \
  'generator': CONLLFeatGenerator(), \
  'help': 'The feature generator with default settings.'
},\
{ 'flag':'--f03', \
  'generator': CONLLFeatGenerator(addAmbiguousPos=True,addVerbcGramm=True), \
  'help': 'The feature generator with settings: addAmbiguousPos=True, addVerbcGramm=True;'
},\
{ 'flag':'--f04', \
  'generator': CONLLFeatGenerator(addAmbiguousPos=True,addVerbcGramm=True,addNomAdvVinf=True,addClauseBound=True,addSeSayingVerbs=True), \
  'help': 'The feature generator with settings: addAmbiguousPos=True, addVerbcGramm=True, addNomAdvVinf=True, addClauseBound=True, addSeSayingVerbs=True;'
}
]

def add_feature_generator_arguments_to_argparser( argparser ):
    group = argparser.add_mutually_exclusive_group()
    for gen_id, generator in enumerate(feature_generators):
        group.add_argument(generator['flag'], dest='generator_id', action='store_const', const=gen_id, help=generator['help'])

def get_feature_generator( args, verbose=False ):
    args_as_dict = vars( args )
    generator_id = 0
    if 'generator_id' in args_as_dict:
        generator_id = args_as_dict['generator_id']
    gen = feature_generators[generator_id]
    if verbose:
        print(' Using feature generator: '+str(gen['flag'])+' "'+str(gen['help'])+'"' )
    return gen['generator']


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

