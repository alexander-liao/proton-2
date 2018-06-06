import re, sys

keywords = "if else for while try catch finally const immutable not".split()

symbols = list(map(re.escape, "( ) [ ] { } // /^ / % ** `/ * . ; : && || & | and or".split())) + ["\\++", "\\-+"]

token_types = [(re.compile(x), y, z) for x, y, z in [
	(r"##.*", "comment", -1),
	(r"/.\\(.+|\s+)*/.\\", "comment", -1),
	(r"\s+", "whitespace", -1),
	(r"|".join(symbols), "symbol", 0),
	(r"(([1-9][0-9]*|0)(\.[0-9]*)?|\.[0-9]+)", "number", 0),
	(r"\"([^\\\"]+|\\.)*\"", "string", 0),
	(r"\'([^\\\']+|\\.)*\'", "string", 0),
	(r"|".join(keywords), "keyword", 0),
	(r"\w+", "identifier", 0),
]]

def modify(match):
	if all(char == "+" for char in match):
		if len(match) == 1: yield ("symbol", "+")
		elif len(match) == 2: yield ("symbol", "++")
		elif len(match) == 3: yield ("symbol", "++"); yield ("symbol", "+")
		elif len(match) == 4: yield ("symbol", "++"); yield ("symbol", "+"); yield ("symbol", "+")
		else: yield ("symbol", "++"); yield from [("symbol", "+")] * (len(match) - 4); yield ("symbol", "++")
	elif all(char == "-" for char in match):
		if len(match) == 1: yield ("symbol", "-")
		elif len(match) == 2: yield ("symbol", "--")
		elif len(match) == 3: yield ("symbol", "--"); yield ("symbol", "-")
		elif len(match) == 4: yield ("symbol", "--"); yield ("symbol", "-"); yield ("symbol", "-")
		else: yield ("symbol", "--"); yield from [("symbol", "-")] * (len(match) - 4); yield ("symbol", "--")
	else:
		yield ("symbol", match)

def tokenize(code):
	unmatched = ""
	while code:
		for regex, name, group in token_types:
			match = re.match(regex, code)
			if match:
				if unmatched:
					yield from modify(unmatched)
					unmatched = ""
				if group != -1: 
					string = match.group(group)
					if name == "symbol": yield from modify(string)
					else: yield (name, string)
				else:
					string = match.group()
				code = code[len(string):]
				break
		else:
			unmatched += code[0]
			code = code[1:]
	if unmatched:
		yield from modify(unmatched)

def Grammar(name):
	def inside(func):
		return func
	return inside
		

def OperParser(last, opers, name, not_first = None):
	not_first = not_first or last
	@Grammar(name)
	def inner(tokens):
		value = last(tokens)
		if value:
			values = [value]
			operators = []
			while tokens and tokens[0][0] == "symbol" and tokens[0][1] in opers:
				operators.append(tokens.pop(0)[1])
				values.append(not_first(tokens))
			if operators:
				return (name, {"values": values, "operators": operators})
			else:
				return values[0]
	return inner

@Grammar("Identifier")
def Identifier(tokens):
	if tokens and tokens[0][0] == "identifier":
		return ("Identifier", tokens.pop(0)[1])

@Grammar("Literal")
def Literal(tokens):
	if tokens and tokens[0][0] in ("number", "string"):
		return ("Literal", tokens.pop(0)[1])

@Grammar("BracketedExpr")
def BracketedExpr(tokens):
	if tokens and tokens[0] == ("symbol", "(") and LAST(tokens[1:]):
		tokens.pop(0)
		result = LAST(tokens)
		if not (tokens and tokens[0] == ("symbol", ")")):
			raise RuntimeError("Unclosed bracket")
		tokens.pop(0)
		return ("BracketedExpr", result)

@Grammar("SingularValue")
def SingularValue(tokens):
	return Identifier(tokens) or Literal(tokens) or BracketedExpr(tokens)

@Grammar("Value")
def Value(tokens):
	front = []
	prev = tokens[:]
	while tokens and tokens[0][0] == "symbol" and tokens[0][1] in ["++", "--", "+", "-", "**", "*"]:
		front.append(tokens.pop(0)[1])
	inner = SingularValue(tokens)
	if inner:
		back = []
		while tokens and tokens[0][0] == "symbol" and tokens[0][1] in ["++", "--"]:
			back.append(tokens.pop(0)[1])
		return ("Value", {"front": front, "inner": inner, "back": back})
	tokens[:] = prev

SubValue = OperParser(Value, ["."], "SubValue", Identifier)

@Grammar("BracketCall")
def BracketCall(tokens):
	base = SubValue(tokens)
	if base:
		argument_lists = []
		calltype = []
		while tokens and tokens[0][0] == "symbol" and tokens[0][1] in ["[", "("]:
			isFunc = tokens[0][1] == "("
			calltype.append("func" if isFunc else "index")
			tokens.pop(0)
			argument_lists.append(ArgumentList(tokens, BracketCall if isFunc else IndexSlice))
			if not (tokens and tokens[0][0] == "symbol" and tokens[0][1] == (")" if isFunc else "]")):
				raise RuntimeError("Unclosed bracket at end of argument list for " + ("function" if isFunc else "index access"))
			tokens.pop(0)
		if argument_lists == []:
			return base
		return ("BracketCall", {"base": base, "argument_lists": argument_lists, "calltype": calltype})

@Grammar("IndexSlice")
def IndexSlice(tokens):
	if BracketCall(tokens[:]):
		first = BracketCall(tokens)
		if tokens and tokens[0] == ("symbol", ":"):
			tokens.pop(0)
			second = BracketCall(tokens)
			if tokens and tokens[0] == ("symbol", ":"):
				tokens.pop(0)
				third = BracketCall(tokens)
				return ("IndexSlice", [first, second, third])
			return ("IndexSlice", [first, second, None])
		else:
			return first

@Grammar("ArgumentList")
def ArgumentList(tokens, subtype = BracketCall):
	if subtype(tokens[:]):
		args = [subtype(tokens)]
		while tokens and tokens[0] == ("symbol", ","):
			tokens.pop(0)
			args.append(subtype(tokens))
		return ("ArgumentList", args)

InfixCall = OperParser(BracketCall, ["@", "#"], "InfixCall")
Exponent = OperParser(InfixCall, ["**", "`/"], "Exponent")
Product = OperParser(Exponent, ["*", "%", "/", "//", "/^"], "Product")
Sum = OperParser(Product, ["+", "-"], "Sum")
BitShift = OperParser(Sum, [">>", "<<"], "BitShift")
BitAnd = OperParser(BitShift, ["&"], "BitAnd")
BitXor = OperParser(BitAnd, ["^"], "BitXor")
BitOr = OperParser(BitXor, ["|"], "BitOr")
EnglishLike = OperParser(BitOr, ["and", "or"], "EnglishLike")
Comparison = OperParser(EnglishLike, [">", "<", ">=", "<=", "==", "!=", "in", "not in", "is", "is not"], "Comparison")

@Grammar("LogicalNot")
def LogicalNot(tokens):
	number = 0
	while tokens and tokens[0] == ("keyword", "not"):
		tokens.pop(0)
		number += 1
	result = Comparison(tokens)
	if number == 0:
		return result
	return result and ("LogicalNot", {"nots": number, "base": result})

LogicalAnd = OperParser(LogicalNot, ["&&"], "LogicalAnd")
LogicalOr = OperParser(LogicalAnd, ["||"], "LogicalOr")

LAST = LogicalOr

@Grammar("Statement")
def Statement(tokens):
	if LAST(tokens[:]):
		result = LAST(tokens)
		if tokens and tokens[0] == ("symbol", ";"):
			tokens.pop(0)
		return ("Statement", result)
	else:
		return None

@Grammar("Program")
def Program(tokens):
	statements = []
	while tokens:
		result = Statement(tokens)
		if result: statements.append(result)
		else: tokens.pop(0)
	return ("Program", statements)

INDENT = 3

def prettyprint(expr, indent = 0, inline = False):
	if type(expr) != list: expr = [expr]; list_mode = False
	else: list_mode = True
	if expr == []: print([]); return
	if list_mode and inline: print("[")
	for sub in expr:
		if type(sub) == tuple:
			print(" " * indent * (list_mode or not inline) + sub[0])
			prettyprint(sub[1], indent + INDENT)
		elif type(sub) == dict:
			if inline: print("{")
			for key in sub:
				print(" " * indent + repr(key) + ": ", end = "")
				prettyprint(sub[key], indent + INDENT, True)
			if inline: print(" " * (indent - INDENT) + "}")
		else:
			print(" " * indent * (not inline) + str(sub))
	if list_mode and inline: print(" " * (indent - INDENT) + "]")

def attempt(*factories, error = "All attempts failed"):
	for func in factories:
		try:
			return func()
		except:
			pass
	else:
		raise RuntimeError(error)

def getProtonAttr(obj, name, altname = None):
	if obj["type"] == "__primitive":
		try: return getattr(obj["value"], name)
		except: return None
	else:
		return obj.get(altname or name, None)

def downgrade(obj):
	if obj["type"] == "__primitive": obj = obj["value"]
	return obj

def caller(func, *a, **k):
	return lambda: func(*a, **k)

def operError(symbol, left, right):
	return "Operation %s not supported between objects of type %s and %s" % (symbol, left["type"], right["type"])

def primitive(value):
	return {"type": "__primitive", "value": value}

def operGen(symbol, name, rname, altname = None, altrname = None):
	altname = altname or name
	altrname = altrname or rname
	def inner(left, right):
		l_oper = getProtonAttr(left, name, altname)
		r_oper = getProtonAttr(right, rname, altrname)
		L = downgrade(left)
		R = downgrade(right)
		return primitive(attempt(caller(l_oper, R), caller(r_oper, L), operError(symbol, left, right)))
	return inner

mul = operGen("*", "__mul__", "__rmul__")
div = operGen("/", "__truediv__", "__rtruediv__")
floordiv = operGen("//", "__floordiv__", "__rfloordiv__")
mod = operGen("%", "__mod__", "__rmod__")
add = operGen("+", "__add__", "__radd__")
sub = operGen("-", "__sub__", "__rsub__")

def ceildiv(left, right):
	try:
		return primitive(-(-downgrade(left) // downgrade(right)))
	except:
		try:
			return primitive(-(downgrade(left) // -downgrade(right)))
		except:
			pass
	if "__ceildiv__" in left:
		try:
			return left["__ceildiv__"](downgrade(right))
		except:
			pass
	if "__rceildiv__" in right:
		try:
			return right["__rceildiv__"](downgrade(left))
		except:
			pass
	raise RuntimeError(operError("/^", left, right))

def evalopers(tree, funcs):
	values = tree[1]["values"][:]
	operators = tree[1]["operators"][:]
	value = evaluate(values.pop(0))
	while operators:
		operator = operators.pop(0)
		value = funcs[operator](value, evaluate(values.pop(0)))
	return value

def assign(tree, value, scope, global_scope):
	pass

def evaluate(tree, scope = {}, global_scope = {}):
	name = tree[0]
	if name == "Program":
		value = None
		for subtree in tree[1]:
			value = evaluate(subtree)
		return value
	elif name == "Statement":
		return evaluate(tree[1])
	elif name == "Product":
		return evalopers(tree, {"*": mul, "/": div, "//": floordiv, "/^": ceildiv, "%": mod})
	elif name == "Sum":
		return evalopers(tree, {"+": add, "-": sub})
	elif name == "Value":
		value = evaluate(tree[1]["inner"])
		return value # TODO
	elif name == "Literal":
		result = eval(tree[1])
		return primitive(result) # TODO
	elif name == "BracketedExpr":
		return evaluate(tree[1]) # TODO
	else:
		print(name + " not evaluated")

tokens = list(tokenize(sys.stdin.read()))

print(*tokens)

tree = Program(tokens)

print(evaluate(tree))
