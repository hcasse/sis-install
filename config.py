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
OUTPUT_PATH = "config.mk"
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

def fatal(num, message):
	if num == None:
		sys.stderr.write("ERROR: %s\n" % message)
	else:
		sys.stderr.write("ERROR: config.in:%d: %s\n" % (num, message))
	exit(1)

def info(message):
	if not QUIET:
		sys.stdout.write("INFO: %s\n" % message)
	if LOGGING:
		STDOUT.write("INFO: %s\n" % message)
		STDOUT.flush()

def execute(cmd, dir = None):
	if dir == None:
		dir = os.getcwd()
	cp = subprocess.run(cmd, shell=True, cwd = dir, stdout=STDOUT, stderr=STDERR)
	return cp.returncode == 0

VAR_RE = re.compile('\$\$|\$\(([^\)]+)\)|\$(\S+)')

def eval_arg(text, map):
	res = ''
	match = VAR_RE.search(text)
	while match is not None:
		res += text[:match.start()]
		found = match.groups()[0]
		if found == None:
			res += '$'
		else:
			try:
				res += map[found]
			except KeyError:
				pass
		text = text[match.end():]  
		match = VAR_RE.search(text)
	return res + text


def eval_args(args, map):
	return [eval_arg(arg, map) for arg in args]

class ConfigException(Exception):

	def __init__(self, msg):
		self.msg = msg

	def __str__(self):
		return self.msg
	
class ParseException(ConfigException):

	def __init__(self, msg):
		ConfigException.__init__(self, msg)


###### Sources ######

class Source:
	MAP = {}

	def eval(self, env):
		return None

	def error(self):
		return None

	def declare(name, source):
		Source.MAP[name] = source

	def make(name, args):
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

class Pipe:
	MAP = {}

	def process(self, input, env):
		passs

	def error(self):
		return None

	def declare(name, pipe):
		Pipe.MAP[name] = pipe

	def make(name, args):
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
	class FromFun(Pipe):
		def __init__(self, args):
			if len(args) != n:
				raise ParseException('"%s" requires %d arguments!' % (name, n))
			self.args = args
		def process(self, input, eval):
			return f(*([input] + eval_args(self.args, env)))
		def error(self):
			return '"%s%s" failed!' % (name, " ".join(self.args))
	Pipe.declare(name, FromFun)

def check_fun(name, f, n = 0):
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

class Command:
	MAP = { }

	def process(self, env):
		pass

	def output(self, out):
		pass

	def declare(name, command):
		Command.MAP[name] = command

	def make(name, args):
		try:
			return Command.MAP[name](args)
		except KeyError:
			raise ParseException('no command named "%s"' % name)


class Definition(Command):

	def __init__(self, name, type, action, comment):
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
				fatal(self.num, self.action.error())
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
		self.comment = comment

	def output(self, out):
		if self.comment != '':
			out.write("# %s\n" % self.comment)
		else:
			out.write('\n')		

class OSInfo(Command):

	def __init__(self, args):
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
		self.args = args

	def process(self, env):
		print(eval_arg(self.args, env))

Command.declare('!echo', EchoCommand)


class Gen(Command):

	def __init__(self, args):
		self.args = args

	def process(self, env):

		# parse args
		args = [arg.strip() for arg in eval_arg(self.args.strip(), env).split()]
		if len(args) != 2:
			fatal(self.num, '!gen requires as argument: input output.')
		in_path = args[0]
		out_path = args[1]

		# generate the file
		try:
			with open(out_path, "w") as out:
				with open(in_path) as input:
					for l in input.readlines():
						out.write(eval_arg(l, env))
		except FileNotFoundError as e:
			fatal(self.num, str(e))

Command.declare('!gen', Gen)


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
			fatal(num, "unknown type %s" % type)
		return (name, type, value, comment)
		
	except ValueError:
		fatal(num, "garbage here!")


def parse_source(num, action):
	if not action.startswith('!'):
		return Const(action.strip())
	else:
		args = [arg.strip() for arg in action.split()]
		try:
			return Source.make(args[0], args[1:])
		except ParseException as e:
			fatal(num, str(e))


def parse_pipe(num, action):
	args = [arg.strip() for arg in action.split()]
	if len(args) == 0:
		fatal(num, "empty pipe action")
	try:
		return Pipe.make(args[0], args[1:])
	except ParseException as e:
		fatal(num, str(e))


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
			fatal(num, str(e))


def parse_alts(num, action):
	alts = [alt for alt in action.split("||")]
	if len(alts) == 0:
		raise ParseException("empty default value")
	elif len(alts) == 1:
		return parse_check(num, action)
	else:
		return Alt([parse_check(num, alt) for alt in alts])


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

args = parser.parse_args()
if args.quiet:
	QUIET = True
	STDOUT = subprocess.DEVNULL
if args.log:
	out = open(args.log, "w")
	STDOUT = out
	STDERR = out
	LOGGING = True


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


# command supports
COMMANDS = []

def add_command(num, command):
	command.num = num
	COMMANDS.append(command)

# parse the script
with open("config.in") as input:
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
			add_command(num, Comment(l[1:]))
		elif l.startswith('!'):
			match = SPACE_RE.search(l)
			if match is None:
				command = l
				args = ""
			else:
				command = l[:match.start()]
				args = l[match.end():]
			try:
				add_command(num, Command.make(command, args))
			except ParseException as e:
				fatal(num, str(e))
		else:
			name, type, action, comment = parse_var(num, l)
			try:
				action = parse_alts(num, action)
			except ParseException as e:
				fatal(num, str(e))
			add_command(num, Definition(name, type, action, comment))


# evaluate the script
for command in COMMANDS:
	command.process(env)

# generate
with open(OUTPUT_PATH, "w") as out:
	for command in COMMANDS:
		command.output(out)
	
info("configuration generated in '%s'" % OUTPUT_PATH)

