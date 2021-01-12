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
        if not compression in self.ALLOWED_COMPRESSIONS:
            raise ValueError(
                f"`compression` argument not in allowed values: {self.ALLOWED_COMPRESSIONS}"
            )
        self.compression = compression
        self._content = dict()

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

    def dump(self, filepath: str):
        r"""
        Dump compressed_dictionary to file.
        Start by collecting the attributes that should be saved and then
        move the whole content of the dictionary to the file, separating
        key and values with a tab and different entries with a new-line.
        This is a safe op because json will escape possible tabs and newlines
        contained in the values of the dictionary.
        """
        with self.ALLOWED_COMPRESSIONS[self.compression].open(filepath, "wb") as fo:
            # write arguments
            specs_to_dump = dict()
            for key in self.ATTRIBUTES_TO_DUMP:
                specs_to_dump[key] = getattr(self, key)

            args = self.str2bytes(json.dumps(specs_to_dump))
            self.write_line(args, fo)

            # write key-value pairs
            for k in self.keys():
                self.write_key_value_line(k, self._content[k], fo)

    @classmethod
    def load(cls, filepath: str, compression: str = 'bz2', limit: int = None):
        r"""
        Create an instance by decompressing a dump from disk. First retrieve the
        object internal parameters from the first line of the compressed file,
        then start filling the internal dictionary without doing compression/decompression
        again.
        """
        assert os.path.isfile(filepath), (
            f"`filepath` {filepath} is not a file"
        )

        res = CompressedDictionary()

        # file might be already decompressed
        if compression is None:
            open_fn = open
        else:
            open_fn = cls.ALLOWED_COMPRESSIONS[compression].open

        with open_fn(filepath, "rb") as fi:
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

    def __delitem__(self, key: int):
        del self._content[key]

    def __iter__(self):
        return iter(self._content)

    def __len__(self):
        return len(self._content)

    def __eq__(self, o: object):
        r"""
        Two compressed dictionaries are equal if they contain the same key-value pairs
        and if they use the same compression algorithm.
        """
        return super().__eq__(o) and (self.compression == o.compression)

    @staticmethod
    def combine(*dictionaries):
        r"""
        Combine together multiple dictionaries using the same compression algorithm.
        This method will return a new CompressedDictionay object but values will not be
        cloned from the original dictionaries.
        """

        if not dictionaries:
            raise ValueError(
                "`combine` must be called with at least a dictionary"
            )

        res = dictionaries[0]
        for d in dictionaries[1:]:
            res.import_from_other(d)
        return res

    def merge(self, other, shift_keys=True):
        r"""
        Merge another dictionary with this one. If `shift_keys` is True,
        duplicated keys will be shifter in `other` to free positions. Otherwise,
        an error is raised.
        Dictionaries must use the same `compression` algorithm.

        Return:
            a new dictionary with values of both `self` and `other`
        """

        if self.compression != other.compression:
            raise ValueError(
                f"`other` must use the same `compression` algorithm as `self`"
            )

        res = CompressedDictionary()
        for key in self.keys():
            res.__add_already_compresses_value__(key, self.__get_without_decompress_value__(key))

        for key in other.keys():
            if key in res:
                if shift_keys:
                    res.__add_already_compresses_value__(len(res), other.__get_without_decompress_value__(key))
                else:
                    raise ValueError(
                        f"There is a common key {key} between `self` and `other`"
                    )
            else:
                res.__add_already_compresses_value__(key, other.__get_without_decompress_value__(key))

        return res

    def import_from_other(self, other, shift_keys=True):
        r"""
        Merge another dictionary into this one. If `shift_keys` is True,
        duplicated keys will be shifter in `other` to free positions. Otherwise,
        an error is raised. This method is similar to `update` but it takes in input
        another CompressedDictionary instead of a simple dict.
        Dictionaries must use the same `compression` algorithm.
        """

        if self.compression != other.compression:
            raise ValueError(
                f"`other` must use the same `compression` algorithm as `self`"
            )

        for key in list(other.keys()):
            if key in self:
                if shift_keys:
                    self.__add_already_compresses_value__(len(self), other.__get_without_decompress_value__(key))
                else:
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
        lengths = sum(len(value) for value in self.values())
        return byte_header_size * len(self) + lengths

    def get_keys_size(self): 
        r""" Return total keys size. """
        return sum(sys.getsizeof(key) for key in self.keys())

    def shuffle(self):
        r"""
        In-place shuffling of values.
        After the shuffling, each key will have a different value chosen randomly among
        the others. This is a permutation, no value is deleted or duplicated.
        """
        shuffled_keys = list(self.keys())
        random.shuffle(shuffled_keys)
        self._tmp_content = dict()

        for k1, k2 in zip(self.keys(), shuffled_keys):
            self._tmp_content[k1] = self._content[k2]

        self._content = self._tmp_content
        del self._tmp_content

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

        if shuffle:
            self.shuffle()

        all_keys = list(self.keys())
        k, m = divmod(len(all_keys), parts)

        split_keys = [all_keys[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(parts)]
        if len(split_keys) > 1 and len(split_keys[0]) > len(split_keys[-1]) and drop_last:
            split_keys.pop()

        for keys in split_keys:
            new_compressed_dictionary = CompressedDictionary(compression=self.compression)
            for i, k in enumerate(keys):
                new_compressed_dictionary.__add_already_compresses_value__(i if reset_keys else k, self.__get_without_decompress_value__(k))
            yield new_compressed_dictionary
