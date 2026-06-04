#include "db/Database.h"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace fs = std::filesystem;

namespace cz {

Database::Database(const fs::path& dbFile, const fs::path& migrationsDir) {
    fs::create_directories(dbFile.parent_path());
    db_ = std::make_unique<SQLite::Database>(
        dbFile.string(),
        SQLite::OPEN_READWRITE | SQLite::OPEN_CREATE);
    db_->exec("PRAGMA foreign_keys = ON;");
    db_->exec("PRAGMA journal_mode = WAL;");

    db_->exec("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);");
    runMigrations(migrationsDir);
}

int Database::currentVersion() {
    SQLite::Statement q(*db_, "SELECT COALESCE(MAX(version), 0) FROM schema_version");
    if (q.executeStep()) return q.getColumn(0).getInt();
    return 0;
}

void Database::setVersion(int v) {
    SQLite::Statement ins(*db_, "INSERT INTO schema_version(version) VALUES(?)");
    ins.bind(1, v);
    ins.exec();
}

static int parseVersion(const std::string& filename) {
    // expects NNN_*.sql
    int v = 0;
    for (char c : filename) {
        if (c == '_') break;
        if (c < '0' || c > '9') return -1;
        v = v * 10 + (c - '0');
    }
    return v;
}

void Database::runMigrations(const fs::path& migrationsDir) {
    if (!fs::exists(migrationsDir)) return;

    struct Mig { int v; fs::path path; };
    std::vector<Mig> migs;
    for (const auto& e : fs::directory_iterator(migrationsDir)) {
        if (e.path().extension() != ".sql") continue;
        int v = parseVersion(e.path().filename().string());
        if (v <= 0) continue;
        migs.push_back({v, e.path()});
    }
    std::sort(migs.begin(), migs.end(), [](auto& a, auto& b){ return a.v < b.v; });

    int current = currentVersion();
    for (const auto& m : migs) {
        if (m.v <= current) continue;
        std::ifstream in(m.path);
        if (!in) throw std::runtime_error("Cannot open migration: " + m.path.string());
        std::stringstream ss; ss << in.rdbuf();

        SQLite::Transaction tx(*db_);
        db_->exec(ss.str());
        setVersion(m.v);
        tx.commit();
    }
}

}
