#include "domain/SheetRepository.h"

namespace cz {

std::vector<Sheet> SheetRepository::list() {
    std::vector<Sheet> out;
    SQLite::Statement q(db_.handle(),
        "SELECT id, kind, subtype, name, data, created_at, updated_at "
        "FROM sheets ORDER BY updated_at DESC");
    while (q.executeStep()) {
        Sheet s;
        s.id         = q.getColumn(0).getInt64();
        s.kind       = q.getColumn(1).getString();
        s.subtype    = q.getColumn(2).getString();
        s.name       = q.getColumn(3).getString();
        s.data       = Json::parse(q.getColumn(4).getString(), nullptr, false);
        if (s.data.is_discarded()) s.data = Json::object();
        s.created_at = q.getColumn(5).getString();
        s.updated_at = q.getColumn(6).getString();
        out.push_back(std::move(s));
    }
    return out;
}

std::optional<Sheet> SheetRepository::get(long long id) {
    SQLite::Statement q(db_.handle(),
        "SELECT id, kind, subtype, name, data, created_at, updated_at "
        "FROM sheets WHERE id = ?");
    q.bind(1, static_cast<int64_t>(id));
    if (!q.executeStep()) return std::nullopt;
    Sheet s;
    s.id         = q.getColumn(0).getInt64();
    s.kind       = q.getColumn(1).getString();
    s.subtype    = q.getColumn(2).getString();
    s.name       = q.getColumn(3).getString();
    s.data       = Json::parse(q.getColumn(4).getString(), nullptr, false);
    if (s.data.is_discarded()) s.data = Json::object();
    s.created_at = q.getColumn(5).getString();
    s.updated_at = q.getColumn(6).getString();
    return s;
}

long long SheetRepository::create(const Sheet& s) {
    SQLite::Statement q(db_.handle(),
        "INSERT INTO sheets(kind, subtype, name, data) VALUES(?, ?, ?, ?)");
    q.bind(1, s.kind);
    q.bind(2, s.subtype);
    q.bind(3, s.name);
    q.bind(4, s.data.dump());
    q.exec();
    return db_.handle().getLastInsertRowid();
}

bool SheetRepository::update(long long id,
                             const std::optional<std::string>& name,
                             const std::optional<Json>& data) {
    if (!name && !data) return true;

    std::string sql = "UPDATE sheets SET updated_at = datetime('now')";
    if (name) sql += ", name = ?";
    if (data) sql += ", data = ?";
    sql += " WHERE id = ?";

    SQLite::Statement q(db_.handle(), sql);
    int idx = 1;
    if (name) q.bind(idx++, *name);
    if (data) q.bind(idx++, data->dump());
    q.bind(idx, static_cast<int64_t>(id));
    return q.exec() > 0;
}

bool SheetRepository::remove(long long id) {
    SQLite::Statement q(db_.handle(), "DELETE FROM sheets WHERE id = ?");
    q.bind(1, static_cast<int64_t>(id));
    return q.exec() > 0;
}

}
