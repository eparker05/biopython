# Copyright 2009-2011 by Peter Cock.  All rights reserved.
# This code is part of the Biopython distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.
"""Lazy parsing and feature indexing of sequence files (PRIVATE).

You are not expected to access this module, or any of its code, directly. This
is all handled internally by the following functions when accessed with the
lazy=True kwarg.
Bio.SeqIO.parse(.... lazy=True)
Bio.SeqIO.index(..., lazy=True)
Bio.SeqIO.read(..., lazy=True) 


The lazy loading parsers will read an entire record efficiently storing and 
parsing only the mimimum amount of information to provide fast lookup. Records
returned from parse(), index(), and read() will act as a proxy to a regular 
SeqRecord class.

The lazy loading strategy is, for large sequences, faster to initialize than
SeqIO.parse() and more memory efficient. It is slower to initialize than
SeqIO.index() but also more memory efficient.

The lazy loader will partially parse a sequence file noting the sequence
span and file position of sequence annoations. These annotations will
be stored for efficient retrieval from the file when requested. Sequence 
data will also be efficiently pulled from structured regions
and file

Note that this means all parsing is on demand, so improperly formatted
records may not trigger an exception unless the problem region is requested.
This is by design.
"""
