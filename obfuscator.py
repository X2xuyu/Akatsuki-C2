import sys
import hashlib
import struct

# ==================== S-BOX (AES-inspired) ====================
SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i


def derive_keys(secret, rounds=4):
    """Derive multiple round keys from a secret string using SHA-256 chain."""
    keys = []
    seed = secret.encode()
    for _ in range(rounds):
        seed = hashlib.sha256(seed).digest()
        keys.append(seed)
    return keys


def rot_left(byte, n):
    """Bitwise rotate left within 8 bits."""
    n %= 8
    return ((byte << n) | (byte >> (8 - n))) & 0xFF


def rot_right(byte, n):
    """Bitwise rotate right within 8 bits."""
    n %= 8
    return ((byte >> n) | (byte << (8 - n))) & 0xFF


def feistel_round(left, right, round_key):
    """One Feistel round: mix right half with round key, XOR into left."""
    mixed = []
    for i, b in enumerate(right):
        k = round_key[i % len(round_key)]
        mixed.append(SBOX[(b ^ k) & 0xFF])
    new_left = [l ^ m for l, m in zip(left, mixed)]
    return right, new_left


def inv_feistel_round(left, right, round_key):
    """Inverse Feistel round."""
    mixed = []
    for i, b in enumerate(left):
        k = round_key[i % len(round_key)]
        mixed.append(SBOX[(b ^ k) & 0xFF])
    new_right = [r ^ m for r, m in zip(right, mixed)]
    return new_right, left


def shuffle(data, seed_bytes):
    """Fisher-Yates shuffle seeded by key bytes."""
    arr = list(data)
    n = len(arr)
    rng_state = int.from_bytes(seed_bytes[:8], 'big')
    for i in range(n - 1, 0, -1):
        rng_state = (rng_state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        j = rng_state % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def unshuffle(data, seed_bytes):
    """Reverse Fisher-Yates shuffle."""
    arr = list(data)
    n = len(arr)
    rng_state = int.from_bytes(seed_bytes[:8], 'big')
    swaps = []
    for i in range(n - 1, 0, -1):
        rng_state = (rng_state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        j = rng_state % (i + 1)
        swaps.append((i, j))
    for i, j in reversed(swaps):
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def obfuscate(data, secret="Z", rounds=4):
    """
    Multi-layer obfuscation:
      1) PKCS7 padding to even length
      2) Per-byte S-BOX substitution + bit rotation
      3) Fisher-Yates shuffle (key-seeded)
      4) Feistel network (multiple rounds)
      5) Final XOR diffusion pass
    """
    keys = derive_keys(secret, rounds)
    raw = list(data.encode())

    # --- Layer 1: Pad to even length ---
    # Store original data length as 2-byte suffix (big-endian)
    orig_len = len(raw)
    raw.append((orig_len >> 8) & 0xFF)
    raw.append(orig_len & 0xFF)
    # If still odd, insert one more pad byte before the length bytes
    if len(raw) % 2 != 0:
        raw.insert(-2, 0x00)

    # --- Layer 2: S-BOX + Bit Rotation ---
    for i in range(len(raw)):
        k = keys[0][i % len(keys[0])]
        raw[i] = SBOX[raw[i]] ^ k
        raw[i] = rot_left(raw[i], (i + k) % 8)

    # --- Layer 3: Fisher-Yates Shuffle ---
    raw = shuffle(raw, keys[1])

    # --- Layer 4: Feistel Network ---
    mid = len(raw) // 2
    left, right = raw[:mid], raw[mid:]
    for r in range(rounds):
        left, right = feistel_round(left, right, keys[r % len(keys)])
    raw = left + right

    # --- Layer 5: XOR Diffusion (CBC-like chain) ---
    prev = keys[-1][0]
    for i in range(len(raw)):
        raw[i] ^= prev
        raw[i] = (raw[i] + keys[2][i % len(keys[2])]) & 0xFF
        prev = raw[i]

    return raw


def deobfuscate(encoded, secret="Z", rounds=4):
    """Reverse all layers."""
    keys = derive_keys(secret, rounds)
    raw = list(encoded)

    # --- Undo Layer 5: XOR Diffusion ---
    prev_chain = [keys[-1][0]]
    for i in range(len(raw)):
        current = raw[i]
        raw[i] = (raw[i] - keys[2][i % len(keys[2])]) & 0xFF
        raw[i] ^= prev_chain[-1]
        prev_chain.append(current)

    # --- Undo Layer 4: Feistel Network ---
    mid = len(raw) // 2
    left, right = raw[:mid], raw[mid:]
    for r in range(rounds - 1, -1, -1):
        left, right = inv_feistel_round(left, right, keys[r % len(keys)])
    raw = left + right

    # --- Undo Layer 3: Fisher-Yates Shuffle ---
    raw = unshuffle(raw, keys[1])

    # --- Undo Layer 2: S-BOX + Bit Rotation ---
    for i in range(len(raw)):
        k = keys[0][i % len(keys[0])]
        raw[i] = rot_right(raw[i], (i + k) % 8)
        raw[i] = INV_SBOX[(raw[i] ^ k) & 0xFF]

    # --- Undo Layer 1: Remove Padding ---
    # Last 2 bytes store original length (big-endian)
    orig_len = (raw[-2] << 8) | raw[-1]
    # Check if there was an extra pad byte (odd original + 2 len bytes = odd → +1 pad)
    expected_total = orig_len + 2
    if expected_total % 2 != 0:
        expected_total += 1
    raw = raw[:orig_len]

    return bytes(raw).decode()


def main():
    if len(sys.argv) < 2:
        print("╔══════════════════════════════════════╗")
        print("║           String Obfuscator          ║")
        print("╚══════════════════════════════════════╝")
        print()
        print("Usage: python obfuscator.py <string> [secret_key] [rounds]")
        print()
        print("  string      Text to obfuscate")
        print("  secret_key  Secret passphrase (default: k3ycu5t0m)")
        print("  rounds      Feistel rounds 1-16 (default: 4)")
        print()
        print("Example:")
        print("  python obfuscator.py [IP_ADDRESS]")
        return

    text = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else "k3ycu5t0m"
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    rounds = max(1, min(16, rounds))

    result = obfuscate(text, secret, rounds)
    restored = deobfuscate(result, secret, rounds)

    print()
    print(f"  [*] Original:  {text}")
    print(f"  [*] Secret:    {secret}")
    print(f"  [*] Rounds:    {rounds}")
    print(f"  [*] Length:    {len(result)} bytes")
    print(f"  [*] Encoded:   {result}")
    print(f"  [*] Verify:    {restored}")
    print(f"  [*] Match:     {'✅' if restored == text else '❌'}")
    print()
    print("Config payload:")
    print(f"  bytes({result})")


if __name__ == "__main__":
    main()