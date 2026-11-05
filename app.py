"""Small web tool for the DAA mini project: compress notes with Huffman coding."""

import io
import os
import struct

from flask import Flask, jsonify, render_template, request, send_file

from compressor import compress, decompress

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

SAMPLE = "\n".join([
    "Design and Analysis of Algorithms. Greedy method. Huffman coding.",
    "A min-heap stores the character counts. The two smallest counts are merged.",
    "Frequent characters receive short codes. Rare characters receive long codes.",
] * 12)


@app.route("/")
def index():
    return render_template("index.html", sample=SAMPLE)


@app.route("/compress", methods=["POST"])
def compress_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    try:
        result = compress(text)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    blob = result.pop("blob")
    # Keep the file in memory only for this response. The page downloads it.
    result["file_base64"] = _b64(blob)
    result["ok"] = True
    return jsonify(result)


@app.route("/decompress", methods=["POST"])
def decompress_route():
    upload = request.files.get("file")
    if upload is None or upload.filename == "":
        return jsonify({"ok": False, "error": "Choose a .huf file first."}), 400
    try:
        text = decompress(upload.read())
    except (ValueError, KeyError, UnicodeDecodeError, struct.error):
        return jsonify({"ok": False, "error": "Could not restore that file. Use a .huf file made by PackLite."}), 400
    return jsonify({"ok": True, "text": text, "characters": len(text)})


@app.route("/download", methods=["POST"])
def download_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    try:
        result = compress(text)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return send_file(
        io.BytesIO(result["blob"]),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name="notes.huf",
    )


def _b64(blob):
    import base64
    return base64.b64encode(blob).decode("ascii")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(debug=False, host="127.0.0.1", port=port)
