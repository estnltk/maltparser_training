
Training MaltParser models for EstNLTK
======================================

This repository contains scripts necessary for preparing data for EstNLTK's MaltParser's models, and for training and evaluating the models. 
Here, various models are experimented with, and once the best model is found, it is to be merged back to EstNLTK as the default MaltParser model.

Prerequisites
--------------

Download and unpack the following Java based tools:

   * MaltParser (ver 1.8): <http://www.maltparser.org/download.html>
   * MaltOptimizer (ver 1.0.3): <http://nil.fdi.ucm.es/maltoptimizer/download.html>
   * MaltEval: <http://www.maltparser.org/malteval.html>

Download and unpack the following annotated corpora:

   * "The Estonian UD treebank": <https://github.com/UniversalDependencies/UD_Estonian>
   * "Estonian Dependency Treebank": <https://github.com/EstSyntax/EDT>

Download and install EstNLTK (ver 1.4+) with Python 3.4.x:

   * Most scripts in this repository have been developed and tested with Python 3.4.x (so compatibility with version 2.7.x is not guaranteed);
   * In order to use these scripts, you need to install the latest development version of EstNLTK that includes the improved syntactic parsing interface.
   For that, clone the repository, checkout the development commit [cebee219231ac8b404e3a5fb99aded802e32954f](https://github.com/estnltk/estnltk/tree/cebee219231ac8b404e3a5fb99aded802e32954f) (or any following commit under the version 1.4), and install the development version of EstNLTK;

<!-- TODO: it should point to a stable version, if finally available -->

Building models that use EstCG tagset
--------------------------------------

EstCG tagset is the tagset used by the Estonian Constraint Grammar parser (<https://github.com/EstSyntax/EstCG>), and "Estonian Dependency Treebank" is also annotated following this tagset. A brief description of the tagset can be found here: <https://korpused.keeleressursid.ee/syntaks/dokumendid/syntaksiliides_en.pdf>

### Preparing data

Our routine:  following the data split introduced in "The Estonian UD treebank", we split the data into three subsets: **training** data, **development** data (for optimizing models), and **test** data (for final evaluation);
However, because "The Estonian UD treebank" does not use the EstCG format, we cannot directly use the data from "The Estonian UD treebank". Instead, we take syntactically annotated sentences from "Estonian Dependency Treebank", and, in order to get  the correct splits, align them with the sentences from "The Estonian UD treebank". This ensures that our experiments using the EstCG tagset are roughly comparable with the experiments using the UD (Universal Dependencies) tagset.

#### Aligning a single file from UD_Estonian

The script `align_ud_corpus_with_edt_corpus.py` takes two arguments `<CONLL_file>` and `<EDT_corpus_dir>`, extracts all the sentences from `*.inforem` files in `<EDT_corpus_dir>` that are also contained in `<CONLL_file>` (aligns sentences using the sentence indices from `<CONLL_file>`), converts the extracted sentences into CONLL format (the conversion includes some *ad hoc* fixes and the feature extraction), and rewrites the newly formatted sentences into a new file. 

The script creates two output files: both files have the same base name as the input file `<CONLL_file>`, but different extensions. The first file has extension `.cg3-conll` and contains all the extracted sentences in CONLL format, and the second file has extension `.sent_ids` and it contains all indices of the extracted sentences, exactly in the same order as sentences in the file with the extension `.cg3-conll`.

The following usage examples assume that the working directory contains subdirs `UD_Estonian-master` (files from "Estonian UD treebank"), and `EDT` (files from "Estonian Dependency Treebank").

Preparing the *training data* :

    python align_ud_corpus_with_edt_corpus.py UD_Estonian-master\et-ud-train.conllu EDT

Preparing the *development data*:

    python align_ud_corpus_with_edt_corpus.py UD_Estonian-master\et-ud-dev.conllu EDT

Preparing the *evaluation data*:

    python align_ud_corpus_with_edt_corpus.py UD_Estonian-master\et-ud-test.conllu EDT

Notes:

  * The alignment will not be obtain 100% coverage, as "The Estonian UD treebank" contains sentences (the Arborest sentences) that are not part of the "Estonian Dependency Treebank". However, the number of missing sentences is relatively small:  in terms of token counts, the resulting `.cg3-conll` files are only approx. 4% smaller than the original `.conllu` files.
  
  * "Estonian Dependency Treebank" currently available at github also misses one newspaper article file: `aja_EPL_2006_12_16.tasak.inforem`; This file is available from an internal repository, please contact the authors to obtain it.

#### Creating the large training set

Currently, "Estonian Dependency Treebank" is much larger than "Estonian UD treebank", so, instead of using the small training set `et-ud-train.cg3-conll`, you can also opt for using all the sentences, excluding only the sentences from `et-ud-dev.conllu` and `et-ud-test.conllu`.

The script `get_edt_corpus_diff_from_ud_corpus.py` takes `<EDT_corpus_dir>` and a list of CONLL file names (`<CONLL_file1>`, `<CONLL_file2>`, `...`) as input arguments, finds all the sentences from `<EDT_corpus_dir>` that are also in the CONLL files (aligns sentences using the sentence indices from `<CONLL_file>`), extracts sentences from `<EDT_corpus_dir>` that were left unaligned in the previous phase, converts the extracted sentences into CONLL format (the conversion includes some *ad hoc* fixes and the feature extraction), and rewrites the newly formatted sentences into a new file.

The script creates two output files: the file `et-train-diff.cg3-conll` containing all the extracted sentences in CONLL format, and the file `et-train-diff.sent_ids` containing all indices of the extracted sentences, exactly in the same order as sentences in the file with the extension `.cg3-conll`.

Usage example. Preparing the large *training set* -- taking all sentences from `EDT`, except the sentences that are also in files `et-ud-dev.conllu` and `et-ud-test.conllu`:

    python get_edt_corpus_diff_from_ud_corpus.py UD_Estonian-master\et-ud-dev.conllu UD_Estonian-master\et-ud-test.conllu EDT

#### Different feature generation models

Scripts that prepare the data ( `align_ud_corpus_with_edt_corpus.py` and `get_edt_corpus_diff_from_ud_corpus.py` ) can be executed with different feature generation models. A feature generation model guides, how fields `ID`, `FORM`, `LEMMA`, `CPOSTAG`, `POSTAG`, `FEATS` (of a token) are populated. You can use flags `--f01` , `--f02` , `--f03` , `...` to switch between different models (the model `f01` is used by default). A brief information about the models is available when executing the script with the flag `-h`, e.g.:

    python align_ud_corpus_with_edt_corpus.py -h

More technically, available feature generation models are stored in the module `feature_generators.py`. The class `CONLLFeatGenerator` encapsulates the logic. It can be initialized with different flags, specifying the details about which features should be enabled/disabled. You can augment the class with new logic to experiment with your own features.
Note that `CONLLFeatGenerator` in `feature_generators.py` mirrors `estnltk.syntax.maltparser_support.CONLLFeatGenerator` in EstNLTK, so if you update the local `CONLLFeatGenerator` and find a better model which you want to contribute to EstNLTK, please make sure you also update the logic in corresponding EstNLTK's generator class.      

The variable named `feature_generators` (in `feature_generators.py`) lists the available instances of `CONLLFeatGenerator`. If you want to experiment with new models, you should add these to the list to make them available  in the data preparation scripts.  

### Optimization

Optimization uses `MaltOptimizer.jar` and `et-ud-dev.cg3-conll` dataset for finding the best parsing/learning algorithm and the feature model. Once the  *development data set* has been prepared (and is located in a subdir `UD_Estonian-master`), execute the following commands in a row:

    java -jar MaltOptimizer.jar -p 1 -m maltparser-1.8.jar -c UD_Estonian-master\et-ud-dev.cg3-conll

    java -jar MaltOptimizer.jar -p 2 -m maltparser-1.8.jar -c UD_Estonian-master\et-ud-dev.cg3-conll

    java -jar MaltOptimizer.jar -p 3 -m maltparser-1.8.jar -c UD_Estonian-master\et-ud-dev.cg3-conll

Notes:

 * `MaltOptimizer.jar` (ver 1.0.3) uses script `validateFormat.py` that seems to be compatible only with Python 2.7.* (or with versions older than 3.*); If you are using a newer version as a default, you have to change it to an older version in order to get the validation script working (e.g. by adding the directory of python2.7 to the beginning of `PATH` environment variable);
 
 * If the validation script detects some cycles, you should fix these in order to get through the automatic optimization process (otherwise, some of the algorithms may fail with an error). A temporary soultion employed here is to add the logic of fixing to the script `adhoc_fixes.py`, so it will be automatically re-applied each time the dataset is generated; 

 * You may have to increase the Java memory heap size, e.g. by adding flags `-Xmx2048M` or `-Xmx5048M` to the java command (it is advisable to use 64bit Java VM; when using 32bit VM, consider the [possible limitations of setting maximum heap size](http://www.oracle.com/technetwork/java/hotspotfaq-138619.html#gc_heap_32bit));

After the final optimization step (`-p 3`), the MaltOptimizer [produces](http://nil.fdi.ucm.es/maltoptimizer/userguide.html) a *final configuration file* (`finalOptionsFile.xml`) and a file containing suggested options (`phase3_optFile.txt`), which also contains option `feature_model (-F)`, pointing to *the feature model XML file*. These two file names will also be passed as parameters in training of the MaltParser.

### Training & evaluation (combined)

The script `train_and_test_maltparser.py` trains a MaltParser model on *training data set*, and after the training, evaluates it on *test data set*, and reports the accuracy. Command line flags can be used to specify details of the process:

 * `--n <model_name>` -- specifies name of the model (Default: `estnltkECG`);
 * `--m <maltparser_jar>`-- specifies MaltParser's jar file to be used in training/evaluation (Default: `maltparser-1.8.jar`);
 *  `--j <java_heap_size>`-- Java heap size argument used in executing Java commands (Default: `-Xmx5048M`);
 * `--in <train_corpus>` -- Training corpus CONLL file (Default: `UD_Estonian-master\et-ud-train.cg3-conll`);
 * `--g <test_corpus>` -- Test corpus CONLL file (Default: `UD_Estonian-master\et-ud-test.cg3-conll`);
 * `--F <finalOptionsFile>` -- *final configuration file* (`finalOptionsFile.xml`) with path (Default: `None`);
 * `--f <feature_model_file>` --  *feature model XML file* with path (Default: `None`);

The script needs to be executed in a directory that contains `MaltEval.jar`, and also `maltparser-1.8.jar`, alternatively, MaltParser Jar file can be specified via command line argument `--m`.
 
Example: training MaltParser on the training set with the final configuration from `maltoptimizer-1.0.3\malt-opt-results-1-w-cv\finalOptionsFile.xml`, feature model from file `maltoptimizer-1.0.3\malt-opt-results-1-w-cv\addInputFEATS0.xml`, naming the model to `estnltkECG-1` and evaluating it on the test set:

    python train_and_test_maltparser.py -F maltoptimizer-1.0.3\malt-opt-results-1-w-cv\finalOptionsFile.xml -f maltoptimizer-1.0.3\malt-opt-results-1-w-cv\addInputFEATS0.xml -n estnltkECG-1

Note that if training and test set names are not specified in the command line arguments, like in the previous example, default locations are assumed (`UD_Estonian-master\et-ud-train.cg3-conll` for training, and `UD_Estonian-master\et-ud-test.cg3-conll` for evaluation).

In the evaluation part, the script reports accuracy in terms of three metrics: *LA*, *UAS* and *LAS*.

### Evaluation 

#### Evaluating MaltParser's models

The script `test_maltparser.py` can be used to evaluate the performance of an existing MaltParser's model on the *test set*:

    python test_maltparser.py -n estnltkECG-1

The argument `--n <model_name>` specifies name of the model to be evaluated. Name of the test corpus can be changed with the argument `--g <test_corpus>` (Defaults to `UD_Estonian-master\et-ud-test.cg3-conll`);

The script reports accuracy in terms of three metrics: *LA*, *UAS* and *LAS*.

#### Evaluating EstNLTK's VISLCG3-based parser

If VISLCG3 is installed into the system, the script `test_estnltk_vislcg3.py` can be used to evaluate EstNLTK's `VISLCG3Parser`'s current performance on the given *test set*:

    python test_estnltk_vislcg3.py -visl C:\cg3\bin\vislcg3


The argument `-visl <vislcg3_cmd>` specifies full path to the VISLCG3 executable (including the name of the executable). If not provided, it is assumed that the executable can be accessed via `PATH` environment variable. Name of the test corpus can be changed with the argument `--g <test_corpus>` (Defaults to `UD_Estonian-master\et-ud-test.cg3-conll`);

Note that this script evaluates `VISLCG3Parser` with its default configuration. For a more specific evaluation (e.g. changing the pipeline or preprocessing settings), you'll need to modify the script accordingly.

<!-- #### Evaluation results (so far) -->

<!-- TODO -->

