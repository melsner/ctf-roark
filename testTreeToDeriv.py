from treeUtils import treeToDeriv, treeToTuple, untransform

# tt = "(ROOT (S (NP (DT The) (@NP (ADJP (RBS most) (JJ troublesome)) (NN report))) (@S (VP (MD may) (VP (VB be) (NP (NP (DT the) (@NP (NNP August) (@NP (NN merchandise) (@NP (NN trade) (NN deficit))))) (ADJP (JJ due) (@ADJP (ADVP (IN out)) (NP (NN tomorrow))))))) (. .))))"
# print treeToTuple(tt)
# print treeToDeriv(treeToTuple(tt))

tt = """(ROOT (RS (DT The) (ROOTlcDT (NN government) (POS 's) (ROOTlcNP (NN plan) (ROOTlcNP (VP (VBZ is) (VPlcVBZ (ADJP (JJ stupid) (ADJPlcJJ )) (VPlcVP ))) (. .) (ROOTlcS ))))))"""
print treeToTuple(tt)
print untransform(treeToTuple(tt))
