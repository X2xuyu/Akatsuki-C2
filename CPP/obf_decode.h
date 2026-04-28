#pragma once
// ============================================================
// FSOCIETY — Advanced String Decoder (C++ port of obfuscator.py)
// Matches Python decoder: S-BOX + Feistel + Fisher-Yates + SHA-256
// ============================================================

#include <string>
#include <vector>
#include <cstdint>
#include <windows.h>
#include <bcrypt.h>

namespace obf {

// AES S-BOX (same as Python obfuscator)
static const uint8_t SBOX[256] = {
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
};

// Inverse S-BOX (computed at init)
static uint8_t INV_SBOX[256];
static bool _sbox_init = false;

static void init_inv_sbox() {
    if (_sbox_init) return;
    for (int i = 0; i < 256; i++) INV_SBOX[SBOX[i]] = (uint8_t)i;
    _sbox_init = true;
}

// --- SHA-256 using Windows CNG (bcrypt) ---
static std::vector<uint8_t> sha256(const uint8_t* data, size_t len) {
    std::vector<uint8_t> hash(32);
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    BCRYPT_HASH_HANDLE hHash = nullptr;

    BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_SHA256_ALGORITHM, nullptr, 0);
    if (!hAlg) return hash;
    BCryptCreateHash(hAlg, &hHash, nullptr, 0, nullptr, 0, 0);
    if (!hHash) { BCryptCloseAlgorithmProvider(hAlg, 0); return hash; }
    BCryptHashData(hHash, (PUCHAR)data, (ULONG)len, 0);
    BCryptFinishHash(hHash, hash.data(), 32, 0);
    BCryptDestroyHash(hHash);
    BCryptCloseAlgorithmProvider(hAlg, 0);
    return hash;
}

// --- Derive round keys (SHA-256 chain, matches Python derive_keys) ---
static std::vector<std::vector<uint8_t>> derive_keys(const std::string& secret, int rounds = 4) {
    std::vector<std::vector<uint8_t>> keys;
    std::vector<uint8_t> seed(secret.begin(), secret.end());
    for (int r = 0; r < rounds; r++) {
        seed = sha256(seed.data(), seed.size());
        keys.push_back(seed);
    }
    return keys;
}

// --- Bit rotation helpers ---
static inline uint8_t rot_right(uint8_t byte, int n) {
    n %= 8;
    return (uint8_t)((byte >> n) | (byte << (8 - n)));
}

// --- Main decoder (matches Python deobfuscate exactly) ---
static std::string decode(const std::vector<uint8_t>& encoded,
                          const std::string& secret = "k3ycu5t0m", int rounds = 4) {
    if (encoded.empty() || encoded.size() < 2) return "";
    init_inv_sbox();

    auto ks = derive_keys(secret, rounds);
    std::vector<uint8_t> raw(encoded.begin(), encoded.end());
    size_t n = raw.size();

    // --- Undo Layer 5: XOR Diffusion (CBC-like chain) ---
    std::vector<uint8_t> prev_chain;
    prev_chain.push_back(ks[rounds - 1][0]);
    for (size_t i = 0; i < n; i++) {
        uint8_t current = raw[i];
        raw[i] = (uint8_t)((raw[i] - ks[2][i % ks[2].size()]) & 0xFF);
        raw[i] ^= prev_chain.back();
        prev_chain.push_back(current);
    }

    // --- Undo Layer 4: Feistel Network ---
    size_t mid = n / 2;
    std::vector<uint8_t> left(raw.begin(), raw.begin() + mid);
    std::vector<uint8_t> right(raw.begin() + mid, raw.end());

    for (int rd = rounds - 1; rd >= 0; rd--) {
        auto& rk = ks[rd % (int)ks.size()];
        // Compute mixed from left
        std::vector<uint8_t> mx(left.size());
        for (size_t i = 0; i < left.size(); i++) {
            mx[i] = SBOX[(left[i] ^ rk[i % rk.size()]) & 0xFF];
        }
        // new_right = right ^ mx
        std::vector<uint8_t> new_right(right.size());
        for (size_t i = 0; i < right.size(); i++) {
            new_right[i] = right[i] ^ mx[i];
        }
        // Swap: left = new_right, right = old left
        right = left;
        left = new_right;
    }

    // Reassemble
    raw.clear();
    raw.insert(raw.end(), left.begin(), left.end());
    raw.insert(raw.end(), right.begin(), right.end());
    n = raw.size();

    // --- Undo Layer 3: Fisher-Yates Unshuffle ---
    uint64_t rs = 0;
    for (int i = 0; i < 8 && i < (int)ks[1].size(); i++) {
        rs = (rs << 8) | ks[1][i];
    }

    // Build swap list
    std::vector<std::pair<size_t, size_t>> swaps;
    uint64_t rng = rs;
    for (size_t i = n - 1; i > 0; i--) {
        rng = rng * 6364136223846793005ULL + 1442695040888963407ULL;
        size_t j = (size_t)(rng % (i + 1));
        swaps.push_back({i, j});
    }
    // Reverse the swaps
    for (int i = (int)swaps.size() - 1; i >= 0; i--) {
        std::swap(raw[swaps[i].first], raw[swaps[i].second]);
    }

    // --- Undo Layer 2: S-BOX + Bit Rotation ---
    for (size_t i = 0; i < raw.size(); i++) {
        uint8_t k = ks[0][i % ks[0].size()];
        int rt = ((int)i + (int)k) % 8;
        raw[i] = rot_right(raw[i], rt);
        raw[i] = INV_SBOX[(raw[i] ^ k) & 0xFF];
    }

    // --- Undo Layer 1: Remove Padding ---
    // Last 2 bytes store original length (big-endian)
    size_t orig_len = ((size_t)raw[raw.size()-2] << 8) | raw[raw.size()-1];
    if (orig_len > raw.size()) orig_len = 0; // safety
    raw.resize(orig_len);

    return std::string(raw.begin(), raw.end());
}

// --- Convenience: decode to wide string (for WinHTTP) ---
static std::wstring decode_wide(const std::vector<uint8_t>& encoded,
                                const std::string& secret = "k3ycu5t0m", int rounds = 4) {
    std::string narrow = decode(encoded, secret, rounds);
    if (narrow.empty()) return L"";
    int sz = MultiByteToWideChar(CP_UTF8, 0, narrow.c_str(), -1, nullptr, 0);
    std::wstring wide(sz - 1, 0);
    MultiByteToWideChar(CP_UTF8, 0, narrow.c_str(), -1, &wide[0], sz);
    return wide;
}

} // namespace obf
