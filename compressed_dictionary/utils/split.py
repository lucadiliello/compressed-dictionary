import os
import math
import logging
from tqdm import tqdm
from argparse import ArgumentParser

from compressed_dictionary import CompressedDictionary

logging.getLogger().setLevel(logging.INFO)


def main(args):
    
    assert os.path.isfile(args.input_file), (
        f"Input file {args.input_file} does not exist."
    )

    assert not os.path.isdir(args.output_folder), (
        f"Output directory {args.output_folder} does already exist."
    )

    assert (args.parts is None) != (args.parts_length is None), (
        "you can define only one between `parts` and `parts-length`"
    )

    logging.info("Loading input dictionary")
    dictionary = CompressedDictionary.load(args.input_file, limit=args.limit)
    os.makedirs(args.output_folder)

    logging.info("Splitting")
    splits_iterator = dictionary.split(
        parts=args.parts,
        parts_length=args.parts_length,
        drop_last=args.drop_last,
        reset_keys=args.reset_keys,
        shuffle=args.shuffle
    )

    logging.info("Writing splits to disk")
    total = (
        args.parts if args.parts is not None else (
            math.floor(len(dictionary) / args.parts_length) if args.drop_last else math.ceil(len(dictionary) / args.parts_length)
        )
    )
    for i, split_dict in tqdm(enumerate(splits_iterator), desc="Splitting", total=total):
        name = f"{os.path.basename(args.input_file).split('.')[0]}-split-{i}"
        split_dict.dump(
            os.path.join(args.output_folder, name),
        )

    logging.info("Done")


if __name__ == '__main__':

    parser = ArgumentParser()

    parser.add_argument('-i', '--input-file', type=str, required=True, help="Input dictionary to split")
    parser.add_argument('-o', '--output-folder', type=str, required=True, help="Output folder in which splits will be put")
    parser.add_argument('--parts', type=int, required=False, default=None, help="Input dictionary to split")
    parser.add_argument('--parts-length', type=int, required=False, default=None, help="Input dictionary to split")
    parser.add_argument('--drop-last', action="store_true", help="Input dictionary to split")
    parser.add_argument('--reset-keys', action="store_true", help="Input dictionary to split")
    parser.add_argument('--shuffle', action="store_true", help="Input dictionary to split")
    parser.add_argument('--limit', type=int, default=None, required=False,
                        help="Read only a limited number of key-value pairs from the input dict")

    args = parser.parse_args()

    main(args)
