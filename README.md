# compressed-dictionary
A dictionary which values are compressed to save memory. No external library is required. Python 3 is required.

## Is this for you?

The `CompressedDictionary` is useful when you have a large dictionary where values are, for example, strings of text, long lists of numbers or strings, dictionaries with many key-value pairs and so on. Using a `CompressedDictionary` to store `int->int` relations make no sense since the `CompressedDictionary` would result in a bigger memory occupancy.

The `CompressedDictionary` has some contraints:
- `keys` must be integers (max key value is `2^32`). You could also use strings or larger integers, but some functionalities may not work out-of-the-box.
- `values` must be `json` serializable. This means that values can be integers, booleans, strings, floats and any combination of this types grouped in lists or dictionaries. You can test if a value is json serializable with `json.dumps(object)`.


## Install

Install with:
```bash
pip install compressed-dictionary
```

and remove with:
```bash
pip uninstall compressed-dictionary
```


## How to use the `CompressedDictionary`

A `CompressedDictionary` is a python dictionary with some enhancements under the hood. When assigning a value to a key, the value is automatically serialized and compressed. The same applies when a value is extracted with a key from the dictionary.

```python
>>> from create_pretraining_dataset.utils import CompressedDictionary
>>>
>>> d = CompressedDictionary()
>>> # OR
>>> d = CompressedDictionary.load("/path/to/file")
>>> # OR
>>> d = CompressedDictionary.load("/path/to/file")
>>>
>>> d[0] = {'value_1': [1, 2, 3, 4], 'value_2': [1.0, 1.0, 1.0, 1.0], 'value_3': ["hi", "I", "am", "Luca"], 'value_4': [True, False, True, True]}
>>>
>>> # use it like a normal dictionary
>>> # remember that keys are integers (to be better compatible with pytorch dataset indexing with integers)
>>> d[0]
{'value_1': [1, 2, 3, 4], 'value_2': [1.0, 1.0, 1.0, 1.0], 'value_3': ["hi", "I", "am", "Luca"], 'value_4': [True, False, True, True]}
>>>
>>> for k in d.keys():
>>>     # do something with d[k]
>>>     print(k)
>>> # OR
>>> for k, value in d.items():
>>>     print(k, value) # print millions of entries is not always a good idea...
>>>
>>> # delete an entry
>>> del d[0]
>>>
>>> # get number of key-value pairs
>>> len(d)
1
>>>
>>> # access compressed data directly
>>> d._content[0]
b"3hbwuchbufbou&RFYUVGBKYU6T76\x00\x00" # the compressed byte array corresponding to the d[0] value
>>>
>>> # save the dict to disk
>>> d.dump("/path/to/new/dump.cd")
>>>
>>> # split the dict in a set of smaller ones
>>> d.update((i, d[0]) for i in range(5))
>>> res = d.split(parts=2, reset_keys=True, drop_last=False, shuffle=True) 
>>> # Notice: splits are returned as a generator
>>> # Notice: reset_keys will ensure that each resulting split has keys from 0 to len(split)-1
>>> # Notice: shuffle will shuffle keys (indexes) before splitting
>>>
>>> list(next(res).items())
[(0, {'value_1': [1, 2, 3, 4], 'value_2': [1.0, 1.0, 1.0, 1.0], 'value_3': ["hi", "I", "am", "Luca"], 'value_4': [True, False, True, True]}), (1, {'value_1': [1, 2, 3, 4], 'value_2': [1.0, 1.0, 1.0, 1.0], 'value_3': ["hi", "I", "am", "Luca"], 'value_4': [True, False, True, True]}), (2, {'value_1': [1, 2, 3, 4], 'value_2': [1.0, 1.0, 1.0, 1.0], 'value_3': ["hi", "I", "am", "Luca"], 'value_4': [True, False, True, True]})]
>>>
>>> list(next(res).items())
[(0, {'input_ids': [1, 2, 3, 4], 'attention_mask': [1, 1, 1, 1], 'token_type_ids': [0, 0, 1, 1], 'words_tails': [True, False, True, True]}), (1, {'input_ids': [1, 2, 3, 4], 'attention_mask': [1, 1, 1, 1], 'token_type_ids': [0, 0, 1, 1], 'words_tails': [True, False, True, True]})]
>>>
>>> list(next(res).items())
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
StopIteration
```

The documentation for each method can be found in `compressed_dictionary/compressed_dictionary.py`.


## Utilities

We provide some utilities to manage `compressed-dictionary`s from the command line.

### Merge

Merge two dictionaries into a third one:

```bash
python -m compressed_dictionary.utils.merge --input-files <input-dict-1> <input-dict-2> <...> --output-file <resulting-dict>
```

If dictionaries have common keys, you can re-create the key index from `0` to the sum of the lengths of the dicts by using `--reset-keys`.
If you want the resulting dict to use a different compression algorithm use `--compression <xz|bz2|gzip>`.


### Split

Split a dictionary in many sub-dictionaries:

```bash
python -m compressed_dictionary.utils.split --input-file <input-dict> --output-folder <resulting-dicts-folder> --parts <number-of-parts>
```

This will create `<number-of-parts>` dictionaries into `<resulting-dicts-folder>`. If you want to specify the length of the splits you can use `--parts-length <splits-length>` instead of `--parts`. Use `--drop-last` if you don't want the last smaller dict when splitting.

If you want to reset the keys in the new dictionaries, use `--reset-keys`. If you want to shuffle values before splitting, use `--shuffle`. Finally, if you want to read only a part of the input dictionary, use `--limit <number-of-key-value-pairs-to-read>`.
