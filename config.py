#!/usr/bin/env python3

import argparse
import os
import os.path
import re
import shutil
import subprocess
import sys
import traceback

VERSION = "0.1"
STDOUT = None
STDERR = None
QUIET = False
LOGGING = False

OS_INFO = {
	"linux": [
		"OS = linux",
		"EXEC =",
		"LIBDYN_SUFF = .so",
		"LIBDYN_PREF = lib",
		"LIB_SUFF = .a",
		"LIB_PREF = lib"
	],
	"darwin": [
		"OS = darwin",
		"EXEC =",
		"LIBDYN_SUFF = .dynlib",
		"LIBDYN_PREF =",
		"LIB_SUFF = .a",
		"LIB_PREF = lib"
	]
}

SPACE_RE = re.compile('\s')

def fatal(message, source=None, return_code=1):
	"""Display an error and stops the script with the rerturn_code parameter (default to 1). Source must be a pair (source path,source line)."""
	if source == None:
		sys.stderr.write("ERROR: %s\n" % message)
	else:
		file, line = source
		sys.stderr.write("ERROR: %s:%d: %s\n" % (file, line, message))
	exit(return_code)

def info(message):
	"""Display information to the user."""
	if not QUIET:
		sys.stdout.write("INFO: %s\n" % message)
	if LOGGING:
		STDOUT.write("INFO: %s\n" % message)
		STDOUT.flush()

def execute(cmd, dir = None):
	"""Execute the command as a shell command in the dir directory (default current directory)."""
	if dir == None:
		dir = os.getcwd()
	cp = subprocess.run(cmd, shell=True, cwd = dir, stdout=STDOUT, stderr=STDERR)
	return cp.returncode == 0

VAR_RE = re.compile('\$\$|\$\(([^\)]+)\)|\$(\S+)')

def eval_arg(text, env):
	"""Transform the text by replacing $-prefixed variables by the definitions in the env dictionary."""
	res = ''
	match = VAR_RE.search(text)
	while match is not None:
		res += text[:match.start()]
		found = match.groups()[0]
		if found == None:
			res += '$'
		else:
			try:
				res += env[found]
			except KeyError:
				pass
		text = text[match.end():]  
		match = VAR_RE.search(text)
	return res + text


def eval_args(args, env):
	"""Transform arguments by replacing $-prefixed variables by the definitions in the env dictionary."""
	return [eval_arg(arg, env) for arg in args]


class ConfigException(Exception):

	def __init__(self, msg):
		self.msg = msg

	def __str__(self):
		return self.msg
	
class ParseException(ConfigException):
	"""Exception raised if there is a parsing error."""

	def __init__(self, msg):
		ConfigException.__init__(self, msg)


class Action:
	"""Base class of Source, Pipe and Command. Provide support for source file:line information for error display."""

	def __init__(self):
		self.source = None
		self.line = None

	def set_source(self, file, line):
		self.source = (file, line)

	def get_source(self):
		"""Get source information."""
		return self.source

	def error(self):
		"""Called to get an error message for the current action."""
		return ""

	def fatal(self, message = None):
		"""Display fatal error for the current action."""
		if message == None:
			message = self.error()
		fatal(message, self.get_source())


###### Sources ######

class Source(Action):
	"""A source is element that generate a string, typically a path after the realization of some operations."""
	MAP = {}

	def __init__(self, args):
		"""Build the source with the given arguments (list of strings).
		In case of error, the constructor can raise ParException."""
		Action.__init__(self)

	def eval(self, env):
		"""Called to evaluate the source with the given environment.
		This function has to return the resulting string or None to represent failure."""
		return None

	def error(self):
		"""Called to produce as string the last error of this source."""
		return None

	def declare(name, source):
		"""Declare a new source (that must be prefixed by !). Source must be the constructor of the source class."""
		Source.MAP[name] = source

	def make(name, args):
		"""Build a source with name and args parameters."""
		try:
			return Source.MAP[name](args)
		except KeyError:
			raise ParseException('no source named "%s"' % name)

class Const(Source):

	def __init__(self, value):
		self.value = value

	def eval(self, env):
		return eval_arg(self.value, env)


class Which(Source):

	def __init__(self, cmds):
		self.cmds = cmds

	def eval(self, env):
		for cmd in eval_args(self.cmds, env):
			path = shutil.which(cmd)
			if path is not None:
				return path
		return None

	def error(self):
		return "canot find one command of %s." % ", ".join(self.cmds)

Source.declare("!which", Which)


class LookUp(Source):

	def __init__(self, paths):
		self.paths = paths

	def eval(self, env):
		for path in eval_args(self.paths, env):
			if os.path.exists(path):
				return path
		return None

	def error(self):
		return "cannot find one path of %s." % ", ".join(self.paths)

Source.declare('!lookup', LookUp)


class Git(Source):

	def __init__(self, args):
		if len(args) != 1:
			raise ParseException("!git requires exacly 1 argument!")
		self.url = args[0]
		try:
			p = self.url.rindex('/')
			self.path = self.url[p+1:-4]
		except ValueError:
			raise ParsException('malformed URL "%s"' % self.url)

	def eval(self, env):
		path = self.path
		if os.path.exists(path):
			info("GIT pulling %s" % path)
			execute("git pull %s" % self.url, dir=path)
			return path
		else:
			info("GIT cloning %s" % path)
			if not execute("git clone %s" % self.url):
				return None
			else:
				return path

	def error(self):
		return "cannot clone %s" % self.path

Source.declare("!git", Git)

class Alt(Source):

	def __init__(self, alts):
		self.alts = alts

	def eval(self, env):
		for alt in self.alts:
			res = alt.eval(env)
			if res is not None:
				return res
		return None

	def error(self):
		return "all alternatives failed:\n* %s\n" \
			% "\n* ".join([alt.error() for alt in self.alts])


class Chain(Source):

	def __init__(self, source, pipeline):
		self.source = source
		self.pipeline = pipeline
		self.failed = None

	def eval(self, env):
		value = self.source.eval(env)
		if value is None:
			self.failed = self.source
			return None
		value = self.pipeline.process(value, env)
		if value is None:
			self.failed  = self.pipeline
		return value

	def error(self):
		return self.failed.error()


class Check(Source):

	def __init__(self, source, pipes):
		self.source = source
		self.pipes = pipes

	def eval(self, env):
		value = self.source.eval(env)
		for pipe in self.pipes:
			if pipe.process(value, env) is None:
				self.failed = pipe
				return None
		return value

	def error(self):
		return self.failed.error() 


####### Pipes ######

class Pipe(Action):
	"""Pipe objects takes a string as inputd return the string possibly transformed. If a None is returned, the pipe work is considered as failed."""
	MAP = {}

	def __init__(self):
		Action.__init__(self)

	def process(self, input, env):
		"""Transform the string as input in the given environment.
		If None is returned, the proccessing is considered as failed."""
		passs

	def error(self):
		"""Called to explicit the last error of this pipe."""
		return None

	def declare(name, pipe):
		"""Declare a new pipe with the given name. Pipe must the constructor to the pipe class. This constructor will be invoked with a list of strings as arguments."""
		Pipe.MAP[name] = pipe

	def make(name, args):
		"""Build a pipe with the given name and arguments (list of strings)."""
		try:
			return Pipe.MAP[name](args)
		except KeyError:
			raise ParseException('no pipe named "%s"' % name)


class Make(Pipe):

	def __init__(self, args):
		self.args = args
		self.path = None

	def process(self, input, env):
		if execute("make%s" % " ".join(eval_args(self.args, env)), dir=input):
			return input
		else:
			self.path = input
			return None

	def error(self):
		return 'make failed in "%s"' % self.path

Pipe.declare("make", Make)


class Config(Pipe):

	def __init__(self, args):
		self.args = args

	def process(self, input, env):
		if not execute("%s%s" % (__file__, " ".join(eval_args(self.args, env))), dir=input):
			self.path = input
			return None
		else:
			return input

	def error(self):
		return 'configuration error in "%s"' % self.path

Pipe.declare("config", Config)


class Echo(Pipe):

	def __init__(self, args):
		self.args = args

	def process(self, input, env):
		print(*(eval_args(self.args, env) + [input]))
		return input

Pipe.declare("echo", Echo)


def from_fun(name, f, n = 0):
	"""Build a pipe from a Python function f. n is the number of parameters after the first one. The parameters passed to f is the input of the pipe followed by arguments in the pipe invocation."""
	class FromFun(Pipe):
		def __init__(self, args):
			if len(args) != n:
				raise ParseException('"%s" requires %d arguments!' % (name, n))
			self.args = args
		def process(self, input, env):
			return f(*([input] + eval_args(self.args, env)))
		def error(self):
			return '"%s%s" failed!' % (name, " ".join(self.args))
	Pipe.declare(name, FromFun)

def check_fun(name, f, n = 0):
	"""Build a pipe from a Python function f returning a boolean. f takes as parameter the input of the pipe followed by the arguments from the actual invocation. Returning true returns the input string, false returns None."""
	from_fun(name, lambda x: x if f(x) else None, n)

from_fun('/', os.path.join, 1)
from_fun('..', os.path.dirname)
from_fun('lower', str.lower)
from_fun('title', str.title)
from_fun('upper', str.upper)
from_fun('basename', os.path.basename)
from_fun('dirname', os.path.dirname)
from_fun('abspath', os.path.abspath)
from_fun('expanduser', os.path.expanduser)
from_fun('normcase', os.path.normcase)
from_fun('normpath', os.path.normpath)
from_fun('removeprefix', str.removeprefix, 1)
from_fun('removesuffix', str.removesuffix, 1)
from_fun('replace', str.replace, 2)
check_fun('isdir', os.path.isdir)
check_fun('isfile', os.path.isfile)
check_fun('islink', os.path.islink)
check_fun('exists', os.path.exists)
check_fun('startswith', str.startswith)
check_fun('endswith', str.endswith)
check_fun('contains', lambda x, y: str.find(x, y) >= 0)


class Pipeline(Pipe):

	def __init__(self, pipes):
		self.pipes = pipes

	def process(self, data, env):
		for pipe in self.pipes:
			data = pipe.process(data, env)
			if data == None:
				self.failed = pipe
				break
		return data

	def error(self):
		return self.failed.error()


###### Commands ######

class Command(Action):
	"""A command is an evaluation element at the top-level of the script. It is evaluated and, if there is no failure, is used to output Makefile definitions. In case of error, the constructor can raise ParException."""
	MAP = { }

	def __init__(self):
		Action.__init__(self)

	def process(self, env):
		"""Evaluate the command in the given environment. If the command fails, it has to call fatal() function."""
		pass

	def output(self, out):
		"""Called to generate the output file that is supposed to be included in Makefile."""
		pass

	def declare(name, command):
		"""Declare a new command (that must be prefixed by !). Command is the constructor to the actual class of the command. This constructor will be called as argument the remaining of the line as argument."""
		Command.MAP[name] = command

	def make(name, args):
		"""Build a command from name and arguments parameters."""
		try:
			return Command.MAP[name](args)
		except KeyError:
			raise ParseException('no command named "%s"' % name)


class Definition(Command):

	def __init__(self, name, type, action, comment):
		Command.__init__(self)
		self.name = name
		self.type = type
		self.action = action
		self.comment = comment

	def process(self, env):
		try:
			self.value = env[self.name]
		except KeyError:
			self.value = self.action.eval(env)
			if self.value is None:
				self.fatal()
			env[self.name] = self.value

	def output(self, out):
		if self.type == "bool" and not int(self.value):
			out.write('#')
			self.value = 1
		out.write('%s = %s\t' % (self.name, self.value))
		if self.comment != '':
			out.write('# %s' % self.comment)
		out.write('\n')

class Comment(Command):

	def __init__(self, comment):
		Command.__init__(self)
		self.comment = comment

	def output(self, out):
		if self.comment != '':
			out.write("# %s\n" % self.comment)
		else:
			out.write('\n')		

class OSInfo(Command):

	def __init__(self, args):
		Command.__init__(self)
		if args != "":
			raise ParseException("!os-info does not accept any argument!")

	def output(self, out):
		out.write('\n# OS Information\n\n')
		out.write('BYTE_ORDER = %s\n' % sys.byteorder)
		out.write('DEFAULT_ENCODING = %s\n' % sys.getdefaultencoding())
		info = OS_INFO[sys.platform]
		for line in info:
			out.write("%s\n" % line)

Command.declare('!os-info', OSInfo)


class EchoCommand(Command):

	def __init__(self, args):
		Command.__init__(self)
		self.args = args

	def process(self, env):
		print(eval_arg(self.args, env))

Command.declare('!echo', EchoCommand)


class Gen(Command):

	def __init__(self, args):
		Command.__init__(self)
		self.args = args

	def process(self, env):

		# parse args
		args = [arg.strip() for arg in eval_arg(self.args.strip(), env).split()]
		if len(args) != 2:
			self.fatal('!gen requires as argument: input output.')
		in_path = args[0]
		out_path = args[1]

		# generate the file
		try:
			with open(out_path, "w") as out:
				with open(in_path) as input:
					for l in input.readlines():
						out.write(eval_arg(l, env))
		except FileNotFoundError as e:
			self.fatal(str(e))

Command.declare('!gen', Gen)


class Include(Command):

	def __init__(self, args):
		Command.__init__(self)
		self.commands = parse_script(args.strip())

	def process(self, env):
		for command in self.commands:
			command.process(env)

	def output(self, out):
		for command in self.commands:
			command.output(out)

Command.declare('!include', Include)


###### Script parsing ######

def parse_var(num, line):
	try:
		p = line.index('=')
		name = line[:p].strip()
		value = line[p+1:].strip()

		# find name and type
		try:
			p = name.index(':')
			type = name[p+1:].strip()
			name = name[:p]
		except ValueError:
			type = "string"

		# find value and comment
		try:
			p = value.index('#')
			comment = value[p+1:]
			value = value[:p].strip()
		except ValueError:
			comment = ""

		# add the variable
		if type not in ['string', 'bool', 'int', 'path']:
			fatal("unknown type %s" % type, source=num)
		return (name, type, value, comment)
		
	except ValueError:
		self.fatal("garbage here!")


def parse_source(num, action):
	if not action.startswith('!'):
		return Const(action.strip())
	else:
		args = [arg.strip() for arg in action.split()]
		try:
			return Source.make(args[0], args[1:])
		except ParseException as e:
			fatal(str(e), source=num)


def parse_pipe(num, action):
	args = [arg.strip() for arg in action.split()]
	if len(args) == 0:
		fatal("empty pipe action", source=num)
	try:
		return Pipe.make(args[0], args[1:])
	except ParseException as e:
		fatal(str(e), source=num)


def parse_pipeline(num, action):
	actions = [arg for arg in action.split('|')]
	return Pipeline([parse_pipe(num, pipe) for pipe in actions])


def parse_chain(num, action):
	try:
		p = action.index('|')
		source = parse_source(num, action[:p])
		pipeline = parse_pipeline(num, action[p+1:])
		return Chain(source, pipeline)
	except ValueError:
		return parse_source(num, action)


def parse_check(num, action):
	actions = [arg for arg in action.split('&')]
	source = parse_chain(num, actions[0])
	if len(actions) == 1:
		return source
	else:
		try:
			return Check(source, [parse_pipeline(num, pipe) for pipe in actions[1:]])
		except ParseException as e:
			fatal(str(e), source=num)


def parse_alts(num, action):
	alts = [alt for alt in action.split("||")]
	if len(alts) == 0:
		raise ParseException("empty default value")
	elif len(alts) == 1:
		return parse_check(num, action)
	else:
		return Alt([parse_check(num, alt) for alt in alts])




# parse the script
def parse_script(path):
	commands = []

	with open(path) as input:
		num = 0
		pref = ""
		for l in input.readlines():
			num = num + 1
			l = l.strip()
			if l == "":
				continue
			if l.endswith('\\'):
				pref += l[:-1]
				continue
			l = pref + l
			pref = ''
			if l.startswith("#"):
				command = Comment(l[1:])
			elif l.startswith('!'):
				match = SPACE_RE.search(l)
				if match is None:
					command = l
					args = ""
				else:
					command = l[:match.start()]
					args = l[match.end():]
				try:
					command = Command.make(command, args)
				except ParseException as e:
					fatal(str(e), num)
			else:
				name, type, action, comment = parse_var((path, num), l)
				try:
					action = parse_alts((path, num), action)
				except ParseException as e:
					fatal(str(e), source=num)
				command = Definition(name, type, action, comment)
				
			commands.append(command)
			command.set_source(path, num)

	return commands


def run():
	
	# process arguments
	parser = argparse.ArgumentParser(
		prog="config",
		description="generate configuration to include inbn Makefile.",
		usage="call config.py in a directory containg config.in"
	)
	parser.add_argument('defs', nargs='*', help="definitions to include in the configuration")
	parser.add_argument('-q', '--quiet', action='store_true', help='enable quiet mode.')
	parser.add_argument('--os-info', action='store_true', help='generate OS information definitions.')
	parser.add_argument('--log', nargs='?', const="config.log", help="create log (default to config.log).")
	parser.add_argument('--input', '-i', default='config.in', help="script taken as input.")
	parser.add_argument('--output', '-o', default='config.mk', help="generated file as output.")

	args = parser.parse_args()
	if args.quiet:
		QUIET = True
		STDOUT = subprocess.DEVNULL
	if args.log:
		out = open(args.log, "w")
		STDOUT = out
		STDERR = out
		LOGGING = True
	input_path = args.input
	output_path = args.output

	# build environment
	env = dict(os.environ)
	for arg in args.defs:
		try:
			p = arg.index('=')
			name = arg[:p].strip()
			value = arg[p+1:].strip()
			env[name] = value
		except ValueError:
			fatal(None, "bad argument %s" % arg)

	# parse the scripts
	commands = parse_script(input_path)

	# evaluate the script
	for command in commands:
		command.process(env)

	# generate
	with open(output_path, "w") as out:
		for command in commands:
			command.output(out)
	
	info("configuration generated in '%s'" % output_path)


if __name__ == '__main__':
	run()

	
