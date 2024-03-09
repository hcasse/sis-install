# Simple Installation System

**SIS** is now made of 2 Python's scripts one for helping in installation, the other for making simpler the configuration of an application before building.

The philosophy of both tools :

* portability - this is why they are developed in Python,
* simplicity - opposition to complex and heavy systems to turn back to simple and embeddable scripts.

Another consequence is that there is no building or installation script for them: they are made, and are small enough, to be duplicated, published or embedded in  source repositories.

The tools are:

* `sis-install.py` -- light installation system supporting binary or source distribution with network-based index file.
* `config.py` -- a-la **Make** configuration system producing a file that may be included in `Makefi`.

Details about the scripts can be found in `doc` directory.

Automatic-documentation can be generated with (under command line and in **SIS** directory):

```sh
$ export PYTHONPATH=$PYTHONPATH:$PWD
$ pydoc3 -b
```
that opens a documentation page.

Both tools are distributed under **GPL v3** open-source license (in `LICENSE`).

For any remark, bug or question, feel free to send an email to mailto:hug.casse@gmail.com.

