import sys, ast

operators = sorted(["~", "`", "!", "@", "#", "$", "%", "^", "&", "*", "-", "+", "**", "/", "//", "/_", "=", ">", "<", "==", "!=", ">=", "<="], key = len, reverse = True)
brackets = list("()[]{}")

def tokenize(chararray):
	chararray = chararray[::-1]
	while chararray:
		next = chararray[-1]
		if next.isdigit():
			num = ""
			while chararray and chararray[-1].isdigit():
				num += chararray.pop()
			yield ("literal-num", int(num))
		elif next.isalnum():
			ident = ""
			while chararray[-1].isalnum():
				ident += chararray.pop()
			yield ("identifier", ident)
		elif next == ".":
			chararray.pop()
			yield ("getattr", ".")
		elif next == "'" or next == '"':
			end = string = next
			chararray.pop()
			jump = False
			while True:
				if chararray == []:
					raise RuntimeError("Tokenization Error: Unclosed String ({end}...{end})".format(end = end))
				next = chararray.pop()
				string += next
				if next == end and not jump:
					break
				if next == "\\" and not jump:
					jump = True
				else:
					jump = False
			yield ("literal-str", ast.literal_eval(string))
		elif any(operator.startswith(next) for operator in operators):
			op = max(filter(lambda operator: list(operator) == chararray[-len(operator):], operators), key = len)
			yield ("operator", op)
			chararray = chararray[:-len(op)]
		elif next in brackets:
			yield ("bracket", next)
			chararray.pop()
		else:
			chararray.pop()

functions = {}

def Grammar(name):
	def inner(func):
		functions[name] = func
		return func
	return inner

def func(name):
	return functions.get(name, name)

def OperParser(name, operators, sub):
	@Grammar(name)
	def inner(tokens):
		first = func(sub)(tokens)
		if not first: return
		values = [first]
		ops = []
		while tokens and tokens[0][0] == "operator" and tokens[0][1] in operators:
			ops.append(tokens.pop(0)[1])
			values.append(func(sub)(tokens))
		return (name, values, ops)
	return inner

@Grammar("Program")
def Program(tokens):
	statements = []
	while tokens:
		statement = Statement(tokens)
		if not statement: raise RuntimeError("Parse Error: non-statement detected")
		statements.append(statement)
	return ("Program", statements)

@Grammar("Statement")
def Statement(tokens):
	return Expression(tokens)

@Grammar("Expression")
def Expression(tokens):
	return Sum(tokens)

Sum = OperParser("Sum", ["+", "-"], "Product")
Product = OperParser("Product", ["*", "/", "//", "/_", "%"], "Exponent")
Exponent = OperParser("Exponent", ["**"], "Value")

@Grammar("Value")
def Value(tokens):
	return Literal(tokens)

@Grammar("Literal")
def Literal(tokens):
	if tokens[0][0].startswith("literal"):
		return ("Literal", tokens.pop(0)[1])

def prettyprint(tree, indent = 0):
	print("  " * indent + tree[0])
	if hasattr(tree[1], "__iter__"):
		for sub in tree[1]:
			prettyprint(sub, indent + 1)
	else:
		print("  " * (indent + 1) + str(tree[1]))

if __name__ == "__main__":
	prettyprint(Program(list(tokenize(list(sys.argv[1])))))
