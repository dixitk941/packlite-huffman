"""Huffman text compressor.

The tree is built with a min-heap. At every step the two least frequent
nodes are merged. That greedy choice gives the shortest codes to the
characters that appear most often.
"""

import heapq
import struct


class Node:
    def __init__(self, freq, symbol=None, left=None, right=None, tie=0):
        self.freq = freq
        self.symbol = symbol
        self.left = left
        self.right = right
        self.tie = tie

    def __lt__(self, other):
        if self.freq != other.freq:
            return self.freq < other.freq
        return self.tie < other.tie


def build_tree(text):
    """Return the Huffman tree, the code map, and how many heap operations ran."""
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1

    heap = []
    tie = 0
    heap_ops = 0
    for ch in sorted(freq):
        tie += 1
        heapq.heappush(heap, Node(freq[ch], symbol=ch, tie=tie))
        heap_ops += 1

    if len(heap) == 1:
        only = heap[0]
        root = Node(only.freq, left=only, tie=tie + 1)
        return root, {only.symbol: "0"}, freq, heap_ops

    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        tie += 1
        parent = Node(left.freq + right.freq, left=left, right=right, tie=tie)
        heapq.heappush(heap, parent)
        heap_ops += 3

    codes = {}

    def walk(node, prefix):
        if node.symbol is not None:
            codes[node.symbol] = prefix or "0"
            return
        walk(node.left, prefix + "0")
        walk(node.right, prefix + "1")

    walk(heap[0], "")
    return heap[0], codes, freq, heap_ops


def _pack_bits(bits):
    pad = (8 - (len(bits) % 8)) % 8
    bits = bits + ("0" * pad)
    data = bytearray()
    for i in range(0, len(bits), 8):
        data.append(int(bits[i:i + 8], 2))
    return bytes(data), pad


def _unpack_bits(data, pad, bit_length):
    bits = "".join(f"{byte:08b}" for byte in data)
    if pad:
        bits = bits[:-pad] if pad != 8 else bits
    return bits[:bit_length]


def compress(text):
    """Compress a string. Returns a dict the web page and the file writer share."""
    if text is None or text == "":
        raise ValueError("Nothing to compress.")

    _root, codes, freq, heap_ops = build_tree(text)
    bits = "".join(codes[ch] for ch in text)
    packed, pad = _pack_bits(bits)

    header = _encode_header(freq, len(bits), pad)
    blob = header + packed

    original = len(text.encode("utf-8"))
    compressed = len(blob)
    saved = original - compressed
    ratio = (saved / original * 100) if original else 0

    table = [
        {"char": ch, "freq": freq[ch], "code": codes[ch]}
        for ch in sorted(freq, key=lambda c: (-freq[c], c))
    ]
    return {
        "blob": blob,
        "original_bytes": original,
        "compressed_bytes": compressed,
        "saved_bytes": saved,
        "saved_percent": round(ratio, 1),
        "characters": len(text),
        "alphabet": len(freq),
        "heap_operations": heap_ops,
        "table": table,
    }


def _encode_header(freq, bit_length, pad):
    """Compact header: magic, each character with its count, then the bit length."""
    parts = [b"HUF1", struct.pack(">H", len(freq))]
    for ch in sorted(freq):
        raw = ch.encode("utf-8")
        if len(raw) > 255:
            raise ValueError("A character was too long to store.")
        if freq[ch] > 65535:
            raise ValueError("One character appears too many times for this mini project file.")
        parts.append(struct.pack(">B", len(raw)))
        parts.append(raw)
        parts.append(struct.pack(">H", freq[ch]))
    parts.append(struct.pack(">I", bit_length))
    parts.append(struct.pack(">B", pad))
    return b"".join(parts)


def _decode_header(blob):
    if not blob or len(blob) < 8 or blob[:4] != b"HUF1":
        raise ValueError("This is not a Huffman file from this project.")
    count = struct.unpack(">H", blob[4:6])[0]
    pos = 6
    freq = {}
    for _ in range(count):
        if pos >= len(blob):
            raise ValueError("The file header is cut off.")
        length = blob[pos]
        pos += 1
        raw = blob[pos:pos + length]
        pos += length
        ch = raw.decode("utf-8")
        (n,) = struct.unpack(">H", blob[pos:pos + 2])
        pos += 2
        freq[ch] = n
    bit_length = struct.unpack(">I", blob[pos:pos + 4])[0]
    pad = blob[pos + 4]
    packed = blob[pos + 5:]
    return freq, bit_length, pad, packed


def decompress(blob):
    """Rebuild the tree from the stored frequencies and decode the bit string."""
    freq, bit_length, pad, packed = _decode_header(blob)
    text_chars = []
    # Rebuild the same tree. Symbols are inserted in sorted order, as in compress.
    heap = []
    tie = 0
    for ch in sorted(freq):
        tie += 1
        heapq.heappush(heap, Node(freq[ch], symbol=ch, tie=tie))

    if len(heap) == 1:
        only = heapq.heappop(heap)
        symbol = only.symbol
        return symbol * only.freq

    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        tie += 1
        heapq.heappush(heap, Node(left.freq + right.freq, left=left, right=right, tie=tie))

    root = heap[0]
    bits = _unpack_bits(packed, pad, bit_length)
    node = root
    for bit in bits:
        node = node.left if bit == "0" else node.right
        if node.symbol is not None:
            text_chars.append(node.symbol)
            node = root
    return "".join(text_chars)
