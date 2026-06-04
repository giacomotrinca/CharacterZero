#pragma once
#include "server/Json.h"
#include <string>

namespace cz {

struct Sheet {
    long long   id        = 0;
    std::string kind;       // "character" | "npc"
    std::string subtype;    // "human" | "beast" | ...
    std::string name;
    Json        data       = Json::object();
    std::string created_at;
    std::string updated_at;

    Json toJsonSummary() const;
    Json toJsonFull()    const;
};

}
