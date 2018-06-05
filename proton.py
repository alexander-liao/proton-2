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
	return lambda f: f
		

def OperParser(last, opers, name, not_first = None):
	not_first = not_first or last
	@Grammar(name)
	def inner(tokens):
		if last(tokens[:]):
			values = [last(tokens)]
			operators = []
			while tokens and tokens[0][0] == "symbol" and tokens[0][1] in opers:
				operators.append(tokens.pop(0))
				values.append(not_first(tokens))
			if operators:
				return (name, {"values": values, "operators": operators})
			else:
				return values[0]
	return inner

@Grammar("Identifier")
def Identifier(tokens):
	if tokens and tokens[0][0] == "identifier":
		return ("Identifier", tokens.pop(0))

@Grammar("Literal")
def Literal(tokens):
	if tokens and tokens[0][0] in ("number", "string"):
		return ("Literal", tokens.pop(0))

@Grammar("BracketedExpr")
def BracketedExpr(tokens):
	if tokens and tokens[0] == ("symbol", "(") and LAST(tokens[1:]):
		tokens.pop(0)
		result = LAST(tokens)
		if not (tokens and tokens[0] == ("symbol", ")")):
			raise RuntimeError("Unclosed bracket")
		tokens.pop(0)
		return result

@Grammar("SingularValue")
def SingularValue(tokens):
	return Identifier(tokens) or Literal(tokens) or BracketedExpr(tokens)

@Grammar("Value")
def Value(tokens):
	index = 0
	front = []
	while index < len(tokens) and tokens[index][0] == "symbol" and tokens[index][1] in ["++", "--", "+", "-", "**", "*"]:
		front.append(tokens[index][1])
		index += 1
	if SingularValue(tokens[index:]):
		tokens[:] = tokens[index:]
		inner = SingularValue(tokens)
		index = 0
		back = []
		while index < len(tokens) and tokens[index][0] == "symbol" and tokens[index][1] in ["++", "--"]:
			back.append(tokens[index][1])
			index += 1
		tokens[:] = tokens[index:]
		return ("Value", {"front": front, "inner": inner, "back": back})

SubValue = OperParser(Value, ["."], "SubValue", Identifier)

@Grammar("BracketCall")
def BracketCall(tokens):
	if SubValue(tokens[:]):
		base = SubValue(tokens)
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
	while tokens:
		result = Statement(tokens)
		if result: yield result
		else: yield ("Unmatched", tokens.pop(0))

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

tokens = list(tokenize(sys.stdin.read()))

print(*tokens)

prettyprint(list(Program(tokens)))
