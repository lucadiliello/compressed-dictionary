import os
import math
import logging
from tqdm import tqdm
from argparse import ArgumentParser

from compressed_dictionary import CompressedDictionary

logging.getLogger().setLevel(logging.INFO)


def main(args):
    
    for filename in args.input_files:
        assert os.path.isfile(filename), (
            f"Input file {filename} does not exist."
        )

    assert not os.path.isdir(args.output_file), (
        f"Output file {args.output_file} does already exist."
    )

    logging.info("Merging input dictionaries into single file")
    CompressedDictionary.combine_on_disk(args.output_file, *args.input_files, compression=args.compression, shift_keys=args.shift_keys)
    logging.info("Done")


if __name__ == '__main__':

    parser = ArgumentParser()

    parser.add_argument('-i', '--input-files', type=str, nargs='+', required=True, help="Input dictionaries to merge")
    parser.add_argument('-o', '--output-file', type=str, required=True, help="Output file resulting merged dictionary")

    parser.add_argument('--compression', type=str, default='bz2',
                        choices=list(CompressedDictionary.ALLOWED_COMPRESSIONS.keys()) + [None],
                        help="Compression format of input dictionary and output splits")
    parser.add_argument('--shift_keys', action="store_true", help="Whether to reset keys")

    args = parser.parse_args()

    main(args)
