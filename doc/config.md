# SIS Config

**SIS Config** is a simple Python 3 script helping application in their configuration phase. It may be viewed as a replacement of some features of **CMake** or of **autotools** while keeping the full expressivity power and simplicity of **Make**.

It s first function is to generate a file `config.mk` from a template `config.in` containing configuration of the human user and portability definitions to make **Make** more portable. In the choice of its syntax, **SIS config** try to be as close as possible to **Make** but in the same time, to be as light as possible to be embedded in the source repository. The goal is that the builder of an application has no more dependeny except **Make** and the programming language support.



## Usage

The basic way to invoke **SIS Config** is to type:

```sh
$ ./config.py
```

It will automatically takes as output `config.in` and complain if it does noy exist and produces its output in file `config.mk`. This file can then be included at the head of a classical `Makefile`:

```makefile
include config.mk
```

And the `Makefile` can benefit from the definitions inside `config.mk`.



## config.in syntax

As `Makefile`, `config.in` has a line-oriented syntax with a logical line spanning over lines by suffixing each line with `\`.

Thereafter, the _output file_ or _output_ is `config.mk` unless configured otherwise at **SIS Config** call.

The lines may have the following formats:

* ` ` (empty line) -- just ignored and not copied to the output.
* `#...` (comment line) -- copied as-is to the output.
* `!command arguments!` -- invoke the given command with the given arguments.
* `IDENTIFER:TYPE = EXPRESSION  #  comment` -- add a definition the given _identifier_ and the given _expression_. The expression is evaluated and the definition is written back to the output with the component.

Comments alone or at the end of a definition are very important as `command.mk` file supposed to be fixed by the user. Therefore, they are copied in the output.

_Identifier_ is any list of symbols not containing spaces, `:`, `=` or `#`. In addition, they can not start with `!`.

_Type_ is optional and will be used to help editing or better outputting the result of the expressions. Current _types_ encompasses `bool`, `int`, `str` and `path`. Currently, the main processing of types if for `bool`: the definition is commented if its value is false.


The _expression_ can have two main form:
* a _checked expression_ producing a string,
* a `||` separated list of _checked expressions_ : the _check expressions_ are tested in turn until producing a value.

The code below assign `dir` to `DIR1` and depending on the existence of the directory `dir2`, assign `dir2` or `dir3`:

```
DIR1 = dir1
DIR2 = dir2 | isdir || dir3
```

`isdir` is a filter that break the evaluation if the input string, `dir2`, is not a valid existing directory.


A _checked expression_ can have also two forms:
* a _chain expression_ producing a string,
* a _chain expression_ separated by one or several _filter chains_ prefixed by `&`.

In the second form, the _chain expression_ produces a string that is checked against all _filter chains_ and the evaluation fails if one of the _filter chains_ fails. In case of success, the string of _chain_ expression is returned.

The example returns directory `dir` if it contains a file named `file.txt`:

```
DIR = dir & / file.txt | isfile
```
Otherwise the configuration fails.


A _chain expression_ is some expression producing a value that may be changed by a _filter chain_. The example below look for the directory path of an executable in the given list and then returns it with character in upper case:

```
EXEC = !which cc gcc clang | upper | dirname
```

A _chain expression_ is made of a _source_, something producing a string followed by a _filter chain_ that may test or tranform the generated string. _source_ may a simple string or a command introduced by a `!` and possibly continued space-separated arguments.

On the other hand, a _filter chain_ is a list of commands separated by `|` possibly with one or several arguments. They cover two main roles:
* transform the string result in a new string,
* check the string: if true the string is returned, if false an error is raised.

Sections below gives the list of _commands_, _sources_ and _filters_.

In addition, the string part of the command can support variable evaluation with the following syntax:
* `$(IDENTIFIER)` is replaced by the value of the variable (identifier may be any character except `)`,
* `$IDENTIFIER` is replaced by the value of the variable (identifier may be any character except space and `$`,
* `$$` is a replaced by a single `$`.



## Available Filters

### Text Filters

With these filter, the input is considered a plain text.

* `contains` _WORD_ - check that the input contains _WORD_.
* `endswith` _WORD_ - check that input ends with _WORD_.
* `lower` - transform to lowercase the input.
* `removeprefix` _PREF_ - remove _PREF_ from input.
* `removesuffix` _PREF_ - remove _PREF_ from input.
* `replace` _LWORD_ _RWORD_ - replace in input any instance of _LWORD_ by _RWORD_.
* `startswith` _WORD_ - check that input starts with _WORD_.
* `title`- set to uppercase first word letter of the input.
* `uppder` - transform to uppercase the input.

### Path Filters

In these filters, the input is considered as a path.

* `/` _ARG_ - join the name _ARG_ to the input.
* `..` - get the parent directory.
* `basename` - return the rightmost component.
* `dirname` - return all except the rightmost component.
* `exists` - test if the input is a path to an existing element of the file system.
* `expanduser` - replace ~_user_ by its home path.
* `normcase` - normalize the case according to the OS.
* `normpath` - normalize the path separators according to the OS.
* `isdir` - test if the input is a path to a directory.
* `isfile` - test if the input is a path to a plain file.
* `islink` - test if the input is a path to a link file.

### Command Filters

These filters uses the input to apply a command on it. If successul, the input is propagated. Otherwise an error is rised.

* `config` _ARGS_ - call `config.py` itself with _ARG_ on the directory given by input.
* `echo` _ARGS_ - display _ARGS_ followed by the input (useful for debugging).
* `make` _ARGS_ - call `make` in the directory whose path is input. Fails if `make` fails. _ARGS_ are passed to `make` as is.



## Available Sources

Sources produces a string, often a path, that are assigned to variables, possibly after passing by filters.

* `!git` _URL_ - clone with **Git** the repository corresponding to _URL_ and return the path to the repository.
* `!lookup` _ARGS_ - look for a file item matching one of the _ARGS_ relatively to the current directory and return it.
* `!which` _ARGS_ - look for an execuble matching one of the _ARGS_ in the system list of executable paths and return it.


## Available Commands

In place of definitions and comments, `!`-prefixed are also supported:

* `!echo` _ARGS_ - display _ARGS_ at the definition evaluation time.
* `!gen` _INPUT_ _OUTPUT_ - generate _OUTPUT_ file from _INPUT_ file that may contain `$`-prefixed variables with the definitions produced in `config.mk`.
* `!import` _PATH_ - import a Python script used to add new pipes, sources and commands. The Python script has just to define classes for these action and add the `declare` class function to make these action available.
* `!include` _PATH_ - include another script in the current script.
* `!os-info` - generate a list of definitions providing information about OS and providing portability definitions (see below for the provided definitions).





