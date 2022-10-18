#!/usr/bin/env python3

"""Find duplicate files (based on hash of contents) in a directory (or
tree) and deduplicate them by either deleting duplicates or (with -l)
symlinking duplicates to a canonical original.
"""

import logging
import os
from collections import defaultdict

from pyutils import bootstrap, config, string_utils
from pyutils.files import file_utils

logger = logging.getLogger(__name__)
parser = config.add_commandline_args(
    f'Dedup Files ({__file__})',
    'Deduplicate files based on content in a directory or recursively',
)
parser.add_argument(
    'start_dirs',
    type=str,
    nargs='*',
    help='Filespec (glob) of starting directory',
)
parser.add_argument(
    '-n',
    '--dry_run',
    action='store_true',
    help='Do nothing, just say what you\'d do',
)
parser.add_argument(
    '-R',
    '--recursive',
    action='store_true',
    help='Traverse recursively',
)
parser.add_argument(
    '-l',
    '--link',
    action='store_true',
    help='Instead of deleting duplicates, create symbolic links',
)


@bootstrap.initialize
def main() -> int:
    """Entry point"""
    sigs = defaultdict(list)
    sizes = defaultdict(list)
    dry_size = 0

    for spec in config.config['start_dirs']:
        if config.config['recursive']:
            filez = file_utils.get_files_recursive(spec)
        else:
            filez = file_utils.get_files(spec)

        for filename in filez:
            if not file_utils.is_symlink(filename) and file_utils.is_normal_file(
                filename
            ):
                size = file_utils.get_file_size(filename)
                sizes[size].append(filename)
                logging.debug('%d => %s', size, sizes[size])

        for size in sizes:
            files = sizes[size]
            if len(files) > 1:
                logging.debug('%s (size=%d) need checksums', files, size)
                for filename in files:
                    md5 = file_utils.get_file_md5(filename)
                    sigs[md5].append(filename)

        for md5 in sigs:
            files = sigs[md5]
            if len(files) > 1:
                logging.debug('%s are all dupes', files)

                filename = files[0]
                for dupe in files[1:]:
                    if len(dupe) > len(filename):
                        filename = dupe

                for dupe in files:
                    if filename == dupe:
                        continue

                    assert not file_utils.is_symlink(dupe)
                    if config.config['dry_run']:
                        print(f'{filename} == {dupe}.')
                        dry_size += file_utils.get_file_size(dupe)
                    else:
                        assert len(filename) >= len(dupe)
                        saved = filename
                        killed = dupe
                        print(f'{killed} == {saved} -- DELETED')
                        logger.info('Deleting %s', killed)
                        os.remove(killed)
                        if config.config['link']:
                            logger.info('Creating symlink from %s -> %s', saved, killed)
                            os.symlink(saved, killed)
                        filename = saved

    if dry_size > 0:
        print(
            f'Running w/o -n would have deleted {string_utils.add_thousands_separator(dry_size)} bytes from disk.'
        )
    return 0


if __name__ == '__main__':
    main()
