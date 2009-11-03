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

public class AccurateUnaries
{
	Grammar grammar;
	SophisticatedLexicon lexicon;
	ArrayParser labeler;
	Numberer tagNumberer;
	Binarization binarization;

	CounterMap<String, String> unaryTable;

	public static class Options {		
		@Option(name = "-gr", required = true, usage = "Input File for Grammar (Required)\n")
		public String inFileName;

		@Option(name = "-inputFile", usage = "Read input from this file instead of reading it from STDIN.")
		public String inputFile;

		@Option(name="-out", usage="Stem of filename for output files.")
		public String outName;
	}

	public AccurateUnaries(Grammar grammar, SophisticatedLexicon lexicon,
						   int labelLevel, Binarization bin) 
	{
		unaryTable = new CounterMap<String, String>();

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
		boolean unary = children.size() == 1;

		if(tree.isLeaf())
		{
			return;
		}
		else if(tree.isPreTerminal())
		{
			//far as I know, preterms are pretty safe
		}
		else
		{
			//System.err.println("intermediate node");
			if(unary)
			{
				StateSet currentState = tree.getLabel();
				int nSubStates = currentState.numSubStates();
				short tag = currentState.getState();

				String label = (String)tagNumberer.object(tag);

				double norm = 0;

				for(short substate=0; substate<nSubStates; substate++) 
				{
					String lhs = label + "_" + substate;

					double score = currentState.getOScore(substate) *
						currentState.getIScore(substate);

					double scalingFactor = 
						ScalingTools.calcScaleFactor(currentState.getOScale() +
													 currentState.getIScale() - 
													 sentenceScale);

					double weight = score * scalingFactor;

					norm += weight;

					StateSet childState = children.get(0).getLabel();
					int nChildSubStates = childState.numSubStates();
					short childTag = childState.getState();

					String childLabel = (String)tagNumberer.object(childTag);

					for(short childSubstate=0; 
						childSubstate<nChildSubStates; childSubstate++) 
					{
						String rhs = childLabel + "_" + childSubstate;

						double childScore = 
							childState.getOScore(childSubstate) *
							childState.getIScore(childSubstate);

						double childScalingFactor = 
							ScalingTools.calcScaleFactor(
								childState.getOScale() +
								childState.getIScale() - 
								sentenceScale);

						double childWeight = childScore * childScalingFactor;

						Double totalWeight = new Double(weight * childWeight);
						unaryTable.incrementCount(lhs, rhs, totalWeight);
						if(totalWeight.isNaN())
						{
							throw new RuntimeException("Bad!");
						}												  
					}
				}

				if(Math.abs(sentenceScore - norm) > 1e-5)
				{
					throw new RuntimeException(
						"Probabilities not properly normalized.");
				}
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

	void printUnaries(PrintStream out)
	{
		unaryTable.normalize();

		for(String lhs : unaryTable.keySet())
		{
			Counter<String> vals = unaryTable.getCounter(lhs);

			for(String val : vals.keySet())
			{
				Double dval = new Double(vals.getCount(val));
				if(dval != 0 && !dval.isNaN())
				{
					out.println(dval + " " + lhs + " -> " + val);
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

			AccurateUnaries acc = 
				new AccurateUnaries(grammar, lexicon, level, pData.bin);

			short[] numSubstates = acc.grammar.numSubStates;
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
					acc.record(stateSetTree);
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

			try
			{
				PrintStream output =
					new PrintStream(
						new GZIPOutputStream(
							new FileOutputStream(
								useOutName+".unaries.gz")));

				acc.printUnaries(output);
				output.println();
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
