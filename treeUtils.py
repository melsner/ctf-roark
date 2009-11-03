from rule import Rule

def treeToStr(tree):
    if type(tree) != tuple:
        return str(tree)
    return "(%s %s)" % (tree[0], " ".join([treeToStr(x) for x in tree[1:]]))

def normalizeTree(tree, stripSub=True):
    return normalizeTreeHelper(tree, stripSub)[0]

def normalizeTreeHelper(tree, stripSub):
    if type(tree) != tuple:
        return [tree,]
    if tree[1] is None:
        return []

    label = tree[0]
    if stripSub:
        label = label.split("_")[0]
    if label.startswith("@"):
        res = []
        for sub in tree[1:]:
            ntree = normalizeTreeHelper(sub, stripSub)
            for constit in ntree:
                res.append(constit)
    else:
        res = [label,]
        for sub in tree[1:]:
            ntree = normalizeTreeHelper(sub, stripSub)
            for constit in ntree:
                res.append(constit)
        res = [tuple(res)]

    return res

def treeToDeriv(tree):
    if type(tree[1]) is not tuple:
        r = Rule()
        r.setup(tree[0], [tree[1],], 1.0)
        return [r,]
    else:
        r = Rule()
        rhs = [x[0] for x in tree[1:]]
        assert(len(rhs) <= 2), "Non-binary rule: %s" % str(rhs)
        r.setup(tree[0], rhs, 1.0)
        res = [r,]
        for subt in tree[1:]:
            res += treeToDeriv(subt)
        return res

def treeToTuple(tree):
    assert(tree[0] == "(")
    return treeToTupleHelper(tree, 1)[0]

def treeToTupleHelper(tbuf, ind):
    label = ""
    word = ""
    inLabel = True
    subs = []

    while ind < len(tbuf):
        char = tbuf[ind]
        #print char
        ind += 1

        if char == "(":
            #print "push", ind
            (sub, newInd) = treeToTupleHelper(tbuf, ind)
            subs.append(sub)
            #print "pop", newInd, subs
            ind = newInd
        elif char == ")":
            if word:
                return ((label, word), ind)
            elif subs:
                return (tuple([label,]+subs), ind)
            else:
                #epsilon
                return ((label,), ind)
        elif char == " ":
            inLabel = False
        else:
            if inLabel:
                label += char
            else:
                word += char
    assert(False), "Malformed tree, read %s" % char
