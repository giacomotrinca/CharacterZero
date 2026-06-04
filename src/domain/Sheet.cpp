#include "domain/Sheet.h"

namespace cz {

Json Sheet::toJsonSummary() const {
    Json j = {
        {"id", id},
        {"kind", kind},
        {"subtype", subtype},
        {"name", name},
        {"updated_at", updated_at},
    };
    // Esponi race dal blob data così la home non deve caricare la scheda completa
    if (data.is_object() && data.contains("race") && data["race"].is_string()) {
        j["race"] = data["race"];
    }
    // Esponi il thumbnail (64×64) per la lista — il token completo è solo nel full
    if (data.is_object() && data.contains("token_thumb") && data["token_thumb"].is_string()) {
        j["token_thumb"] = data["token_thumb"];
    }
    return j;
}

Json Sheet::toJsonFull() const {
    return {
        {"id", id},
        {"kind", kind},
        {"subtype", subtype},
        {"name", name},
        {"data", data},
        {"created_at", created_at},
        {"updated_at", updated_at},
    };
}

}
