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

public class Unker
{
	public static class Options {		
		@Option(name = "-gr", required = true, usage = "Input File for Grammar (Required)\n")
		public String inFileName;

		@Option(name = "-inputFile", usage = "Read input from this file instead of reading it from STDIN.")
		public String inputFile;

		@Option(name = "-trees", usage  = "Print trees, not strings.")
		public boolean printTrees = false;
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
		SophisticatedLexicon lexicon = (SophisticatedLexicon)pData.getLexicon();

		Numberer.setNumberers(pData.getNumbs());
		Numberer tagNumberer =  Numberer.getGlobalNumberer("tags");

		try
		{
			InputStreamReader inputData = (opts.inputFile==null) ? new InputStreamReader(System.in) : new InputStreamReader(new FileInputStream(opts.inputFile), "UTF-8");
			PennTreeReader treeReader = new PennTreeReader(inputData);

			Tree<String> tree = null;
			while(treeReader.hasNext())
			{
				tree = treeReader.next(); 
				if (tree.getYield().get(0).equals(""))
				{
					// empty tree -> parse failure
					continue;
				}
				int pos = 0;
				if(!opts.printTrees)
				{
					for(String word : tree.getYield())
					{
						if(pos > 0)
						{
							System.out.print(" ");
						}

						if(lexicon.isKnown(word))
						{
							System.out.print(word);
						}
						else
						{
							System.out.print(lexicon.getSignature(word, pos));
						}
						++pos;
					}
					System.out.println();
				}
				else
				{
					for(Tree<String> pt : tree.getTerminals())
					{
						if(!lexicon.isKnown(pt.getLabel()))
						{
							pt.setLabel(
								lexicon.getSignature(pt.getLabel(), pos));
						}
						++pos;
					}
					System.out.println(tree);
				}
			}
		}
		catch(Exception ex) 
		{
			ex.printStackTrace();
			throw new RuntimeException(ex);
		}
		System.exit(0);
	}
}
