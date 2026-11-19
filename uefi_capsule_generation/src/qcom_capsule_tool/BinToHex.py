# --------------------------------------------------------------------
# Copyright (c) 2025 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
# --------------------------------------------------------------------

import sys


def bin_to_hex(input_file, output_file):
    try:
        with open(input_file, "rb") as f:
            binary_data = f.read()
    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
        return

    # Calculate the size of the binary file and create the 32-bit header
    file_size = len(binary_data)
    header = f"{file_size:08x}"

    hex_chunks = [header]
    for i in range(0, len(binary_data), 4):
        # Pad a short last chunk with zeros after the data: the header
        # holds the real length, so the reader keeps only the first bytes.
        chunk = binary_data[i : i + 4].ljust(4, b"\x00")
        hex_chunks.append(chunk.hex())

    try:
        with open(output_file, "w") as f:
            f.write(" ".join(hex_chunks))
    except IOError:
        print(f"Error: Could not write to file {output_file}.")
        return

    print(f"Conversion successful! Hex data with header written to {output_file}")


def main():
    if len(sys.argv) != 3:
        print("Usage: qcom-capsule-tool bin-to-hex <input_file> <output_file>")
        sys.exit(1)

    bin_to_hex(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
