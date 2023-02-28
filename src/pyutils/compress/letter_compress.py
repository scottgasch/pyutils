#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""
This is a simple, honestly, toy compression scheme that uses a custom
alphabet of 32 characters which can each be represented in six bits
instead of eight.  It therefore reduces the size of data composed of
only those letters by 25% without loss.
"""

import bitstring

from pyutils.collectionz.bidict import BiDict

special_characters = BiDict(
    {
        " ": 27,
        ".": 28,
        ",": 29,
        "-": 30,
        '"': 31,
    }
)


def compress(uncompressed: str) -> bytes:
    """Compress a word sequence into a stream of bytes.  The compressed
    form will be 5/8th the size of the original.  Words can be lower
    case letters or special_characters (above).

    Args:
        uncompressed: the uncompressed string to be compressed

    Returns:
        the compressed bytes

    >>> import binascii
    >>> binascii.hexlify(compress('this is a test'))
    b'a2133da67b0ee859d0'

    >>> binascii.hexlify(compress('scot'))
    b'98df40'

    >>> binascii.hexlify(compress('scott'))  # Note the last byte
    b'98df4a00'

    """
    compressed = bitstring.BitArray()
    for letter in uncompressed:
        if "a" <= letter <= "z":
            bits = ord(letter) - ord("a") + 1  # 1..26
        else:
            if letter not in special_characters:
                raise Exception(
                    f'"{uncompressed}" contains uncompressable char="{letter}"'
                )
            bits = special_characters[letter]
        compressed.append(f"uint:5={bits}")
    while len(compressed) % 8 != 0:
        compressed.append("uint:1=0")
    return compressed.bytes


def decompress(compressed: bytes) -> str:
    """
    Decompress a previously compressed stream of bytes back into
    its original form.

    Args:
        compressed: the compressed data to decompress

    Returns:
        The decompressed string

    >>> import binascii
    >>> decompress(binascii.unhexlify(b'a2133da67b0ee859d0'))
    'this is a test'

    >>> decompress(binascii.unhexlify(b'98df4a00'))
    'scott'

    """
    decompressed = ""
    kompressed = bitstring.BitArray(compressed)

    # There are compressed messages that legitimately end with the
    # byte 0x00.  The message "scott" is an example; compressed it is
    # 0x98df4a00.  It's 5 characters long which means there are 5 x 5
    # bits of compressed info (25 bits, just over 3 bytes).  The last
    # (25th) bit in the steam happens to be a zero.  The compress code
    # padded out the compressed message by adding seven more zeros to
    # complete the partial 4th byte.  In the 4th byte, however, one
    # bit is information and seven are padding.
    #
    # It's likely that this API's client code may treat a zero byte as
    # a termination character and not regard it as a legitimate part
    # of the message.  This is a bug in that client code, to be clear.
    #
    # However, it's a bug we can work around:
    #
    # Here, I'm appending an extra 0x00 byte to the compressed message
    # passed in.  If the client code dropped the last 0x00 byte (and,
    # with it, some of the legitimate message bits) by treating it as
    # a termination mark, this 0x00 will replace it (and the missing
    # message bits).  If the client code didn't drop the last 0x00 (or
    # if the compressed message didn't end in 0x00), adding an extra
    # 0x00 is a no op because the codepoint 0b00000 is a "stop" message
    # so we'll ignore the extras.
    kompressed.append("uint:8=0")

    for chunk in kompressed.cut(5):
        chunk = chunk.uint
        if chunk == 0:
            break

        if 1 <= chunk <= 26:
            letter = chr(chunk - 1 + ord("a"))
        else:
            letter = special_characters.inverse[chunk][0]
        decompressed += letter
    return decompressed


if __name__ == "__main__":
    import doctest

    doctest.testmod()
