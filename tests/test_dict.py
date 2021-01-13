import os
import random
import shutil
import pytest
from compressed_dictionary.compressed_dictionary import CompressedDictionary


def generate_dict(depth=0):
    res = dict()
    if depth > 4:
        return None
    for i in range(random.randint(2, 5)):
        if random.random() > 0.9:
            res[len(res)] = generate_dict(depth=depth+1)
        elif random.random() > 0.45:
            res[len(res)] = generate_list(depth=depth+1)
        elif random.random() > 0.2:
            res[len(res)] = generate_string()
        else:
            res[len(res)] = random.random()
    return res

def generate_string():
    return ''.join([chr(random.randint(0, 2**20)) for _ in range(50)])

def generate_list(depth=0):
    res = []
    if depth > 4:
        return None
    for i in range(random.randint(2, 5)):
        if random.random() > 0.9:
            res.append(generate_dict(depth=depth+1))
        elif random.random() > 0.45:
            res.append(generate_list(depth=depth+1))
        elif random.random() > 0.2:
            res.append(generate_string())
        else:
            res.append(random.random())
    return res


# testing save/reload
@pytest.mark.parametrize(
    ["iteration"], [
        [i] for i in range(100)
    ],
)
def test_save_reload(iteration):
    
    dd = CompressedDictionary()
    for i in range(10):
        if random.random() > 0.7:
            dd[i] = generate_dict()
        elif random.random() > 0.5:
            dd[i] = generate_list()
        elif random.random() > 0.25:
            dd[i] = generate_string()
        else:
            dd[i] = random.random()

    dd.dump("tmp.bz2")
    a = CompressedDictionary.load('tmp.bz2')

    assert a == dd

    dd = dd.merge(dd, reset_keys=True)
    dd.merge_(dd, reset_keys=True)

    os.remove('tmp.bz2')


# testing save/reload
@pytest.mark.parametrize(
    ["iteration"], [
        [i] for i in range(100)
    ],
)
# test shuffle and splitting
def test_shuffle_and_splitting(iteration):

    dd = CompressedDictionary()
    dd.update(((i, i) for i in range(50)))

    res = dd.split(parts=random.randint(1, 5), reset_keys=False, drop_last=False, shuffle=False)
    assert CompressedDictionary.combine(*list(res)) == dd


# testing save/reload
@pytest.mark.parametrize(
    ["iteration"], [
        [i] for i in range(100)
    ],
)
# test shuffle and splitting
def test_combination_on_disk(iteration):

    dd = CompressedDictionary()
    dd.update(((i, i) for i in range(50)))

    os.makedirs("tmp")

    filenames = []
    res = dd.split(parts=random.randint(1, 5), reset_keys=False, drop_last=False, shuffle=False)
    for i, r in enumerate(res):
        name = f"split-{i}.bz2"
        r.dump(os.path.join("tmp", name))
        filenames.append(name)
    
    filepaths = [os.path.join("tmp", f) for f in filenames]
    CompressedDictionary.combine_on_disk(os.path.join("tmp", "result.bz2"), *filepaths, reset_keys=False)
    
    a = CompressedDictionary.load(os.path.join("tmp", "result.bz2"))
    shutil.rmtree("tmp")

    assert a == dd
