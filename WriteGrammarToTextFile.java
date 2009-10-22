/**
 * 
 */
package edu.berkeley.nlp.PCFGLA;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.io.Writer;

import edu.berkeley.nlp.util.Option;
import edu.berkeley.nlp.util.OptionParser;

import edu.berkeley.nlp.util.Numberer;

import java.util.Map;
import java.util.TreeMap;

/**
 * @author petrov
 *
 */
public class WriteGrammarToTextFile {

	public static class Options {		
// 		@Option(name = "-labelLevel", usage = "Parse with projected grammar from this level (yielding 2^level substates) (Default: -1 = input grammar)")
// 		public int labelLevel = -1;

		@Option(name = "-threshold", usage = "Filter rules below threshold.")
		public double threshold = -1;

		@Option(name = "-gr", usage = "Grammar.")
		public String grammar;

		@Option(name = "-out", usage = "Output file stem.")
		public String out;
	}

	/**
	 * @param args
	 */
	public static void main(String[] args) 
	{
		OptionParser optParser = new OptionParser(Options.class);
		Options opts = (Options) optParser.parse(args, true);
		// provide feedback on command-line arguments
		System.err.println("Calling with " + optParser.getPassedInOptions());
	
		String inFileName = opts.grammar;
		String outName = opts.out;

		System.out.println("Loading grammar from file "+inFileName+".");
		ParserData pData = ParserData.Load(inFileName);
		if (pData == null) {
			System.out.println("Failed to load grammar from file" + inFileName + ".");
			System.exit(1);
		}
		
		Grammar grammar = pData.getGrammar();
//		if (grammar instanceof HierarchicalGrammar)
//			grammar = (HierarchicalGrammar)grammar;
		Lexicon lexicon = pData.getLexicon();

		Numberer.setNumberers(pData.getNumbs());
		Numberer tagNumberer = Numberer.getGlobalNumberer("tags");

//		int labelLevel = opts.labelLevel;
		double threshold = opts.threshold;

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
		System.out.println("max level: "+topLevel);

		//dump the inheritance tree
		try
		{
			Writer output = 
				new BufferedWriter(new FileWriter(outName+".hier"));

			int[][][] toSub = new int[topLevel+1][][];
			grammar.splitRules();

			for(int level = 0; level <= topLevel; ++level)
			{ 
				int[][] fromMapping = grammar.computeMapping(1);
				int[][] toSubstateMapping = 
					grammar.computeSubstateMapping(level);
				toSub[level] = toSubstateMapping;
			}

			int numNts = grammar.numStates;
			for(int nt = 0; nt < numNts; ++nt)
			{
				String ntName = (String)tagNumberer.object(nt);
				for(int level = 1; level <= topLevel; ++level)
				{
					int[] currSubs = toSub[level][nt];
					int[] prevSubs = toSub[level-1][nt];

					Map<Integer, Integer> mapping = 
						new TreeMap<Integer,Integer>();

					int numSubstates = currSubs.length;
					for(int i = 1; i < numSubstates; ++i)
					{
						int prevSym = prevSubs[i];
						int currSym = currSubs[i];

						Integer prevMap = mapping.get(currSym);
						if(prevMap != null && prevMap != prevSym)
						{
							throw new RuntimeException("BAD!");
						}

						mapping.put(currSym, prevSym);
					}

					for(Map.Entry ent : mapping.entrySet())
					{
						String mapStr = level +" " + 
							ntName+"_"+ent.getValue()+" -> "+
							ntName+"_"+ent.getKey();

						output.write(mapStr+"\n");
					}
				}
			}

			output.close();
		}
		catch(IOException e)
		{
			throw new RuntimeException(e);
		}

		for(int labelLevel = 0; labelLevel <= topLevel; ++labelLevel)
		{
			Grammar useGrammar = null;
			Lexicon useLexicon = null;
			
			if(labelLevel != topLevel)
			{
				int[][] fromMapping = grammar.computeMapping(1);
				int[][] toSubstateMapping = 
					grammar.computeSubstateMapping(labelLevel);
				int[][] toMapping = 
					grammar.computeToMapping(labelLevel,toSubstateMapping);
				double[] condProbs = 
					grammar.computeConditionalProbabilities(fromMapping,toMapping);
    	
				Grammar newGr = 
					grammar.projectGrammar(condProbs,
										   fromMapping,toSubstateMapping);
				Lexicon newLx = 
					lexicon.projectLexicon(condProbs,
										   fromMapping,toSubstateMapping);
				newGr.splitRules();

// 				double filter = 1.0e-10;
// 				newGr.removeUnlikelyRules(filter,1.0);
// 				newLx.removeUnlikelyTags(filter,1.0);

				useGrammar = newGr;
				useLexicon = newLx;
			}
			else
			{
				useGrammar = grammar;
				useLexicon = lexicon;
			}

			SpanPredictor spanPredictor = pData.getSpanPredictor();
		
			if (threshold != -1)
			{
				double filter = threshold;
				grammar.removeUnlikelyRules(filter,1.0);
				lexicon.removeUnlikelyTags(filter,1.0);
			}

			String useOutName = outName+"-lvl"+labelLevel;

			System.out.println("Writing output to files "+useOutName+".xxx");
			Writer output = null;
			try {
				output = new BufferedWriter(new FileWriter(useOutName+".grammar"));
				//output.write(grammar.toString());
				useGrammar.writeData(output);
				if (output != null)	output.close();
				output = new BufferedWriter(new FileWriter(useOutName+".lexicon"));
				output.write(useLexicon.toString());
				if (output != null)	output.close();
//			output = new BufferedWriter(new FileWriter(useOutName+".words"));
//			for (String word : lexicon.wordCounter.keySet())
//				output.write(word + "\n");
//			if (output != null)	output.close();
				if (spanPredictor!=null){
					SimpleLexicon lex = (SimpleLexicon)useLexicon;
					output = new BufferedWriter(new FileWriter(useOutName+".span"));
					output.write(spanPredictor.toString(lex.wordIndexer));
					if (output != null)	output.close();
				}

			} catch (IOException ex) { ex.printStackTrace();}
		}
	}
}
