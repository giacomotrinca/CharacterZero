#pragma once
#include "server/Json.h"
#include <string>
#include <vector>

namespace cz {

struct SubtypeDef {
    std::string value;
    std::string label;
};

struct KindDef {
    std::string             value;
    std::string             label;
    std::string             description;
    std::string             subtypeGroupLabel; // label for the subtype selector step
    std::vector<SubtypeDef> subtypes;
    bool                    usesClasses;       // true if this kind has the D&D class system
};

class Schema {
public:
    static const std::vector<KindDef>& kinds();

    static bool isValidKind(const std::string& kind);
    static bool isValidSubtypeFor(const std::string& kind, const std::string& subtype);

    static Json toJson();
};

}
