# -*- coding: utf-8 -*- 
#
#     What: 
#        ad hoc fixes for syntactically annotated data to ensure validity of the data (no cycles);
#     Why: 
#        because its tedious to manually fix these things every time a dataset with new features is generated;
#
#
from __future__ import unicode_literals, print_function

import re, json
import os, os.path
import codecs, sys

from pprint import pprint 

from estnltk.names import *
from estnltk import Text


def repair_cycles( text, ud_sent, layer = LAYER_CONLL ):
    ''' An ad hoc method for repairing cycles. Addresses only specific cases:
         1) Two consecutive tokens point to each other and form a cycle;
         2) Specific sentences that are known to contain cycles;
    '''
    sentence_text = ' '.join( ud_sent[1] )
    for wid, token in enumerate( text[layer] ):
        last_token = text[layer][wid-1] if wid-1 > -1 else None
        # 1) Two consecutive tokens that point to each other and form a cycle:
        this_analysis = token[PARSER_OUT][0]
        last_analysis = last_token[PARSER_OUT][0] if last_token else None
        has_next = wid+1<len(text[layer]) and text[layer][wid+1][SENT_ID] == token[SENT_ID]
        if this_analysis and last_analysis:
            if this_analysis[1]==wid-1 and last_analysis[1]==wid:
                print ( '(!) Cycle detected in consecutive tokens: \n  '+str(last_token)+'\n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    if has_next:
                        # Make it point to the next token
                        analysis[1] = wid+1
                    else:
                        # Make it ROOT
                        analysis[1] = -1
                    token[PARSER_OUT][aid] = analysis
        # 2) (Ad hoc) Specific sentences that are known to contain cycles:
        if 'Su nimi sai kuulsaks paganate hulgas' in sentence_text and len(ud_sent[1])==29:
            if wid == 24 and this_analysis[1] == 28:
                print ( '(~) Addressing a known cycle #1: \n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    analysis[1] = wid+1
                    token[PARSER_OUT][aid] = analysis
        if 'Gradstein ja Milanovic , 2002' in sentence_text and len(ud_sent[1])==47:
            if wid == 42 and this_analysis[1] == 43:
                print ( '(~) Addressing a known cycle #2: \n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    analysis[1] = wid-2
                    token[PARSER_OUT][aid] = analysis
        if 'Teadusministeeriumi esindajaks CALIBRATE projektis' in sentence_text and len(ud_sent[1])==14:
            if wid == 1 and this_analysis[1] == 4:
                print ( '(~) Addressing a known cycle #3: \n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    analysis[1] = wid+2
                    token[PARSER_OUT][aid] = analysis
            if wid == 3 and this_analysis[1] == 1:
                print ( '(~) Addressing a known cycle #3: \n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    analysis[1] = wid+1
                    token[PARSER_OUT][aid] = analysis
            if wid == 4 and this_analysis[1] == 5:
                print ( '(~) Addressing a known cycle #3: \n  '+str(token) )
                for aid, analysis in enumerate( token[PARSER_OUT] ):
                    analysis[1] = 10
                    token[PARSER_OUT][aid] = analysis

