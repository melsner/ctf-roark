/**
 * 
 */
package edu.berkeley.nlp.PCFGLA;

import java.lang.Math;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.io.PrintStream;
import java.io.IOException;
import java.util.zip.GZIPOutputStream;
import java.util.List;
import java.util.LinkedList;
import java.util.Map;
import java.util.HashMap;

import edu.berkeley.nlp.PCFGLA.Corpus.TreeBankType;
import edu.berkeley.nlp.PCFGLA.Corpus;
import edu.berkeley.nlp.ling.StateSet;
import edu.berkeley.nlp.ling.Tree;
import edu.berkeley.nlp.ling.Trees.PennTreeReader;
import edu.berkeley.nlp.util.Numberer;
import edu.berkeley.nlp.util.Option;
import edu.berkeley.nlp.util.OptionParser;
import edu.berkeley.nlp.util.CounterMap;
import edu.berkeley.nlp.util.Counter;

import edu.berkeley.nlp.util.ScalingTools;

class WordAndPos
{
	public String word;
	public String pos;

	public String toString()
	{
		return pos + "-" + word;
	}

	public WordAndPos(String ww, String pp)
	{
		word = ww;
		pos = pp;
	}

	public int hashCode()
	{
		return word.hashCode() + 1000 * pos.hashCode();
	}

	public boolean equals(Object o)
	{
		WordAndPos other = (WordAndPos)o;
		if(other == null)
		{
			return false;
		}
		return word == other.word && pos == other.pos;
	}
}

public class LeftCornerProbs
{
	Grammar grammar;
	SophisticatedLexicon lexicon;
	ArrayParser labeler;
	Numberer tagNumberer;
	Binarization binarization;

	Map<String, CounterMap<Short, WordAndPos>> wordAndPosProbs;
	Map<String, CounterMap<Short, String>> posProbs;
	Map<String, CounterMap<Short, String>> wordProbs;
	CounterMap<String, String> posToWord;
	Map<String, Double> lambdas;

	public static class Options {		
		@Option(name = "-gr", required = true, usage = "Input File for Grammar (Required)\n")
		public String inFileName;

//		@Option(name = "-labelLevel", usage = "Parse with projected grammar from this level (yielding 2^level substates) (Default: -1 = input grammar)")
//		public int labelLevel = -1;

		@Option(name = "-inputFile", usage = "Read input from this file instead of reading it from STDIN.")
		public String inputFile;

		@Option(name = "-validation", usage = "Read validation trees from this file.")
		public String validation;

		@Option(name="-out", usage="Stem of filename for output files.")
		public String outName;
	}

	public LeftCornerProbs(Grammar grammar, SophisticatedLexicon lexicon,
						   int labelLevel, Binarization bin) 
	{
		lambdas = new HashMap<String, Double>();
		wordAndPosProbs = new HashMap<String, CounterMap<Short, WordAndPos>>();
		posProbs = new HashMap<String, CounterMap<Short, String>>();
		wordProbs = new HashMap<String, CounterMap<Short, String>>();
		posToWord = new CounterMap<String, String>();

		if (labelLevel==-1)
		{
			this.grammar = grammar.copyGrammar(false);
			this.lexicon = lexicon.copyLexicon();
		} 
		else
		{ // need to project
			int[][] fromMapping = grammar.computeMapping(1);
			int[][] toSubstateMapping = 
				grammar.computeSubstateMapping(labelLevel);
			int[][] toMapping = 
				grammar.computeToMapping(labelLevel,toSubstateMapping);
			double[] condProbs = 
				grammar.computeConditionalProbabilities(fromMapping,toMapping);
    	
			this.grammar = 
				grammar.projectGrammar(condProbs,
									   fromMapping,toSubstateMapping);
			this.lexicon = 
				lexicon.projectLexicon(condProbs,
									   fromMapping,toSubstateMapping);
			this.grammar.splitRules();
			double filter = 1.0e-10;
			this.grammar.removeUnlikelyRules(filter,1.0);
			this.lexicon.removeUnlikelyTags(filter,1.0);
		}
		this.labeler = new ArrayParser(this.grammar, this.lexicon);
		this.tagNumberer = Numberer.getGlobalNumberer("tags");
		this.binarization = bin;
	}

	private void record(Tree<StateSet> stateSetTree)
	{
		try
		{
			labeler.doInsideOutsideScores(stateSetTree, false, false);
		}
		catch(Exception e)
		{
			System.err.println("Fail: "+stateSetTree);
			System.err.println(e);
			throw new RuntimeException(e);
		}

//		System.err.println(stateSetTree);

		double sentenceScore = stateSetTree.getLabel().getIScore(0);
		int sentenceScale = stateSetTree.getLabel().getIScale();

		addTreeCounts(stateSetTree, sentenceScore, sentenceScale);
	}

	private void addTreeCounts(Tree<StateSet> tree, double sentenceScore, 
							   int sentenceScale)
	{
		List<Tree<StateSet>> children = tree.getChildren();

		if(tree.isLeaf())
		{
			return;
		}
		else if(tree.isPreTerminal())
		{
			StateSet currentState = tree.getLabel();
 			int nSubStates = currentState.numSubStates();
 			short tag = currentState.getState();

			String word = tree.getChildren().get(0).getLabel().getWord();

			if(!lexicon.isKnown(word))
			{
				word = lexicon.getSignature(word, currentState.from);
			}

			String label = 
				(String)Numberer.getGlobalNumberer("tags").object(tag);

			//System.err.println(tree+" "+label+" "+word);
  		
 			double norm = 0;

 			for (short substate=0; substate<nSubStates; substate++) 
 			{
				double score = currentState.getOScore(substate) *
					currentState.getIScore(substate);

				double scalingFactor = 
					ScalingTools.calcScaleFactor(currentState.getOScale() +
												 currentState.getIScale() - 
												 sentenceScale);

				double weight = score * scalingFactor;

				norm += weight;

				if(wordAndPosProbs.get(label) == null)
				{
					wordAndPosProbs.put(label, 
										new CounterMap<Short, WordAndPos>());
				}
				CounterMap<Short, WordAndPos> submap = 
					wordAndPosProbs.get(label);
				submap.incrementCount(substate, new WordAndPos(word, label),
									  weight);

				if(posProbs.get(label) == null)
				{
					posProbs.put(label, new CounterMap<Short, String>());
				}
				CounterMap<Short, String> posSubmap = posProbs.get(label);
				posSubmap.incrementCount(substate, label, weight);

				if(wordProbs.get(label) == null)
				{
					wordProbs.put(label, new CounterMap<Short, String>());
				}
				CounterMap<Short, String> wordSubmap = wordProbs.get(label);
				wordSubmap.incrementCount(substate, word, weight);
 			}

			//POS tags are fully observed...
			posToWord.incrementCount(label, word, 1.0);

			if(Math.abs(sentenceScore - norm) > 1e-5)
			{
				throw new RuntimeException(
					"Probabilities not properly normalized.");
			}
		}
		else
		{
			//System.err.println("intermediate node");

 			StateSet currentState = tree.getLabel();
 			int nSubStates = currentState.numSubStates();
 			short tag = currentState.getState();

			String label = 
				(String)Numberer.getGlobalNumberer("tags").object(tag);
			String leftWord = tree.getYield().get(0).getWord();
			short leftPosTag = tree.getPreTerminalYield().get(0).getState();
			String leftPos =
				(String)Numberer.getGlobalNumberer("tags").object(leftPosTag);

			if(!lexicon.isKnown(leftWord))
			{
				leftWord = lexicon.getSignature(leftWord, currentState.from);
			}

			//System.err.println(tree+" "+label+" "+leftWord+" "+leftPos);
  		
 			//System.err.println("nsub "+nSubStates+" tag "+tag);
  		
 			double norm = 0;

 			for (short substate=0; substate<nSubStates; substate++) 
 			{
				double score = currentState.getOScore(substate) *
					currentState.getIScore(substate);

				double scalingFactor = 
					ScalingTools.calcScaleFactor(currentState.getOScale() +
												 currentState.getIScale() - 
												 sentenceScale);

				double weight = score * scalingFactor;

				norm += weight;

				if(wordAndPosProbs.get(label) == null)
				{
					wordAndPosProbs.put(label, 
										new CounterMap<Short, WordAndPos>());
				}
				CounterMap<Short, WordAndPos> submap = 
					wordAndPosProbs.get(label);
				submap.incrementCount(substate, 
									  new WordAndPos(leftWord, leftPos),
									  weight);

				if(posProbs.get(label) == null)
				{
					posProbs.put(label, new CounterMap<Short, String>());
				}
				CounterMap<Short, String> posSubmap = posProbs.get(label);
				posSubmap.incrementCount(substate, leftPos, weight);

				if(wordProbs.get(label) == null)
				{
					wordProbs.put(label, new CounterMap<Short, String>());
				}
				CounterMap<Short, String> wordSubmap = wordProbs.get(label);
				wordSubmap.incrementCount(substate, leftWord, weight);
			}

			if(Math.abs(sentenceScore - norm) > 1e-5)
			{
				throw new RuntimeException(
					"Probabilities not properly normalized.");
			}

 			//System.err.println("score "+sentenceScore+" "+
			//sentenceScale+" norm "+norm);
		}

		//System.err.println(tree);

		for (Tree<StateSet> child : children) 
		{
			addTreeCounts(child, sentenceScore, sentenceScale);
		}
	}

	void setLambdas(LeftCornerProbs counts)
	{
		for(Map.Entry<String, CounterMap<Short, WordAndPos>> entry : 
				wordAndPosProbs.entrySet())
		{
			CounterMap<Short, WordAndPos> cmap = entry.getValue();
			cmap.normalize();
		}

		for(Map.Entry<String, CounterMap<Short, String>> entry : 
				posProbs.entrySet())
		{
			CounterMap<Short, String> cmap = entry.getValue();
			cmap.normalize();
		}

		posToWord.normalize();

		Counter<String> wordIsCorrect = new Counter<String>();
		Counter<String> norm = new Counter<String>();

		double ll = lambdaEStep(counts, wordIsCorrect, norm, true);

		System.err.println("Log likelihood: "+ll);

		for(int step = 0; step < 10; ++step)
		{
			for(String key : wordIsCorrect.keySet())
			{
				double newL = wordIsCorrect.getCount(key) / norm.getCount(key);
				lambdas.put(key, newL);
				//System.err.println("Setting lambda: "+key+" "+newL);

				if(newL < -1e-5 || newL > 1 + 1e-5)
				{
					System.err.println(wordIsCorrect.getCount(key)+" / "+
									   norm.getCount(key) + " "+newL);
					throw new RuntimeException("!!!");
				}
				else if(newL < 0)
				{
					newL = 1e-5;
				}
				else if(newL > 1)
				{
					newL = 1 - 1e-5;
				}
			}
			
			wordIsCorrect = new Counter<String>();
			norm = new Counter<String>();
			double newLL = lambdaEStep(counts, wordIsCorrect, norm, false);

			System.err.println("Log likelihood: "+newLL);

			double delta = newLL - ll;
			if(delta < 1)
			{
				break;
			}
			ll = newLL;
		}
	}

	double lambdaEStep(LeftCornerProbs counts, 
					   Counter<String> wordIsCorrect,
					   Counter<String> norm,
					   boolean initialize)
	{
		double ll = 0;

		for(Map.Entry<String, CounterMap<Short, WordAndPos>> entry : 
				counts.wordAndPosProbs.entrySet())
		{
			CounterMap<Short, WordAndPos> cmap = entry.getValue();

			String nonterm = entry.getKey();

			for(Short subtag : cmap.keySet())
			{
				Counter<WordAndPos> vals = cmap.getCounter(subtag);

				for(WordAndPos val : vals.keySet())
				{
					double lambda;
					if(initialize)
					{
						lambda = .5;
						lambdas.put(nonterm, .5);
					}
					else
					{
						try
						{
							lambda = lambdas.get(nonterm);
						}
						catch(NullPointerException e)
						{
							System.err.println("No lambda for: "+nonterm);
							throw e;
						}
					}

					double count = vals.getCount(val);

					if(count == 0.0)
					{
						continue;
					}

					//NOTE: unknown handling would be good here
					double probGivenWord = 0;
					try
					{
						probGivenWord = lambda * 
							wordAndPosProbs.get(nonterm).getCounter(
								subtag).getCount(val);
					}
					catch(NullPointerException e)
					{}

					double probGivenPOS = 0;
					try
					{
						probGivenPOS = (1 - lambda) *
							posProbs.get(nonterm).getCounter(
								subtag).getCount(val.pos) *
							posToWord.getCounter(val.pos).getCount(val.word);
					}
					catch(NullPointerException e)
					{}

					double total = probGivenWord + probGivenPOS;

					if(total > (1.0 + 1e-5) || total < 0.0)
					{
						throw new RuntimeException("Badness!");
					}

					if(probGivenWord > total)
					{
						throw new RuntimeException("Fsck!");
					}
// 					System.err.println("nonterm "+nonterm+"-"+subtag+
// 									   " left word/pos "+
// 									   val+" count "+count);
// 					System.err.println("word model: "+probGivenWord +
// 									   " pos model: "+probGivenPOS
// 									   +" = "+total);

					if(total == 0)
					{
						continue;
					}

					ll += Math.log(total) * count;

					wordIsCorrect.incrementCount(nonterm, 
												 count * probGivenWord/total);
					norm.incrementCount(nonterm, count);
				}
			}
		}
 
		return ll;
	}

	void printLambdas(PrintStream out)
	{
		for(Map.Entry<String, Double> entry : lambdas.entrySet())
		{
			out.println(entry.getKey()+" "+entry.getValue());
		}
	}

	void printNTWordTable(PrintStream out)
	{
		printTable(wordProbs, out);
	}

	void printNTPosTable(PrintStream out)
	{
		printTable(posProbs, out);
	}

	void printPosWordTable(PrintStream out)
	{
		posToWord.normalize();

		for(String pos : posToWord.keySet())
		{
			Counter<String> vals = posToWord.getCounter(pos);

			for(String val : vals.keySet())
			{
				out.println(vals.getCount(val) + " " +
								   pos + " -> " + val);
			}
		}
	}

	void printTable(Map<String, CounterMap<Short, String>> table,
					PrintStream out)
	{
		for(Map.Entry<String, CounterMap<Short, String>> entry : 
				table.entrySet())
		{
			CounterMap<Short, String> cmap = entry.getValue();
			cmap.normalize();

			for(Short subtag : cmap.keySet())
			{
				Counter<String> vals = cmap.getCounter(subtag);

				for(String val : vals.keySet())
				{
					if(vals.getCount(val) == 0)
					{
						continue;
					}

					out.println(vals.getCount(val) + " " +
									   entry.getKey()+"_"+subtag
									   + " -> " + val);
				}
			}
		}
	}

	/*
   * Allocate the inside and outside score arrays for the whole tree
   */
	static void allocate(Tree<StateSet> tree) {
		tree.getLabel().allocate();
		for (Tree<StateSet> child : tree.getChildren()) {
			allocate(child);
		}
	}
  
	public static void main(String[] args) 
	{
		OptionParser optParser = new OptionParser(Options.class);
		Options opts = (Options) optParser.parse(args, true);
		// provide feedback on command-line arguments
		System.err.println("Calling with " + optParser.getPassedInOptions());

		String inFileName = opts.inFileName;
		if (inFileName==null)
		{
			throw new Error("Did not provide a grammar.");
		}
		System.err.println("Loading grammar from "+inFileName+".");

		ParserData pData = ParserData.Load(inFileName);
		if (pData==null)
		{
			System.out.println("Failed to load grammar from file"+
							   inFileName+".");
			System.exit(1);
		}
		System.err.println("Loaded.");

		String outName = opts.outName;
		System.err.println("Output to "+outName+".xxx");

		Grammar grammar = pData.getGrammar();
		grammar.splitRules();
		SophisticatedLexicon lexicon = (SophisticatedLexicon)pData.getLexicon();
    
		Numberer.setNumberers(pData.getNumbs());
		Numberer tagNumberer =  Numberer.getGlobalNumberer("tags");
    
		int topLevel = 0;
		for(int i=0; i<grammar.splitTrees.length; ++i)
		{
			int dep = grammar.splitTrees[i].getDepth();
			if(dep > topLevel)
			{
				topLevel = dep;
			}
		}
		topLevel -= 1;
		System.err.println("Max level: "+topLevel);

		for(int level = 0; level <= topLevel; ++level)
		{
			String useOutName = outName+"-lvl"+level;

			LeftCornerProbs leftCorner = 
				new LeftCornerProbs(grammar, lexicon, level, pData.bin);

			short[] numSubstates = leftCorner.grammar.numSubStates;
			try
			{
				InputStreamReader inputData = (opts.inputFile==null) ? new InputStreamReader(System.in) : new InputStreamReader(new FileInputStream(opts.inputFile), "UTF-8");
				PennTreeReader treeReader = new PennTreeReader(inputData);

				int trees = 0;
				Tree<String> tree = null;
				while(treeReader.hasNext())
				{
					tree = treeReader.next(); 
					if (tree.getYield().get(0).equals(""))
					{
						// empty tree -> parse failure
						continue;
					}
					tree = 
						TreeAnnotations.processTree(
							tree, pData.v_markov, pData.h_markov,pData.bin,false);
					Tree<StateSet> stateSetTree = 
						StateSetTreeList.stringTreeToStatesetTree(
							tree, numSubstates, false, tagNumberer);
					allocate(stateSetTree);
					leftCorner.record(stateSetTree);
					++trees;
				}

				System.err.println(trees+" trees read.");
			}
			catch(Exception ex) 
			{
				ex.printStackTrace();
				throw new RuntimeException(ex);
			}

			System.err.println("Probs computed.");

			if(opts.validation != null)
			{
				System.err.println("Loading validation trees from "+
								   opts.validation);
				try
				{
					InputStreamReader inputData = 
						new InputStreamReader(
							new FileInputStream(opts.validation), "UTF-8");
					PennTreeReader treeReader = new PennTreeReader(inputData);

					int valTrees = 0;
					System.err.println("Summarizing...");

					LeftCornerProbs counts = new LeftCornerProbs(
						grammar, lexicon, level, pData.bin);

					Tree<String> tree = null;
					while(treeReader.hasNext())
					{
						tree = treeReader.next(); 
						if (tree.getYield().get(0).equals(""))
						{
							// empty tree -> parse failure
							continue;
						}
						tree = 
							TreeAnnotations.processTree(
								tree, pData.v_markov, pData.h_markov,
								pData.bin,false);
						Tree<StateSet> stateSetTree = 
							StateSetTreeList.stringTreeToStatesetTree(
								tree, numSubstates, false, tagNumberer);
						counts.record(stateSetTree);
						++valTrees;
					}

					System.err.println(valTrees+" trees loaded.");

					leftCorner.setLambdas(counts);
				}
				catch(Exception ex) 
				{
					ex.printStackTrace();
					throw new RuntimeException(ex);
				}
			}

			try
			{
				PrintStream output =
					new PrintStream(
						new GZIPOutputStream(
							new FileOutputStream(
								useOutName+".lookahead.gz")));

				leftCorner.printLambdas(output);
				output.println();
				leftCorner.printNTPosTable(output);
				output.println();
				leftCorner.printNTWordTable(output);
				output.println();
				leftCorner.printPosWordTable(output);

				output.flush();
				output.close();
			}
			catch(IOException e)
			{
				throw new RuntimeException(e);
			}
		}

		System.exit(0);
	}
}
