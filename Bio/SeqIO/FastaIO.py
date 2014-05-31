# Copyright 2006-2009 by Peter Cock.  All rights reserved.
# This code is part of the Biopython distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.
#
# This module is for reading and writing FASTA format files as SeqRecord
# objects.  The code is partly inspired  by earlier Biopython modules,
# Bio.Fasta.* and the now deprecated Bio.SeqIO.FASTA

"""Bio.SeqIO support for the "fasta" (aka FastA or Pearson) file format.

You are expected to use this module via the Bio.SeqIO functions."""

from __future__ import print_function

from Bio.Alphabet import single_letter_alphabet
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqIO.Interfaces import SequentialSequenceWriter
from Bio._py3k import _bytes_to_string, _as_bytes
from ._lazy import SeqRecordProxyBase


def SimpleFastaParser(handle):
    """Generator function to iterate over Fasta records (as string tuples).

    For each record a tuple of two strings is returned, the FASTA title
    line (without the leading '>' character), and the sequence (with any
    whitespace removed). The title line is not divided up into an
    identifier (the first word) and comment or description.

    >>> with open("Fasta/dups.fasta") as handle:
    ...     for values in SimpleFastaParser(handle):
    ...         print(values)
    ...
    ('alpha', 'ACGTA')
    ('beta', 'CGTC')
    ('gamma', 'CCGCC')
    ('alpha (again - this is a duplicate entry to test the indexing code)', 'ACGTA')
    ('delta', 'CGCGC')

    """
    #Skip any text before the first record (e.g. blank lines, comments)
    while True:
        line = handle.readline()
        if line == "":
            return  # Premature end of file, or just empty?
        if line[0] == ">":
            break

    while True:
        if line[0] != ">":
            raise ValueError(
                "Records in Fasta files should start with '>' character")
        title = line[1:].rstrip()
        lines = []
        line = handle.readline()
        while True:
            if not line:
                break
            if line[0] == ">":
                break
            lines.append(line.rstrip())
            line = handle.readline()

        #Remove trailing whitespace, and any internal spaces
        #(and any embedded \r which are possible in mangled files
        #when not opened in universal read lines mode)
        yield title, "".join(lines).replace(" ", "").replace("\r", "")

        if not line:
            return  # StopIteration

    assert False, "Should not reach this line"


def FastaIterator(handle, alphabet=single_letter_alphabet, title2ids=None):
    """Generator function to iterate over Fasta records (as SeqRecord objects).

    handle - input file
    alphabet - optional alphabet
    title2ids - A function that, when given the title of the FASTA
    file (without the beginning >), will return the id, name and
    description (in that order) for the record as a tuple of strings.

    If this is not given, then the entire title line will be used
    as the description, and the first word as the id and name.

    By default this will act like calling Bio.SeqIO.parse(handle, "fasta")
    with no custom handling of the title lines:

    >>> with open("Fasta/dups.fasta") as handle:
    ...     for record in FastaIterator(handle):
    ...         print(record.id)
    ...
    alpha
    beta
    gamma
    alpha
    delta

    However, you can supply a title2ids function to alter this:

    >>> def take_upper(title):
    ...     return title.split(None, 1)[0].upper(), "", title
    >>> with open("Fasta/dups.fasta") as handle:
    ...     for record in FastaIterator(handle, title2ids=take_upper):
    ...         print(record.id)
    ...
    ALPHA
    BETA
    GAMMA
    ALPHA
    DELTA

    """
    if title2ids:
        for title, sequence in SimpleFastaParser(handle):
            id, name, descr = title2ids(title)
            yield SeqRecord(Seq(sequence, alphabet),
                            id=id, name=name, description=descr)
    else:
        for title, sequence in SimpleFastaParser(handle):
            try:
                first_word = title.split(None, 1)[0]
            except IndexError:
                assert not title, repr(title)
                #Should we use SeqRecord default for no ID?
                first_word = ""
            yield SeqRecord(Seq(sequence, alphabet),
                            id=first_word, name=first_word, description=title)

def FastaLazyIterator(handle, alphabet=single_letter_alphabet, title2ids=None):
    """Steps through the fast file and returns lazy loading SeqRecord"""
    #set handle to beginning
    handle.seek(0)
    position, next_position = -1, 0
    while True:
        #check if iteration has ended
        if position == next_position:
            break
        else:
            position = next_position
        #read the position and advance the file reader
        position = handle.tell()
        line_read_in = _bytes_to_string(handle.readline())
        next_position = handle.tell()
        #check for 
        if line_read_in[0] == ">":
            yield FastaSeqRecProxy(handle, position, single_letter_alphabet)
            handle.seek(next_position)

class FastaSeqRecProxy(SeqRecordProxyBase):
    """Implements the getter metods required to run the SeqRecordProxy"""
    
    def __init__(self, handle, startoffset, alphabet, title2ids = None):
        self._handle = handle
        self._alphabet = alphabet
        self._index = {"start":startoffset}
        self._pre_index_record(title2ids)
        
    def _pre_index_record(self, title2ids):
        """This determines the values needed for lazy loading

        The self._index dictionary is only set with the file
        start location on instantiation. This function sets the
        following variables in _index
            "sequencestart" : the file index where the seq. starts
            "sequencewidth" : the number of amino acids per line
            "linewidth"     : the number of characters per line
        
        This function also parses the title line and sets the following
        attributes:
             self.id
             self.name
             self.descr
        """
        handle = self._handle
        start = self._index["start"]
        handle.seek(start)

        titleline = _bytes_to_string(handle.readline())
        title = titleline[1:].rstrip()
        self._index["sequencestart"] = handle.tell()
        firstseqline = _bytes_to_string(handle.readline())

        #this segment fills out the index
        self._index["linewidth"] = len(firstseqline)
        self._index["sequencewidth"] = len(firstseqline.strip())


        #This segment of code sets attibutes of the SeqRecord proxy
        if title2ids:
            id, name, descr = title2ids(title)
            self.id = id
            self.name = name
            self.descr = descr
        else:
            try:
                first_word = title.split(None, 1)[0]
            except IndexError:
                assert not title, repr(title)
                first_word = ""
            self.id = first_word
            self.name = first_word
            self.descr = title

    def _read_seq(self):
        """implements standard sequence getter required by base class"""
        begin = self._index_begin
        end = self._index_end

        linewidth = self._index["linewidth"]
        sequencewidth = self._index["sequencewidth"]

        readFrom = intbegin/sequencewidth

class FastaWriter(SequentialSequenceWriter):
    """Class to write Fasta format files."""
    def __init__(self, handle, wrap=60, record2title=None):
        """Create a Fasta writer.

        handle - Handle to an output file, e.g. as returned
                 by open(filename, "w")
        wrap -   Optional line length used to wrap sequence lines.
                 Defaults to wrapping the sequence at 60 characters
                 Use zero (or None) for no wrapping, giving a single
                 long line for the sequence.
        record2title - Optional function to return the text to be
                 used for the title line of each record.  By default
                 a combination of the record.id and record.description
                 is used.  If the record.description starts with the
                 record.id, then just the record.description is used.

        You can either use::

            handle = open(filename, "w")
            myWriter = FastaWriter(handle)
            writer.write_file(myRecords)
            handle.close()

        Or, follow the sequential file writer system, for example:

            handle = open(filename, "w")
            myWriter = FastaWriter(handle)
            writer.write_header() # does nothing for Fasta files
            ...
            Multiple calls to writer.write_record() and/or writer.write_records()
            ...
            writer.write_footer() # does nothing for Fasta files
            handle.close()

        """
        SequentialSequenceWriter.__init__(self, handle)
        #self.handle = handle
        self.wrap = None
        if wrap:
            if wrap < 1:
                raise ValueError
        self.wrap = wrap
        self.record2title = record2title

    def write_record(self, record):
        """Write a single Fasta record to the file."""
        assert self._header_written
        assert not self._footer_written
        self._record_written = True

        if self.record2title:
            title = self.clean(self.record2title(record))
        else:
            id = self.clean(record.id)
            description = self.clean(record.description)

            #if description[:len(id)]==id:
            if description and description.split(None, 1)[0] == id:
                #The description includes the id at the start
                title = description
            elif description:
                title = "%s %s" % (id, description)
            else:
                title = id

        assert "\n" not in title
        assert "\r" not in title
        self.handle.write(">%s\n" % title)

        data = self._get_seq_string(record)  # Catches sequence being None

        assert "\n" not in data
        assert "\r" not in data

        if self.wrap:
            for i in range(0, len(data), self.wrap):
                self.handle.write(data[i:i + self.wrap] + "\n")
        else:
            self.handle.write(data + "\n")

if __name__ == "__main__":
    print("Running quick self test")

    import os
    from Bio.Alphabet import generic_protein, generic_nucleotide

    #Download the files from here:
    #ftp://ftp.ncbi.nlm.nih.gov/genomes/Bacteria/Nanoarchaeum_equitans
    fna_filename = "NC_005213.fna"
    faa_filename = "NC_005213.faa"

    def genbank_name_function(text):
        text, descr = text.split(None, 1)
        id = text.split("|")[3]
        name = id.split(".", 1)[0]
        return id, name, descr

    def print_record(record):
        #See also bug 2057
        #http://bugzilla.open-bio.org/show_bug.cgi?id=2057
        print("ID:" + record.id)
        print("Name:" + record.name)
        print("Descr:" + record.description)
        print(record.seq)
        for feature in record.annotations:
            print('/%s=%s' % (feature, record.annotations[feature]))
        if record.dbxrefs:
            print("Database cross references:")
            for x in record.dbxrefs:
                print(" - %s" % x)

    if os.path.isfile(fna_filename):
        print("--------")
        print("FastaIterator (single sequence)")
        with open(fna_filename, "r") as h:
            iterator = FastaIterator(h, alphabet=generic_nucleotide, title2ids=genbank_name_function)
        count = 0
        for record in iterator:
            count += 1
            print_record(record)
        assert count == 1
        print(str(record.__class__))

    if os.path.isfile(faa_filename):
        print("--------")
        print("FastaIterator (multiple sequences)")
        with open(faa_filename, "r") as h:
            iterator = FastaIterator(h, alphabet=generic_protein, title2ids=genbank_name_function)
        count = 0
        for record in iterator:
            count += 1
            print_record(record)
            break
        assert count > 0
        print(str(record.__class__))

    from Bio._py3k import StringIO
    print("--------")
    print("FastaIterator (empty input file)")
    #Just to make sure no errors happen
    iterator = FastaIterator(StringIO(""))
    count = 0
    for record in iterator:
        count += 1
    assert count == 0

    print("Done")

