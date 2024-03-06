#!/usr/bin/env python3

import argparse
import os
import os.path
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


class Source:

	def eval(self):
		return None

	def error(self):
		return None


class Const(Source):

	def __init__(self, value):
		self.value = value

	def eval(self):
		return self.value


class Which(Source):

	def __init__(self, cmds):
		self.cmds = cmds

	def eval(self):
		for cmd in self.cmds:
			path = shutil.which(cmd)
			if path is not None:
				return path
		return None

	def error(self):
		return "canot find one command of %s." % ", ".join(self.cmds)


class Look(Source):

	def __init__(self, paths):
		self.paths = paths

	def eval(self):
		for path in self.paths:
			if os.path.exists(path):
				return path
		return None

	def error(self):
		return "cannot find one path of %s." % ", ".join(self.paths)


class Git(Source):

	def __init__(self, args):
		if len(args) != 1:
			raise OSError("!git requires exacly 1 argument!")
		self.url = args[0]
		try:
			p = self.url.rindex('/')
			self.path = self.url[p+1:-4]
		except ValueError:
			raise OSError('malformed URL "%s"' % self.url)

	def eval(self):
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


class Alt(Source):

	def __init__(self, alts):
		self.alts = alts

	def eval(self):
		for alt in self.alts:
			res = alt.eval()
			if res is not None:
				return res
		return None

	def error(self):
		return "all alternatives failed:\n* %s\n" \
			% "\n* ".join([alt.error() for alt in self.alts])


class Pipe:

	def process(self, input):
		pass

	def error(self):
		return None


class Make(Pipe):

	def __init__(self, args):
		self.args = args
		self.path = None

	def process(self, input):
		if execute("make%s" % " ".join(self.args), dir=input):
			return input
		else:
			self.path = input
			return None

	def error(self):
		return 'make failed in "%s"' % self.path


class Config(Pipe):

	def __init__(self, args):
		self.args = args

	def process(self, input):
		if not execute("%s%s" % (__file__, " ".join(self.args)), dir=input):
			self.path = input
			return None
		else:
			return input

	def error(self):
		return 'configuration error in "%s"' % self.path
	

class Chain(Source):

	def __init__(self, source, pipes):
		self.source = source
		self.pipes = pipes
		self.failed = None

	def eval(self):
		value = self.source.eval()
		if value is None:
			self.failed = self.source
			return None
		for pipe in self.pipes:
			value = pipe.process(value)
			if value is None:
				self.failed = pipe
				return None
		return value

	def error(self):
		return self.failed.error()


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


class Command:

	def process(self, env):
		pass

	def output(self, out):
		pass

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
			self.value = self.action.eval()
			if self.value is None:
				fatal(num, self.action.error())

	def output(self, out):
		if self.type == "bool" and not int(self.value):
			out.write('#')
			self.value = 1
		out.write('%s = %s\t# %s\n' % (self.name, self.value, self.comment))

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
		if args != []:
			raise OSError("!os-info does not accept any argument!")

	def output(self, out):
		out.write('\n# OS Information\n\n')
		out.write('BYTE_ORDER = %s\n' % sys.byteorder)
		out.write('DEFAULT_ENCODING = %s\n' % sys.getdefaultencoding())
		info = OS_INFO[sys.platform]
		for line in info:
			out.write("%s\n" % line)


SOURCES = {
	"!git": Git,
	"!look": Look,
	"!which": Which
}

def parse_source(num, action):
	if not action.startswith('!'):
		return Const(action)
	else:
		args = action.split()
		try:
			return SOURCES[args[0]](args[1:])
		except KeyError:
			fatal(num, "unknown action %s" % args[0])


PIPES = {
	"config": Config,
	"make": Make
}

def parse_pipe(action):
	args = action.split()
	if len(args) == 0:
		fatal(num, "empty pipe action")
	try:
		return PIPES[args[0]](args[1:])
	except KeyError:
		fatal(num, 'unknown pipe "%s"' % args[0])

def parse_chain(num, action):
	actions = action.split('&')
	source = parse_source(num, actions[0])
	if len(actions) == 1:
		return source
	else:
		return Chain(source, [parse_pipe(pipe.strip()) for pipe in actions[1:]])

def parse_alts(num, action):
	alts = action.split("||")
	if len(alts) == 0:
		fatal(num, "empty default value")
	elif len(alts) == 1:
		return parse_chain(num, action)
	else:
		return Alt([parse_chain(num, alt.strip()) for alt in alts])


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
env = { }
for arg in args.defs:
	try:
		p = arg.index('=')
		name = arg[:p].strip()
		value = arg[p+1:].strip()
		env[name] = value
	except ValueError:
		fatal(None, "bad argument %s" % arg)


# parse the script
TOP_COMMANDS = {
	"!os-info": OSInfo
}

COMMANDS = []
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
			COMMANDS.append(Comment(l[1:]))
		elif l.startswith('!'):
			args = l.split()
			try:
				COMMANDS.append(TOP_COMMANDS[args[0]](args[1:]))
			except KeyError:
				fatal(num, 'command "%s" is unknown!' % args[0])
		else:
			name, type, action, comment = parse_var(num, l)
			try:
				action = parse_alts(num, action)
			except OSError as e:
				fatal(num, str(e))
			COMMANDS.append(Definition(name, type, action, comment))


# evaluate the script
for command in COMMANDS:
	command.process(env)

# generate
with open(OUTPUT_PATH, "w") as out:
	for command in COMMANDS:
		command.output(out)
	
info("configuration generated in '%s'" % OUTPUT_PATH)

