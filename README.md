# SIS-INSTALL

sis-install.py is a multi-platform Simple Install System supporting:
* projects split in multiple packages,
* dependency management between packages,
* source or binary package distribution,
* local or global installation,
* local storage of the configuration,
* remote storage of the package index,
* XML-based storage of the package configuration (easy to fix),
* user management of packages installed locally.

In addition, sis-install is very light (about ~1500 lines of code) and
has minimal requirements on the host platform (a V2.0 Python interpreter).

If you develop a framework or a software supporting lots of extensions,
sis-install may be a solution to achieve (a) easy setup of your packages,
(b) user level installation and (c) independency to host package system.



## Installation Model

sis-install provides binary or source installation. Basically, sis-install
uses three XML databases:
* the local database (lDB) contains information on installed packages,
* the source database (sDB) contains generic information and packages
  and possibly, instructions to build a package from sources,
* the binary database (bDB) contains the list of packages for which
a binary distribution is provided.

When sis-install starts, it loads lDB and sDB and, if available, the bDB.
The lDB is found from a path stored in the sis-install.py script: if you
use a path that is relative to the install script, you can obtain a relocatable
installation (and if the installed packages support this). Then, the sDB
is obtained using a URL (that is also configured in the script) augmented
by a file named ''index.xml''. Finally, the URL is augmented by a directory
name corresponding to the host OS (using the table below) and ''index.xml''
to get the binary packages.

| OS      | machine    | directory      |
+---------+------------+----------------+
| Linux   | x86 32-bit | linux-x86      |
| Linux   | x86 64-bit | linux-x86_64   |
| Windows | x86 32-bit | win            |
| Windows | x86 64-bit | win64          |
| Mac OSX | x86 64-it  | darwin-x86_64  |

The three databases, lDB, sDB and bDB use the same XML format and contain
description of the packages, each package enriching the generic database.
The DTD of the database is provided with the distribution but you look
to an excerpt below:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<sis-extend>

	<package id="otawa-sparc">
		<desc>OTAWA loader for Sparc instruction set</desc>
		<copyright>Copyright (c) 2016, University of Toulouse</copyright>
		<license ref="https://www.gnu.org/licenses/lgpl.html">LGPLv3</license>
		<category>tool</category>
		<web>http://www.otawa.fr</web>
		<contact>mailto:otawa@irit.fr</contact>
		
		<req name="sparc"/>
		<req name="otawa"/>
		
		<version number="1.0">
			<file>otawa-sparc-161114-linux-x86_64.tar.bz2</file>
			<size>192175</size>
			<checksum>1b5bb23ce5e071722ff3248d1861e8b7</checksum>
		</version>

		<build>
			<dep name="c++"/>
			<download type="hg" address="https://anon:ok@wwwsecu.irit.fr/hg/TRACES/otawa-sparc/trunk"/>
			<make type="cmake" flags="-DOTAWA_CONFIG=$(top_dir)/bin/otawa-config"/>
		</build>
	</package>

	...

</sis-extend>
```

Here, we have a package named `otawa-sparc` for which a description,
copyright, license and contact are given. It requires two other packages:
`sparc` and `otawa`. It may be provided either as a binary in version
1.0 for which file name, size and checksum are provided. Or as a source
build using C++ compiler, downloaded as a Mercurial archive and build
using CMake. The file entry can contain an absolute path, or a path
relative to the bDB directory.

In fact, such a database is usually split between the description and
build part in sDB and the version part in in bDB. The cDB contains the
list of installed packages (with their version) and, possibly, the list
of actions to perform to uninstall a package.


## Using sis-install.py

sis-install is a standalone package: you have just to configure some
constants at the head of the script and distribute it as is to let any
use to play with your sofware.

Basically, one has to prepare the directory that will contain the installation,
let name it TOP_DIR:

```sh
./sys-install.py -R TOP_DIR
```

In addition, it will install itself in _TOP_DIR_/`bin` to let the user
have access to it for subsequent extension of the installation. It will
also prepare the lDB. From now, the user must invoke the sis-install.py
of the installation.

Now, the user can ask to see the list of available packages:
```sh
TOP_DIR/bin/sys-install.py -l
```


To get details on the package named _PACK_, the user can type:
```sh
TOP_DIR/bin/sys-install.py -i PACK
```

Now, a package _PACK_ can be installed with:
```sh
TOP_DIR/bin/sys-install.py PACK
```

Depending on the available version in the database, a binary version
is loaded if available, otherwise the source version will be installed.
If _PACK_ requires other packages, they will be installed as well.

If a specific _VERSION_ is required, an alternative syntax is:
```sh
TOP_DIR/bin/sys-install.py PACK:VERSION
```

To uninstall a package _PACK_, just type:
```sh
TOP_DIR/bin/sys-install.py -u PACK
```

Alternatively, if you do not want the user to be bothered by sis-install.py
in or outside the installation, you can prepare the database and install
a package with:
```sh
./sys-install.py -R TOP_DIR PACK
```


## Building a database

Basically, you have to select a server to store the databases and the
packages in. A very common way to do this is to use an HTTP server
and access it using ``http://`` or ``https://`` protocols. Additionnaly,
the sources must also be available be available on their own server
(typically using a VCS).

Let the URL be the URL of the resource directory that will be contains
the ``index.xml``. First, create and store the ``index.xml`` file (DB)
on the corresponding server:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<sis-extend>
...
</sis-extend>
```

Replace the `...` by the list of your packages using the following format:
```xml
<package id="PACK">
	<desc>DESC</desc>
	<copyright>COPYRIGHT</copyright>
	<license ref="LREF">LICENSE</license>
	<category>CATEGORY</category>
	<web>WEB</web>
	<contact>EMAIL</contact>
	
	REQUIREMENTS
	
</package>
```

All the entries in the `<package>` is optional. They means:
* PACK_ -- package identifier used througout the installation commands,
* DESC_ -- humand-redable description of the package,
* COPYRIGHT_ -- owner of the copyright of the package, something like
  `copyright (c) YEAR - OWNER`
* _CATEGORY_ -- anything you want, it may be used to sort the packages,
* _WEB_ -- web address to get information on the package,
* _EMAIL_ -- email address of a contact to get in touch with the developers.

The _REQUIREMENTS_ provide the list of packages on which the package
depends. In order to install this package, the packages in the requirements
must be installed first. The requirements element have the following format:
```xml
<req name="RPACK"/>
```
With _RPACK_ the identifier of the required package.

In the following, will be presented the documentation of a source and
of a binary package.


## Source Distribution

To describe a source distribution, one has to include in the package
a `build` element:
```xml
<package id="PACK">
	...
	<build>
		DEPS
		<download .../>
		<make .../>
	</build>
</package>
```

The _DEPS_ lists the dependencies, tool and libraries, that are required
to build the package from the sources. A dependency may be a dependency
automatically provided by sis-install:
```xml
<dep name="ID"/>
```

Where possible ID values:
* ''bzip2'' -- bzip2 compresser,
* ''c++'' -- C++ compiler,
* ''cc'' -- C compiler,
* ''cmake'' -- CMake utility,
* ''gzip'' -- gzip compresser,
* ''hg'' -- Mercurial VCS,
* ''make'' -- GNU make utility,
* ''tar'' -- tar archive command,
* ''unrar'' -- RAR compresser,
* ''unzip'' -- ZIP compresser.

A particular command _CMD_ to look for can be looked:
```xml
<dep name="CMD" type="command"  commands="CMD"/>
```

A library _LIB_ and its compiling components (header file _HEADER_) can be
tested:
```xml
<dep name="LIB" type="library" header="HEADER" lang="LANG" cflags="CFLAGS" ldflags="LDFLAGS"/>
```

_CFLAGS_ and _LDFLAGS_ are commands executed in a shell that will provide
command line options to compile and to link with the library. _LANG_
selects the programming language of the library, ''c'' or ''c++''.
_HEADER_, _LANG_, _CFLAGS_ and _LDFLAGS_ are optional.

The `download` element provides information to download the sources.

GIT repository can be downloaded with:
```xml
<download type="git" address="ADDRESS"/>
```
Where _ADDRESS_ is the address to access the resource on a GIT server.

Mercurial repository can be downloaded with:
```xml
<download type="hg" address="ADDRESS"/>
```
Where _ADDRESS_ is the address to access the resource on a Mercurial server.

Source can also be downloaded and extractet from an archive:
```xml
<download type="archive"  address="URL"/>
```
The _URL_ must points to an archive file that will be downloaded and 
decompacted. The obtained directory must have as name the file name
of the archive without the archive extension.

The `make` element provides information about the build of the package.
To build a package using the CMake system, the following command must
be given:
```xml
<make type="cmake" flags="FLAGS" />
```
_FLAGS_ is a list of CMake flags passed to the `cmake` command at setup
time of the sources.

A simple GNU may also be used:
```xml
<make type="make" flags="FLAGS"/>
```
_FLAGS_ is a list of flags passed at invocation of `make` command.
The Makefile must at least implement two goals: `all` to perform
the build and `install` to perform the installation.

Finally, a custom command can be used:
```xml
<make type="command" build="COMMAND"/>
```
With _COMMAND_ the shell command to invoke to perform the build. The CWD
of this invocation is the directory containing the sources.

All attributes of `download` and `make` elements (except `type`)
can contains special variables with names between `$(` and `)`:
  * `$(top_dir)` -- top directory of the installation (_TOP_DIR_)

In addition, the source directory **may** contain a text file named `VERSION`
that must contain the current version of the sources and will be used
to identify and to store the current version of the package.


## Binary Distribution

To distribute binary packages for an architecture _ARCH_, you have to create
a directory named _URL/ARCH_ on the distribution server. It must contain
a file named `index.xml` with the following format:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<sis-extend>
	...
</sis-extend>
```

For each package for which one or several binary distribution is
available, an entry of the form must be created:
```xml
<package id="PACK">
	...
</package>
```
Where _PACK_ is the identifier of the package. It is not mandatory
but it would be more informative to have the corresponding package
definition in the DB.

Inside the package, one can declare or several binary versions:
```xml
<version number="VERSION">
	<file>PATH</file>
	<size>SIZE</size>
	<checksum>CHECKSUM</checksum>
</version>
```
Where:
  * _VERSION_ -- version of the binary distribution,
  * _PATH_ -- path to the binary package (if relative, relative to URL/ARCH),
  * _SIZE_ (optional) -- size in byte of the package,
  * _CHECKSUM_ (optional) -- MD5 checksum for validation.

The acceted archive format format includes:
  * `.tar.gz`
  * `.tar.bz2`
  * `.zip`
  * `.rar`

Once uncompressed, the obtained directory must have for name the name
of the archive without the extension. It must contain, at top level,
a file named `install.xml` which format is:
```xml
<sis-install>
	...
</sis-install>
```
The `...` must be replaced by a list of actions required to perform
the installation. This may be an `install` action on a plain file:
```xml
	<install file="PATH"/>
```
The _PATH_ must be relative to the package directory and will be installed
using the same relative path in the installation top directory.

The form below provides installation for a dynamic library (the dynamic
library extension will be provided automatically by sis-install):
```xml
	<install dynlib="PATH"/>
```

Optionally, the `install` element accepts also an attribute `to`
providing a path to install the file or the dynamic library. If relative,
this path is composed with _TOP_DIR_.

Finally, the action may include a removal action:
```xml
	<remove path="PATH"/>
```
The directory or the file pointed by _PATH_ will be removed. It may be
an absolute path or a relative path to _TOP_DIR_.



## Customizing the script the script

To meet your needs, you have to set up some constants inside the script
before distributing it.  This constants are initialized at the head
of the script. They have the following meaning:
* `APP` -- name of your application,
* `DB_URL` -- URL containing the `index.xml` implementing sDB,
* `DB_TOP` -- relative path to find TOP_DIR from the directory
  containing the script (unused when option -R is used),
* `DB_CONF` -- path to the configuration database lDB, relative
to _TOP_DIR_.

In addition, some constants may be customized:
  * `VERSION` -- name of the version file in the source directory
  * `SIS_EXTEND_TAG` -- tag name of the XML database,
  * `SIS_INSTALL_TAG` -- tag name of the install XML file.

For a default configuration (sis-install installed in the `bin`
directory of TOP_DIR), you can use:
```python
APP		= ""
DB_URL	= "URL"
DB_TOP	= ".."
DB_CONF	= "install.xml"
```


## Extending the script

Currently, sis-install provided a rather limited set of download,
build and action options. Yet, with very few lines of Python code,
you can add the support of your preferred tools. The section provides
some help on the sis-install infrastructure to perform this extension.

Interesting base classes includes:
* `Action` -- installation actions for binary distrubtion ``install.xml``,
* `Dep` -- dependencies of the source distribution,
* `Download` -- downloader of the source distribution,
* `Build` -- maker of the source distribution.

The instances of these classes are built from identifier found the used
XML files. To be used, the extended classes must be recorded in maps:
* `ACTIONS` for actions,
* `dep_makers` for dependencies,
* `DOWNLOADERS` for downloaders,
* `BUILDERS` for makers.

Whatever the extension you want to develop, most of classes and methods
are documented and this documentation may be obtained using:
```sh
epydoc --html sis-install.py -o autodoc 
```

I will be happy to reveives your patches to extend **sis-install**. 


## Future developments

sis-install, in this version, provides the basic functionalities of an
installation system. But I plan to augment its features:

[ ] more installation actions,

[ ] more download options,

[ ] more build and install options,

[ ] more checksum options,

[ ] management of version in the binary packages,

[ ] improved UI (progress bar for download, build or installation),

[ ] helper tool to build the install.xml of the binary package,

[ ] more options to sis-install for more control of the process.

For more details, contact me at [hug.casse@gmail.com](matilo:hug.casse@gmail.com).
