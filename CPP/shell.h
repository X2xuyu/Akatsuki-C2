#pragma once
#include <string>

class Shell {
    std::string cwd;
public:
    Shell();
    std::string execute(const std::string& command);
    std::string getCwd() const { return cwd; }
};
