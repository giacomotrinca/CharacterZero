#pragma once
#include "db/Database.h"
#include "domain/Sheet.h"
#include <optional>
#include <vector>

namespace cz {

class SheetRepository {
public:
    explicit SheetRepository(Database& db) : db_(db) {}

    std::vector<Sheet>  list();
    std::optional<Sheet> get(long long id);
    long long           create(const Sheet& s);
    bool                update(long long id, const std::optional<std::string>& name,
                               const std::optional<Json>& data);
    bool                remove(long long id);

private:
    Database& db_;
};

}
