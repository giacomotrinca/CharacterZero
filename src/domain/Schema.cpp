#include "domain/Schema.h"

namespace cz {

const std::vector<KindDef>& Schema::kinds() {
    static const std::vector<KindDef> k = {
        {
            "character", "Personaggio",
            "Un viandante guidato da volontà propria",
            "Razza",
            { {"human", "Umano"} },
            true,
        },
        {
            "npc", "PNG",
            "Bestie, alleati, antagonisti del cammino",
            "Tipo",
            { {"beast", "Bestia"} },
            false,
        },
    };
    return k;
}

bool Schema::isValidKind(const std::string& kind) {
    for (const auto& k : kinds()) {
        if (k.value == kind) return true;
    }
    return false;
}

bool Schema::isValidSubtypeFor(const std::string& kind, const std::string& subtype) {
    for (const auto& k : kinds()) {
        if (k.value != kind) continue;
        for (const auto& s : k.subtypes) {
            if (s.value == subtype) return true;
        }
        return false;
    }
    return false;
}

Json Schema::toJson() {
    Json arr = Json::array();
    for (const auto& k : kinds()) {
        Json subs = Json::array();
        for (const auto& s : k.subtypes) {
            subs.push_back({{"value", s.value}, {"label", s.label}});
        }
        arr.push_back({
            {"value",             k.value},
            {"label",             k.label},
            {"description",       k.description},
            {"subtypeGroupLabel", k.subtypeGroupLabel},
            {"subtypes",          subs},
            {"usesClasses",       k.usesClasses},
        });
    }
    return {{"kinds", arr}};
}

}
