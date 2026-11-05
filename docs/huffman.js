/* Huffman coder. The file layout matches compressor.py. */

function compareNodes(a, b) {
  if (a.freq !== b.freq) return a.freq - b.freq;
  return a.tie - b.tie;
}

class MinHeap {
  constructor() { this.items = []; }
  push(node) {
    this.items.push(node);
    let i = this.items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (compareNodes(this.items[i], this.items[parent]) >= 0) break;
      [this.items[i], this.items[parent]] = [this.items[parent], this.items[i]];
      i = parent;
    }
  }
  pop() {
    const top = this.items[0];
    const last = this.items.pop();
    if (this.items.length) {
      this.items[0] = last;
      let i = 0;
      while (true) {
        const left = i * 2 + 1;
        const right = left + 1;
        let smallest = i;
        if (left < this.items.length && compareNodes(this.items[left], this.items[smallest]) < 0) smallest = left;
        if (right < this.items.length && compareNodes(this.items[right], this.items[smallest]) < 0) smallest = right;
        if (smallest === i) break;
        [this.items[i], this.items[smallest]] = [this.items[smallest], this.items[i]];
        i = smallest;
      }
    }
    return top;
  }
  get size() { return this.items.length; }
}

function sortedChars(freq) {
  return Object.keys(freq).sort((a, b) => {
    const ap = a.codePointAt(0);
    const bp = b.codePointAt(0);
    if (ap !== bp) return ap - bp;
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

function buildTree(text) {
  const freq = {};
  for (const ch of text) freq[ch] = (freq[ch] || 0) + 1;
  const heap = new MinHeap();
  let tie = 0;
  let heapOps = 0;
  for (const ch of sortedChars(freq)) {
    tie += 1;
    heap.push({ freq: freq[ch], symbol: ch, left: null, right: null, tie });
    heapOps += 1;
  }
  if (heap.size === 1) {
    const only = heap.pop();
    return { codes: { [only.symbol]: "0" }, freq, heapOps };
  }
  while (heap.size > 1) {
    const left = heap.pop();
    const right = heap.pop();
    tie += 1;
    heap.push({ freq: left.freq + right.freq, symbol: null, left, right, tie });
    heapOps += 3;
  }
  const codes = {};
  function walk(node, prefix) {
    if (node.symbol !== null && node.symbol !== undefined) {
      codes[node.symbol] = prefix || "0";
      return;
    }
    walk(node.left, prefix + "0");
    walk(node.right, prefix + "1");
  }
  walk(heap.items[0], "");
  return { codes, freq, heapOps };
}

function packBits(bits) {
  const pad = (8 - (bits.length % 8)) % 8;
  const padded = bits + "0".repeat(pad);
  const data = new Uint8Array(padded.length / 8);
  for (let i = 0; i < data.length; i++) data[i] = parseInt(padded.slice(i * 8, i * 8 + 8), 2);
  return { data, pad };
}

function encodeHeader(freq, bitLength, pad) {
  const chars = sortedChars(freq);
  const parts = [];
  parts.push(new TextEncoder().encode("HUF1"));
  const count = new Uint8Array(2);
  new DataView(count.buffer).setUint16(0, chars.length);
  parts.push(count);
  const encoder = new TextEncoder();
  for (const ch of chars) {
    const raw = encoder.encode(ch);
    if (raw.length > 255) throw new Error("A character was too long to store.");
    if (freq[ch] > 65535) throw new Error("One character appears too many times for this mini project file.");
    const piece = new Uint8Array(1 + raw.length + 2);
    piece[0] = raw.length;
    piece.set(raw, 1);
    new DataView(piece.buffer).setUint16(1 + raw.length, freq[ch]);
    parts.push(piece);
  }
  const tail = new Uint8Array(5);
  new DataView(tail.buffer).setUint32(0, bitLength);
  tail[4] = pad;
  parts.push(tail);
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let pos = 0;
  for (const part of parts) {
    out.set(part, pos);
    pos += part.length;
  }
  return out;
}

function compressText(text) {
  if (!text) throw new Error("Nothing to compress.");
  const { codes, freq, heapOps } = buildTree(text);
  let bits = "";
  for (const ch of text) bits += codes[ch];
  const { data, pad } = packBits(bits);
  const header = encodeHeader(freq, bits.length, pad);
  const blob = new Uint8Array(header.length + data.length);
  blob.set(header, 0);
  blob.set(data, header.length);
  const original = new TextEncoder().encode(text).length;
  const table = sortedChars(freq)
    .map((ch) => ({ char: ch, freq: freq[ch], code: codes[ch] }))
    .sort((a, b) => b.freq - a.freq || (a.char < b.char ? -1 : 1));
  const saved = original - blob.length;
  return {
    blob,
    originalBytes: original,
    compressedBytes: blob.length,
    savedPercent: original ? Math.round((saved / original) * 1000) / 10 : 0,
    heapOperations: heapOps,
    alphabet: Object.keys(freq).length,
    table,
  };
}

function decodeHeader(blob) {
  if (blob.length < 8 || String.fromCharCode(...blob.slice(0, 4)) !== "HUF1") {
    throw new Error("This is not a Huffman file from this project.");
  }
  const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
  const count = view.getUint16(4);
  let pos = 6;
  const freq = {};
  const decoder = new TextDecoder();
  for (let i = 0; i < count; i++) {
    const length = blob[pos];
    pos += 1;
    const raw = blob.slice(pos, pos + length);
    pos += length;
    const ch = decoder.decode(raw);
    const n = view.getUint16(pos);
    pos += 2;
    freq[ch] = n;
  }
  const bitLength = view.getUint32(pos);
  const pad = blob[pos + 4];
  const packed = blob.slice(pos + 5);
  return { freq, bitLength, pad, packed };
}

function decompressBytes(blob) {
  const bytes = blob instanceof Uint8Array ? blob : new Uint8Array(blob);
  const { freq, bitLength, pad, packed } = decodeHeader(bytes);
  const heap = new MinHeap();
  let tie = 0;
  for (const ch of sortedChars(freq)) {
    tie += 1;
    heap.push({ freq: freq[ch], symbol: ch, left: null, right: null, tie });
  }
  if (heap.size === 1) {
    const only = heap.pop();
    return only.symbol.repeat(only.freq);
  }
  while (heap.size > 1) {
    const left = heap.pop();
    const right = heap.pop();
    tie += 1;
    heap.push({ freq: left.freq + right.freq, symbol: null, left, right, tie });
  }
  const root = heap.items[0];
  let bitString = Array.from(packed).map((b) => b.toString(2).padStart(8, "0")).join("");
  if (pad) bitString = bitString.slice(0, bitString.length - pad);
  bitString = bitString.slice(0, bitLength);
  let node = root;
  let text = "";
  for (const bit of bitString) {
    node = bit === "0" ? node.left : node.right;
    if (node.symbol !== null && node.symbol !== undefined) {
      text += node.symbol;
      node = root;
    }
  }
  return text;
}

const huffmanApi = { compressText, decompressBytes };
if (typeof module !== "undefined") module.exports = huffmanApi;
