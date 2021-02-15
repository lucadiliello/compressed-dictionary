import os
import sys
import math
import lzma
import bz2
import gzip
import random
from collections.abc import MutableMapping
from struct import pack, unpack

import json
from typing import Dict, List, Union


class CompressedDictionary(MutableMapping):
    r"""
    A dictionary where every value is compressed. Values can be dictionaries, lists or strings
    (in particular values can be something that could be parsed by `json.dumps`).
    Contains also primitives to be dumped to file and restored from a file.

    This dictionary is multithread-safe and can be easily used with multiple thread calling both get and set.

    Performance:
    - Compression of about 225 entries / second.
        Tested with values equal to strings with an average length of 2000 characters each.
        This dictionary supports multithreading, with which many values can be assigned concurrently to improve performance.
    - Decompression of about 10000 entries / second on a laptop. Entries are the one compressed above. 

    Args:
        compression: compression algorithm, one between `xz`, `gzip` and `bz2`. Defaults to `bz2`.

    Example:
    >>> d = CompressedDictionary()
    >>> d['0'] = 'this is a string!"
    >>> d.dump('file.bz2')
    >>> a = CompressedDictionary.load('file.bz2')
    >>> a == d
    True
    """

    ALLOWED_COMPRESSIONS = { 'xz': lzma, 'gzip': gzip, 'bz2': bz2 }
    ATTRIBUTES_TO_DUMP = ['compression']
    LINE_LENGTH_BYTES = 4

    def __init__(self, compression: str = 'bz2'):
        r"""
        Args:
            compression: a string representing the compression algorithm to use on values and for the dump.
        """

        self.check_valid_compression(compression)
        self.compression = compression
        self._content = dict()
    
    @classmethod
    def check_valid_compression(cls, compression: str, raise_error: bool = True):
        r"""
        Check `compression` is a valid compression argument.
        """
        if not compression in cls.ALLOWED_COMPRESSIONS:
            if raise_error:
                raise ValueError(
                    f"`compression` argument not in allowed values: {cls.ALLOWED_COMPRESSIONS.keys()}"
                )
            else:
                return False
        return True

    @classmethod
    def write_line(cls, data: bytes, fd):
        r""" Write a line composed of a header (data length) and the corresponding payload. """
        payload_length = len(data)
        payload_length_bytes = cls.int2bytes(payload_length, cls.LINE_LENGTH_BYTES)
        line = payload_length_bytes + data
        fd.write(line)
    
    @classmethod
    def write_key_value_line(cls, key, value, fd):
        r""" Pack together a key-value pair and write as line. """
        header = f"i{len(value)}s"
        data = pack(header, key, value)
        cls.write_line(data, fd)

    @classmethod
    def read_line(cls, fd):
        r""" Read a line composed of a header (data length) and the corresponding payload. """
        bytes_payload_length = fd.read(cls.LINE_LENGTH_BYTES)
        if not bytes_payload_length:
            return None # no more data to read

        payload_length = cls.bytes2int(bytes_payload_length)
        data = fd.read(payload_length)
        return data

    @classmethod
    def read_key_value_line(cls, fd):
        r""" Unpack key and value by reading a line. """
        line = cls.read_line(fd)
        if line is None:
            return None # no more data to read

        header = f"i{len(line) - cls.LINE_LENGTH_BYTES}s"
        key, value = unpack(header, line)
        return (key, value)

    def dump(self, filepath: str, limit: int = None):
        r"""
        Dump compressed_dictionary to file.
        Start by collecting the attributes that should be saved and then
        move the whole content of the dictionary to the file, separating
        key and values with a tab and different entries with a new-line.
        This is a safe op because json will escape possible tabs and newlines
        contained in the values of the dictionary.
        """

        with open(filepath, "wb") as fo:
            # write arguments
            specs_to_dump = dict()
            for key in self.ATTRIBUTES_TO_DUMP:
                specs_to_dump[key] = getattr(self, key)

            args = self.str2bytes(json.dumps(specs_to_dump))
            self.write_line(args, fo)

            # write key-value pairs
            for i, k in enumerate(self.keys()):
                if limit is not None and i >= limit:
                    break
                self.write_key_value_line(k, self._content[k], fo)

    @classmethod
    def load(cls, filepath: str, limit: int = None):
        r"""
        Create an instance by decompressing a dump from disk. First retrieve the
        object internal parameters from the first line of the file,
        then start filling the internal dictionary without doing compression/decompression
        again.
        """

        if not os.path.isfile(filepath):
            raise ValueError(
                f"`filepath` {filepath} is not a file"
            )

        res = CompressedDictionary()

        with open(filepath, "rb") as fi:
            # read and set arguments
            arguments = json.loads(cls.bytes2str(cls.read_line(fi)))
            for key, value in arguments.items():
                setattr(res, key, value)

            # read key-value pairs
            read_lines = 0
            while True:
                line = cls.read_key_value_line(fi)
                if line is None or (limit is not None and read_lines >= limit):
                    break
                key, value = line
                res._content[key] = value
                read_lines += 1

        return res

    @staticmethod
    def int2bytes(integer: int, length: int = None):
        r""" Convert integer to bytes computing correct number of needed bytes if `length` is not provided. """
        needed_bytes = length if length else max(math.ceil((integer).bit_length() / 8), 1)
        return (integer).to_bytes(needed_bytes, byteorder="little")

    @staticmethod
    def bytes2int(byteslist: bytes):
        r""" Convert bytes representation to integer. """
        return int.from_bytes(byteslist, byteorder="little")

    @staticmethod
    def str2bytes(s):
        r""" Convert a string to bytes. """
        return s.encode('utf-8')

    @staticmethod
    def bytes2str(b):
        r""" Convert bytes representation to string. """
        return b.decode('utf-8')

    @classmethod
    def __compress__(cls, value, compression: str = 'bz2'):
        value = json.dumps(value)
        value = cls.str2bytes(value)
        value = cls.ALLOWED_COMPRESSIONS[compression].compress(value)
        return value

    @classmethod
    def __decompress__(cls, compressed_value, compression: str = 'bz2'):
        value = cls.ALLOWED_COMPRESSIONS[compression].decompress(compressed_value)
        value = cls.bytes2str(value)
        value = json.loads(value)
        return value

    def __getitem__(self, key: int):
        value = self._content[key]
        value = self.__class__.__decompress__(value, compression=self.compression)
        return value

    def __setitem__(self, key: int, value: Union[Dict, List]):
        value = self.__class__.__compress__(value, compression=self.compression)
        self._content[key] = value

    def __add_already_compresses_value__(self, key: int, value: bytes):
        self._content[key] = value

    def __get_without_decompress_value__(self, key: int):
        return self._content[key]
    
    @classmethod
    def _convert_value(cls, value, compression_in: str, compression_out: str):
        value = cls.__decompress__(value, compression=compression_in)
        value = cls.__compress__(value, compression=compression_out)
        return value

    def __delitem__(self, key: int):
        del self._content[key]

    def __iter__(self):
        return iter(self._content)

    def __len__(self):
        return len(self._content)

    def __eq__(self, other: object):
        r"""
        Two compressed dictionaries are equal if they contain the same key-value pairs
        and if they use the same compression algorithm.
        """
        return super().__eq__(other) and (self.compression == other.compression)

    def compatible(self, other: object):
        r"""
        Return True if this dictionary and `other` use the same compression and could so be merged.
        """
        return (self.compression == other.compression)

    @classmethod
    def combine_on_disk(cls, destination: str, *dictionaries_files, compression: str = None, reset_keys: bool = True):
        r"""
        Combine together multiple dictionary dumps using in a dictionary using `compression` compression.
        If `compression` is None it will use the compression of the first dictionary argument.
        This method will return write to the `destination` file.
        """

        if not dictionaries_files:
            raise ValueError(
                "`combine_on_disk` must be called with at least a dictionary"
            )

        # read first file to load encoding info
        with open(dictionaries_files[0], "rb") as fi:
            # read arguments
            arguments = json.loads(cls.bytes2str(cls.read_line(fi)))

        with open(destination, "wb") as fo:
            # write arguments
            out_arguments = arguments.copy()
            if compression is not None:
                out_arguments['compression'] = compression

            cls.write_line(cls.str2bytes(json.dumps(out_arguments)), fo)

            # write key-value pairs, eventually converting if source and target compression are different
            new_key = 0
            res_keys = set()

            for filename in dictionaries_files:
                # write key-value pairs for each input filename
                with open(filename, "rb") as fi:
                    # read arguments
                    arguments_2 = json.loads(cls.bytes2str(cls.read_line(fi)))

                    # copy input to output
                    while True:

                        line = cls.read_key_value_line(fi)
                        if line is None:
                            break
                        key, value = line

                        if arguments_2['compression'] != out_arguments['compression']:
                            value = cls._convert_value(value, arguments_2['compression'], out_arguments['compression'])

                        # if keys are shifted, use incrementally generated new key
                        if reset_keys:
                            cls.write_key_value_line(new_key, value, fo)
                            new_key += 1

                        # assert new key is not already writted to output
                        else:
                            if key in res_keys:
                                raise ValueError(
                                    f"duplicated key detected. Either call with `reset_keys=True` or combine dictionaries with no common key"
                                )
                            cls.write_key_value_line(key, value, fo)
                            res_keys.add(key)

    @staticmethod
    def combine(*dictionaries, reset_keys: bool = True):
        r"""
        Combine together multiple dictionaries.
        This method will return a new CompressedDictionay object but values will not be
        cloned from the original dictionaries.
        """

        if not dictionaries:
            raise ValueError(
                "`combine` must be called with at least a dictionary"
            )

        res = dictionaries[0]
        # first che compatibility
        for d in dictionaries[1:]:
            if not res.compatible(d):
                raise ValueError(
                    "All dictionaries must use the same compression algorithm"
                )

        for d in dictionaries[1:]:
            res.merge_(d, reset_keys=reset_keys)
        return res

    def merge(self, other, reset_keys: bool = True):
        r"""
        Merge another dictionary with this one. If `reset_keys` is True,
        duplicated keys will be shifter in `other` to free positions. Otherwise,
        an error is raised.
        Dictionaries must use the same `compression` algorithm.

        Return:
            a new dictionary with values of both `self` and `other`
        """

        if not self.compatible(other):
            raise ValueError(
                f"`other` must use the same `compression` algorithm as `self`"
            )

        res = CompressedDictionary()
        new_key = 0

        # add keys from self
        for key in self.keys():
            if reset_keys:
                res.__add_already_compresses_value__(new_key, self.__get_without_decompress_value__(key))
                new_key += 1
            else:
                res.__add_already_compresses_value__(key, self.__get_without_decompress_value__(key))

        # add keys from other
        for key in other.keys():
            if reset_keys:
                res.__add_already_compresses_value__(new_key, other.__get_without_decompress_value__(key))
                new_key += 1
            else:
                if key in res:
                    raise ValueError(
                        f"There is a common key {key} between `self` and `other`"
                    )
                else:
                    res.__add_already_compresses_value__(key, other.__get_without_decompress_value__(key))

        return res

    def merge_(self, other, reset_keys: bool = True):
        r"""
        Merge another dictionary into this one. If `reset_keys` is True,
        duplicated keys will be shifter in `other` to free positions. Otherwise,
        an error is raised. This method is similar to `merge` but is in-place.
        Dictionaries must use the same `compression` algorithm.

        Return:
            None
        """

        if not self.compatible(other):
            raise ValueError(
                f"`other` must use the same `compression` algorithm as `self`"
            )

        # start by filling holes in the keys list
        free_keys = set(range(max(self.keys()) + 1)) - set(self.keys())

        for key in list(other.keys()):
            if reset_keys:
                if free_keys:
                    self.__add_already_compresses_value__(free_keys.pop(), other.__get_without_decompress_value__(key))
                else:
                    self.__add_already_compresses_value__(len(self), other.__get_without_decompress_value__(key))
            else:
                if key in self:
                    raise ValueError(
                        f"There is a common key {key} between `self` and `other`"
                    )
                else:
                    self.__add_already_compresses_value__(key, other.__get_without_decompress_value__(key))

    def get_values_size(self): 
        r"""
        Return total values size (compressed).
        Each bytes array has a fixed default memory usage plus 1 byte for each character
        """
        byte_header_size = sys.getsizeof(bytes())
        lengths = sum(len(value) for value in self._content.values())
        return byte_header_size * len(self) + lengths

    def get_keys_size(self): 
        r""" Return total keys size. """
        return sum(sys.getsizeof(key) for key in self._content.keys())

    def split(
        self,
        parts: int = None,
        parts_length: int = None,
        drop_last: bool = False,
        reset_keys: bool = False,
        shuffle: bool = False
    ):
        r"""
        Split the dictionary in many sub-dictionaries.
        `parts` and `parts_length` arguments are mutually exlusive. They cannot be
        both defined or both undefined at the same time. The algorithm works on keys and only at the
        end divides values into the different resulting dictionaries, without doing compression/decompression.
        The maximal difference in size among the returned dictionaries is `1`.

        Args:
            parts int: number of parts in which the dict should be divided into.
            parts_length int: split the dictionary in parts with a length equal to `parts_length`.
            drop_last bool: whether to drop the possible last smaller dictionary when using `parts_length`.
            reset_keys bool: whether to reset keys starting from `0` in the new dictionaries.
            shuffle bool: whether to shuffle the dataset before the split.

        Return:
            a generator of smaller CompressedDictionaries with same compression algorithm as the original.

        Example:
            >>> d = CompressedDictionary()
            >>> d.update([(i, i) for i in range(17)])
            >>> d_1, d_2 = d.split(parts=2, shuffle=True, reset_keys=True)
            >>> list(d_1.items())
            [(0, 0), (1, 10), (2, 15), (3, 12), (4, 2), (5, 7), (6, 3), (7, 1), (8, 4)]
            >>> list(d_2.items())
            [(0, 8), (1, 13), (2, 14), (3, 11), (4, 5), (5, 6), (6, 9), (7, 16)]
        """

        if (parts is None) == (parts_length is None):
            raise ValueError(
                "only one argument among `parts` and `parts_length` can be defined"
            )

        if parts is None:
            parts = math.ceil(len(self) / parts_length)

        all_keys = list(self.keys())
        if shuffle:
            random.shuffle(all_keys)

        k, m = divmod(len(all_keys), parts)

        split_keys = [all_keys[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(parts)]
        if len(split_keys) > 1 and len(split_keys[0]) > len(split_keys[-1]) and drop_last:
            split_keys.pop()

        for keys in split_keys:
            new_compressed_dictionary = CompressedDictionary(compression=self.compression)
            for i, k in enumerate(keys):
                new_compressed_dictionary.__add_already_compresses_value__(i if reset_keys else k, self.__get_without_decompress_value__(k))
            yield new_compressed_dictionary
